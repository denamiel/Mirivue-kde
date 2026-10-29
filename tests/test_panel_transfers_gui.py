"""Real Qt input, transfer workers and disposable files across both panes.

Only the KIO transport is substituted. Its native service requires a desktop
session; all frontend routing, worker completion and directory updates run.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QEvent, QItemSelectionModel, QMimeData, QPoint, QPointF, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeySequence, QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
from mirivue.app import Window
from mirivue.metadata import basic_entry
from mirivue.item_presentation import map_file_index
from mirivue.platform_services import services
from mirivue.movement import MovementMixin


class TestPanelTransfersGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-pane-transfers-')
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root/'settings.ini'), QSettings.IniFormat)
        settings.setValue('media/start-preview-panel', False)
        with patch('mirivue.app.mirivue_settings', return_value=settings):
            self.window = Window()
        self.window.show()
        self.window.activateWindow()
        self.window.set_split_view(True, navigate_new=False)
        self.drain()
        for pane, name in zip(self.window.panes, ('left', 'right')):
            self.window.activate_pane(pane)
            folder = self.root/name
            folder.mkdir()
            self.window.folder = pane.folder = str(folder)
            pane.model.clear()
        self.window.activate_pane(self.window.panes[0])
        self.window.watch_visible_directories()
        # Completion must work without depending on delivery of a watcher event.
        self.window.visible_watcher.blockSignals(True)
        self.calls = []
        self.resets = []
        for pane in self.window.panes:
            pane.model.modelReset.connect(lambda p=pane: self.resets.append(p))
        original_tool_path = services.tool_path
        self.tool_patch = patch.object(services, 'tool_path', side_effect=lambda name:
            '/test/mirivue-kio-service' if name == 'mirivue-kio-service' else original_tool_path(name))
        self.transport_patch = patch.object(services, 'transfer_kio', side_effect=self.transfer)
        self.confirm_patch = patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes)
        for substitute in (self.tool_patch, self.transport_patch, self.confirm_patch):
            substitute.start()
            self.addCleanup(substitute.stop)
        self.counter = 0

    def tearDown(self):
        self.app.clipboard().clear()
        self.window.quit_requested = self.window.closing = True
        self.window.close()
        self.drain()
        self.temporary.cleanup()

    def drain(self):
        for _ in range(5):
            self.app.processEvents()

    def wait_for(self, condition):
        deadline = time.monotonic() + 5
        while not condition() and time.monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(5)
        self.assertTrue(condition(), 'le transfert ou sa mise à jour ne s’est pas terminé')

    def transfer(self, sources, destination, move, progress, cancelled, operation=None):
        operation = operation or ('move' if move else 'copy')
        self.calls.append((operation, list(sources), destination))
        folder = Path(QUrl(destination).toLocalFile())
        for raw in sources:
            source = Path(QUrl(raw).toLocalFile())
            target = folder/source.name
            if target.exists() or target.is_symlink():
                return False, 'collision dans les données de test'
            if operation == 'link':
                target.symlink_to(source, target_is_directory=source.is_dir())
            elif move:
                shutil.move(source, target)
            elif source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        progress(100)
        return True, ''

    def add_file(self, pane, name=None):
        self.counter += 1
        path = Path(pane.folder)/(name or f'élément-{self.counter}.txt')
        path.write_bytes(f'contenu inchangé {self.counter}'.encode())
        pane.model.add(basic_entry(path))
        self.drain()
        return path

    def select(self, pane, paths):
        self.window.activate_pane(pane)
        pane.table.selectionModel().clearSelection()
        for path in paths:
            row = next(i for i, row in enumerate(pane.model.rows) if row.path == path)
            index = map_file_index(pane.proxy, pane.model.index(row, 0))
            pane.table.selectionModel().select(index, QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.window.update_main_menu_states()
        self.window.active_view().setFocus()
        self.drain()

    def drop(self, source, target, paths, modifiers=Qt.KeyboardModifier.NoModifier, position=None):
        view = target.content_stack.currentWidget()
        self.drain()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        mime.setData('application/x-mirivue-files', b'1')
        mime.setData('application/x-mirivue-source-pane', source.table._backend.drag_token.encode())
        point = position or QPoint(max(20, view.viewport().width()-30), max(60, view.viewport().height()-30))
        actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction
        for event in (QDragEnterEvent(point, actions, mime, Qt.MouseButton.LeftButton, modifiers),
                      QDragMoveEvent(point, actions, mime, Qt.MouseButton.LeftButton, modifiers),
                      QDropEvent(QPointF(point), actions, mime, Qt.MouseButton.LeftButton, modifiers)):
            self.app.sendEvent(view.viewport(), event)
            self.assertTrue(event.isAccepted(), f'{type(event).__name__} refusé')
        return event

    def completed(self, count):
        self.wait_for(lambda: len(self.calls) == count and self.window.kio_transfer_worker is None)
        self.drain()

    def test_copy_and_move_drops_in_all_nine_view_pairs_and_both_directions(self):
        w = self.window
        for source_mode in range(3):
            for target_mode in range(3):
                for source, target in (w.panes, list(reversed(w.panes))):
                    for copy in (True, False):
                        with self.subTest(source_view=source_mode, target_view=target_mode,
                                          source=source.folder, copy=copy):
                            source.content_stack.setCurrentIndex(source_mode)
                            target.content_stack.setCurrentIndex(target_mode)
                            path = self.add_file(source)
                            payload = path.read_bytes()
                            self.select(source, [path])
                            before = len(self.calls)
                            event = self.drop(source, target, [path],
                                Qt.ControlModifier if copy else Qt.ShiftModifier)
                            self.completed(before+1)
                            result = Path(target.folder)/path.name
                            self.assertEqual(event.dropAction(), Qt.CopyAction if copy else Qt.MoveAction)
                            self.assertEqual(result.read_bytes(), payload)
                            self.assertEqual(path.exists(), copy)
                            self.assertEqual(path in {r.path for r in source.model.rows}, copy)
                            self.assertIn(result, {r.path for r in target.model.rows})
                            self.assertEqual([i.data() for i in target.table.selectionModel().selectedRows()], [path.name])
                            self.assertIs(w.bound_pane, source)
        self.assertEqual(self.resets, [])

    def test_default_drop_menu_copy_move_link_and_cancel(self):
        source, target = self.window.panes
        for operation, title in (('copy', 'Copier ici'), ('move', 'Déplacer ici'),
                                 ('link', 'Créer un lien ici'), ('cancel', 'Annuler')):
            with self.subTest(operation=operation):
                path = self.add_file(source)
                self.select(source, [path])
                before = len(self.calls)
                def choose():
                    menu = self.app.activePopupWidget()
                    if isinstance(menu, QMenu):
                        action = next(action for action in menu.actions() if action.text().startswith(title))
                        menu.setActiveAction(action)
                        QTest.keyClick(menu, Qt.Key_Return)
                timer = QTimer()
                timer.timeout.connect(choose)
                timer.start(5)
                try:
                    self.drop(source, target, [path])
                    self.drain()
                    if operation != 'cancel': self.completed(before+1)
                finally:
                    timer.stop()
                result = Path(target.folder)/path.name
                self.assertEqual(result.exists(), operation != 'cancel')
                self.assertEqual(result.is_symlink(), operation == 'link')
                self.assertEqual(path.exists(), operation != 'move')
                self.assertEqual(len(self.calls), before+(operation != 'cancel'))

    def test_drop_on_subfolder_and_multiple_files_and_directory(self):
        source, target = self.window.panes
        folder = Path(target.folder)/'Sous-dossier'
        folder.mkdir()
        target.model.add(basic_entry(folder, is_dir=True))
        first = self.add_file(source, 'Été & vacances.txt')
        second = self.add_file(source, 'autre nom.txt')
        nested = Path(source.folder)/'Dossier sélectionné'
        nested.mkdir()
        (nested/'enfant.txt').write_bytes(b'arborescence')
        source.model.add(basic_entry(nested, is_dir=True))
        self.select(source, [first, second, nested])
        self.drain()
        row = next(i for i, item in enumerate(target.model.rows) if item.path == folder)
        index = map_file_index(target.proxy, target.model.index(row, 0))
        point = target.table.visualRect(index).center()
        # Native item hit-testing uses the name cell for a folder drop.
        point.setX(35)
        self.drop(source, target, [first, second, nested], Qt.ShiftModifier, point)
        self.completed(1)
        self.assertEqual((folder/nested.name/'enfant.txt').read_bytes(), b'arborescence')
        self.assertTrue(all((folder/path.name).exists() and not path.exists() for path in (first, second, nested)))
        self.assertEqual(source.model.rows, [])

    def test_ctrl_shift_drop_creates_a_link_in_each_view(self):
        source, target = self.window.panes
        for mode in range(3):
            with self.subTest(mode=mode):
                source.content_stack.setCurrentIndex(mode)
                target.content_stack.setCurrentIndex(mode)
                path = self.add_file(source)
                self.select(source, [path])
                before = len(self.calls)
                self.drop(source, target, [path], Qt.ControlModifier | Qt.ShiftModifier)
                self.completed(before+1)
                result = Path(target.folder)/path.name
                self.assertTrue(result.is_symlink())
                self.assertEqual(result.resolve(), path)
                self.assertTrue(path.exists())
                self.assertIn(path, {row.path for row in source.model.rows})
                self.assertIn(result, {row.path for row in target.model.rows})
        self.assertEqual(self.resets, [])

    def test_keyboard_clipboard_and_other_pane_commands_transfer_files(self):
        source, target = self.window.panes
        for mode in range(3):
            for clipboard, copy in ((True, True), (True, False), (False, True), (False, False)):
                with self.subTest(mode=mode, clipboard=clipboard, copy=copy):
                    source.content_stack.setCurrentIndex(mode)
                    target.content_stack.setCurrentIndex(mode)
                    path = self.add_file(source)
                    self.select(source, [path])
                    before = len(self.calls)
                    if clipboard:
                        QTest.keySequence(self.window.active_view(), QKeySequence('Ctrl+C' if copy else 'Ctrl+X'))
                        self.window.activate_pane(target)
                        self.window.active_view().setFocus()
                        QTest.keySequence(self.window.active_view(), QKeySequence('Ctrl+V'))
                    else:
                        QTest.keySequence(self.window.active_view(), QKeySequence('Shift+F5' if copy else 'Shift+F6'))
                    self.completed(before+1)
                    self.assertTrue((Path(target.folder)/path.name).is_file())
                    self.assertEqual(path.exists(), copy)
                    self.assertEqual(path in {row.path for row in source.model.rows}, copy)
        self.assertEqual(self.resets, [])

    def test_native_places_and_breadcrumb_completion_reconciles_active_source(self):
        w = self.window
        source, target = w.panes
        for copy in (False, True):
            for mode in range(3):
                with self.subTest(copy=copy, mode=mode):
                    source.content_stack.setCurrentIndex(mode)
                    target.content_stack.setCurrentIndex(mode)
                    path = self.add_file(source)
                    self.select(source, [path])
                    w.watch_visible_directories()
                    result = Path(target.folder)/path.name
                    shutil.copy2(path, result) if copy else shutil.move(path, result)
                    # Another pane may reconfigure watches before KIO completion.
                    # It must not erase the delta for the already displayed pane.
                    w.watch_visible_directories()
                    with patch.object(w, 'navigate') as navigate:
                        w.native_drop_completed()
                        self.wait_for(lambda: not w._visible_workers)
                        self.drain()
                        navigate.assert_not_called()
                    self.assertEqual(path in {r.path for r in source.model.rows}, copy)
                    self.assertIn(result, {r.path for r in target.model.rows})
                    self.assertIs(w.bound_pane, source)
        self.assertEqual(self.resets, [])
        # Keep the previous recovery behavior if a whole displayed directory
        # was moved away through Places, instead of one of its children.
        shutil.move(target.folder, self.root/'dossier déplacé ailleurs')
        with patch.object(w, 'navigate') as navigate:
            w.native_drop_completed()
            navigate.assert_called_once_with(str(self.root))

    def test_native_drag_checks_selected_sources_before_starting(self):
        source = self.window.panes[0]
        path = self.add_file(source)
        self.select(source, [path])
        view = self.window.active_view()
        index = source.table.selectionModel().selectedRows()[0]
        point = view.visualRect(index).center()
        point.setX(35)
        with patch.object(self.window, 'movement_locked', return_value=True) as locked:
            QTest.mousePress(view.viewport(), Qt.LeftButton, pos=point)
            movement = QMouseEvent(QEvent.MouseMove, QPointF(point+QPoint(80, 0)),
                                   QPointF(view.viewport().mapToGlobal(point+QPoint(80, 0))),
                                   Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
            self.app.sendEvent(view.viewport(), movement)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=point+QPoint(80, 0))
            self.assertIn([path], [call.args[0] for call in locked.call_args_list])

    def test_remote_selection_and_clipboard_keep_kio_urls(self):
        paths = ['smb://serveur/partage/un%20fichier.txt', 'sftp://hote/home/p/autre.txt']
        owner = SimpleNamespace(selected_indexes=lambda: range(3),
                                row=lambda index: SimpleNamespace(path=paths[index % 2]))
        self.assertEqual(MovementMixin.selected_entries(owner), paths)
        self.assertEqual(self.window.choose_associated_entries(iter(paths), 'copie'), paths)
        local = [self.add_file(self.window.panes[0]), self.add_file(self.window.panes[0])]
        self.assertEqual(self.window.choose_associated_entries(iter(local), 'copie'), local)
        for cut in (False, True):
            with self.subTest(cut=cut), patch.object(self.window, 'selected_entries', return_value=paths):
                self.window.active_view().setFocus()
                self.window.copy_selection(cut)
                urls = self.app.clipboard().mimeData().urls()
                self.assertEqual([url.toString() for url in urls], [QUrl(path).toString() for path in paths])
                self.assertTrue(all(not url.isLocalFile() for url in urls))
                with patch.object(self.window, 'start_kio_transfer') as transfer:
                    self.window.paste_selection(self.window.panes[1].folder)
                    self.assertEqual(transfer.call_args.args[0], [QUrl(path).toString() for path in paths])
                    self.assertEqual(transfer.call_args.kwargs['move'], cut)


if __name__ == '__main__':
    unittest.main()
