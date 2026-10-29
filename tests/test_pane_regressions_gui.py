"""Exercise focus, delayed rename commits and remote filters through Qt."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QPoint, QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit
from mirivue.app import Window
from mirivue.item_presentation import map_file_index
from mirivue.metadata import basic_entry, remote_entry


class TestPaneRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-regressions-')
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
            path = folder/'film.txt'
            path.write_text(name)
            pane.model.add(basic_entry(path))
        self.window.activate_pane(self.window.panes[0])
        self.window.watch_visible_directories()
        self.window.visible_watcher.blockSignals(True)
        self.drain()

    def tearDown(self):
        self.app.clipboard().clear()
        self.window.quit_requested = self.window.closing = True
        self.window.scanning = False
        for pane in self.window.panes:
            pane.scanning = False
        self.window.close()
        self.drain()
        self.temporary.cleanup()

    def drain(self):
        for _ in range(5):
            self.app.processEvents()

    def view(self, pane):
        return pane.content_stack.currentWidget()

    def select(self, pane, row=0):
        index = map_file_index(pane.proxy, pane.model.index(row, 0))
        view = self.view(pane)
        view.selectionModel().setCurrentIndex(index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

    def set_modes(self, mode):
        for pane in self.window.panes:
            self.window.activate_pane(pane)
            self.window.change_view(mode)
            self.select(pane)
        self.drain()

    def owns_focus(self, pane):
        focus = self.app.focusWidget()
        view = self.view(pane)
        return focus is not None and (focus is view or view.isAncestorOf(focus))

    def tab_to(self, pane, backwards=False):
        for _ in range(120):
            QTest.keyClick(self.app.focusWidget(), Qt.Key_Tab,
                          Qt.ShiftModifier if backwards else Qt.NoModifier)
            self.drain()
            if self.owns_focus(pane):
                return
        self.fail('la navigation au clavier n’atteint pas l’autre vue native')

    def test_tab_and_shift_tab_activate_the_focused_pane_before_copy(self):
        left, right = self.window.panes
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                self.set_modes(mode)
                self.window.activate_pane(left)
                self.view(left).setFocus()
                self.drain()
                for target, backwards in ((right, False), (left, True)):
                    self.tab_to(target, backwards)
                    self.assertIs(self.window.bound_pane, target)
                    self.assertTrue(self.owns_focus(target))
                    self.window.update_main_menu_states()
                    QTest.keySequence(self.app.focusWidget(), QKeySequence('Ctrl+C'))
                    self.drain()
                    urls = self.app.clipboard().mimeData().urls()
                    self.assertEqual([url.toLocalFile() for url in urls],
                                     [str(Path(target.folder)/'film.txt')])

    def begin_rename(self, pane, new_name):
        self.window.activate_pane(pane)
        self.select(pane)
        view = self.view(pane)
        view.setFocus()
        self.drain()
        QTest.keySequence(self.app.focusWidget(), QKeySequence('F2'))
        self.drain()
        # The native engine deletes the previous role editor asynchronously.
        # Only the visible editor receives the user's typing.
        editors = [editor for editor in view.findChildren(QTextEdit) if editor.isVisible()]
        self.assertEqual(len(editors), 1)
        editor = editors[0]
        self.assertTrue(editor.hasFocus())
        QTest.keyClicks(editor, new_name)
        return editor

    def click_other_pane(self, pane):
        view = self.view(pane)
        QTest.mouseClick(view.viewport(), Qt.LeftButton,
                        pos=QPoint(20, view.viewport().height()-30))
        self.drain()

    def test_leaving_rename_by_clicking_the_other_pane_commits_in_its_origin(self):
        w = self.window
        for mode in (0, 1, 2):
            self.set_modes(mode)
            for origin, other in (w.panes, list(reversed(w.panes))):
                with self.subTest(mode=mode, origin=origin.column_slot):
                    old = origin.model.rows[0].path
                    new_base = f'renamed-{mode}-{origin.column_slot}'
                    target = old.with_name(new_base+'.txt')
                    untouched = other.model.rows[0].path
                    original_other_content = untouched.read_bytes()
                    self.begin_rename(origin, new_base)
                    calls = []
                    with patch.object(w, 'start_thumbnails',
                            side_effect=lambda force_paths=(): calls.append((w.bound_pane, force_paths))):
                        self.click_other_pane(other)
                    self.assertFalse(old.exists())
                    self.assertEqual(target.read_text(), origin.column_slot)
                    self.assertEqual(origin.model.rows[0].path, target)
                    self.assertEqual(untouched.read_bytes(), original_other_content)
                    self.assertIs(w.bound_pane, other)
                    forced = [(pane, paths) for pane, paths in calls if paths]
                    self.assertEqual(forced, [(origin, (target,))])

    def test_renaming_a_folder_schedules_its_origin_scan(self):
        w = self.window
        origin, other = w.panes
        old = Path(origin.folder)/'old.folder'
        old.mkdir()
        origin.model.clear()
        origin.model.add(basic_entry(old, is_dir=True))
        self.drain()
        self.begin_rename(origin, 'new.folder')
        scanned = []
        with patch.object(w, 'scan', side_effect=lambda: scanned.append(w.bound_pane)):
            self.click_other_pane(other)
        self.assertTrue(old.with_name('new.folder').is_dir())
        self.assertFalse(old.exists())
        self.assertEqual(scanned, [origin])
        self.assertIs(w.bound_pane, other)

    def test_escape_cancels_rename_before_switching_panes(self):
        origin, other = self.window.panes
        old = origin.model.rows[0].path
        editor = self.begin_rename(origin, 'discarded')
        QTest.keyClick(editor, Qt.Key_Escape)
        self.drain()
        self.click_other_pane(other)
        self.assertTrue(old.exists())
        self.assertFalse(old.with_name('discarded.txt').exists())
        self.assertIs(self.window.bound_pane, other)

    def test_pending_rename_uses_origin_loading_state_not_destination_state(self):
        origin, other = self.window.panes
        old = origin.model.rows[0].path
        other.scanning = True
        self.window.activate_pane(other)
        index = origin.model.index(0, 0)
        self.assertTrue(origin.model.setData(index, 'renamed.txt', Qt.EditRole))
        self.drain()
        self.assertFalse(old.exists())
        self.assertTrue(old.with_name('renamed.txt').exists())
        self.assertIs(self.window.bound_pane, other)

    def test_quick_filter_uses_remote_display_names_in_all_views(self):
        w = self.window
        folder = 'smb://example.invalid/library'
        w.folder = w.bound_pane.folder = folder
        w.set_initial_listing([
            remote_entry(folder+'/opaque-1', 'Épisode 2.mkv'),
            remote_entry(folder+'/opaque-2', 'Épisode 10.mkv'),
            remote_entry(folder+'/opaque-3', 'notes.txt'),
        ])
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                w.change_view(mode)
                w.show_quick_filter()
                w.quick_filter.setText('ÉPISODE')
                self.drain()
                self.assertEqual(w.proxy.rowCount(), 2)
                self.assertEqual([w.proxy.index(row, 0).data() for row in range(2)],
                                 ['Épisode 2.mkv', 'Épisode 10.mkv'])
                w.quick_filter.setText('example.invalid')
                self.drain()
                self.assertEqual(w.proxy.rowCount(), 0)
                w.quick_filter.setText('notes.txt')
                self.drain()
                self.assertEqual(w.proxy.rowCount(), 1)
                w.close_quick_filter()
                self.drain()
                self.assertEqual(w.proxy.rowCount(), 3)

    def test_name_filter_accepts_kio_schemes_without_local_path_methods(self):
        w = self.window
        for uri in ('smb://host/share/id', 'sftp://host/folder/id',
                    'trash:/id', 'mtp:/device/id', 'zip:/tmp/archive.zip/id'):
            with self.subTest(uri=uri):
                w.set_initial_listing([remote_entry(uri, 'Nom affiché.txt')])
                w.proxy.name_filter = 'AFFICHÉ'
                self.assertTrue(w.proxy.filterAcceptsRow(0, QModelIndex()))
                w.proxy.name_filter = 'absent'
                self.assertFalse(w.proxy.filterAcceptsRow(0, QModelIndex()))
                w.proxy.name_filter = ''

    def test_local_filter_keeps_case_insensitive_matching(self):
        w = self.window
        w.show_quick_filter()
        w.quick_filter.setText('FILM')
        self.drain()
        self.assertEqual(w.proxy.rowCount(), 1)
        w.quick_filter.setText('other')
        self.drain()
        self.assertEqual(w.proxy.rowCount(), 0)
        w.close_quick_filter()
        self.drain()
        self.assertEqual(w.proxy.rowCount(), 1)
