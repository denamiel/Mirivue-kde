"""Physical key events through Dolphin's real engine, not source assertions."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, QSettings, Qt, QItemSelectionModel
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QTextEdit
from mirivue.app import Window
from mirivue.metadata import basic_entry
from mirivue.keyboard import conflicts, terminal_selection
from mirivue.configuration import ShortcutConfigurationDialog


class TestKeyboardGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-keys-')
        self.root = Path(self.temporary.name)
        self.settings = QSettings(str(self.root/'settings.ini'), QSettings.IniFormat)
        self.settings.setValue('media/start-preview-panel', False)
        with patch('mirivue.app.mirivue_settings', return_value=self.settings):
            self.window = Window()
        self.window.show()
        self.window.activateWindow()
        self.drain()
        self.seed(self.window.bound_pane, 'left')

    def tearDown(self):
        # Offscreen QPA keeps a Python-created QMimeData in a process static.
        # Release test clipboard contents while the Python runtime is alive.
        self.app.clipboard().clear()
        self.window.quit_requested = self.window.closing = True
        self.window.close()
        self.drain()
        self.temporary.cleanup()

    def drain(self):
        for _ in range(4):
            self.app.processEvents()

    def seed(self, pane, name):
        self.window.activate_pane(pane)
        directory = self.root/name
        directory.mkdir()
        self.window.folder = pane.folder = str(directory)
        for number in range(4):
            path = directory/f'file-{number}.txt'
            path.write_text('test keyboard content')
            pane.model.add(basic_entry(path))
        child = directory/'subfolder'
        child.mkdir()
        pane.model.add(basic_entry(child, is_dir=True))
        self.window.update_main_menu_states()
        self.drain()

    def focus(self):
        view = self.window.active_view()
        QTest.mouseClick(view.viewport(), Qt.LeftButton, pos=QPoint(12, max(30, view.height()-20)))
        view.setFocus()
        self.drain()
        return view

    def press(self, sequence, target=None):
        QTest.keySequence(target or self.app.focusWidget(), QKeySequence(sequence))
        self.drain()

    def select(self, row=0):
        if isinstance(row, str):
            row = next(i for i in range(self.window.proxy.rowCount()) if self.window.proxy.index(i, 0).data() == row)
        view = self.window.active_view()
        index = self.window.proxy.index(row, 0)
        view.setCurrentIndex(index)
        view.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self.window.update_main_menu_states()
        self.drain()

    def test_every_registered_key_reaches_its_command_in_all_views_and_panes(self):
        """No jobs/dialogs are started: this test isolates event dispatch."""
        w = self.window
        w.set_split_view(True, navigate_new=False)
        self.seed(w.panes[1], 'right')
        hits = []
        w.rename_f2 = lambda: hits.append('rename')
        w.open_selected = lambda *args: hits.append('unexpected-open')
        for pane in w.panes:
            for view in (pane.table, pane.icons, pane.compact):
                view.activated.disconnect()
                view.activated.connect(lambda *args: hits.append('unexpected-open'))
        for binding in w.shortcut_bindings:
            for target in binding['targets']:
                signal = target.triggered if isinstance(target, QAction) else target.activated
                signal.disconnect()
                if isinstance(target, QAction):
                    try:
                        target.toggled.disconnect()
                    except RuntimeError:
                        pass
                signal.connect(lambda *args, identifier=binding['id']: hits.append(identifier))
        tested = 0
        with patch.object(QMessageBox, 'warning'), patch.object(QMessageBox, 'information'), \
                patch.object(QInputDialog, 'getText', return_value=('', False)):
            for menus in (False, True):
                w.menu_visibility.action.setChecked(menus)
                w.menu_visibility.apply()
                for pane in list(w.panes):
                    w.activate_pane(pane)
                    for mode in (0, 1, 2):
                        w.change_view(mode)
                        self.drain()
                        view = self.focus()
                        for binding in w.shortcut_bindings:
                            for target in binding['targets']:
                                target.setEnabled(True)
                            for sequence in binding['sequences']:
                                with self.subTest(menus=menus, pane=pane.folder, view=mode,
                                                  command=binding['id'], key=sequence):
                                    hits.clear()
                                    self.press(sequence)
                                    self.assertEqual(hits, [binding['id']])
                                    tested += 1
        self.assertGreater(tested, 900)
        print(f'\nRaccourcis : {tested} scénarios de déclenchement vérifiés.')

    def test_kde_aliases_and_dolphin_specific_defaults(self):
        bindings = {b['id']: b['sequences'] for b in self.window.shortcut_bindings}
        expected = {
            'properties': ['Alt+Return', 'Alt+Enter'], 'location': ['Ctrl+L', 'Alt+D'],
            'copy-to-inactive': ['Shift+F5'], 'move-to-inactive': ['Shift+F6'],
            'filter': ['Ctrl+I', '/'], 'previews': ['F12'],
            'terminal': ['Shift+F4'], 'terminal-selection': ['Alt+Shift+F4'],
        }
        for identifier, keys in expected.items():
            self.assertEqual(set(bindings[identifier]), set(keys), identifier)
        self.assertIn('Ctrl+=', bindings['zoom-in'])
        self.assertIn('Ctrl+Ins', bindings['copy'])
        self.assertIn('Shift+Ins', bindings['paste'])
        self.assertIn('Ctrl+PgDown', bindings['tab-next'])
        self.assertNotIn('Shift+Del', bindings['cut'])
        self.assertEqual(conflicts(self.window, {b['id']: b['sequence'] for b in self.window.shortcut_bindings}), [])

    def test_custom_bindings_persist_disable_and_detect_secondary_conflicts(self):
        w = self.window
        w.apply_shortcut_bindings({'select-all': 'Ctrl+Alt+A', 'refresh': ''})
        view = self.focus()
        self.press('Ctrl+A')
        self.assertEqual(len(view.selectionModel().selectedRows()), 0)
        self.press('Ctrl+Alt+A')
        self.assertEqual(len(view.selectionModel().selectedRows()), 5)
        self.assertEqual(w.refresh.shortcuts(), [])
        w.apply_shortcut_bindings()
        self.assertEqual(w.select_all_action.shortcut().toString(), 'Ctrl+Alt+A')
        values = {b['id']: b['sequence'] for b in w.shortcut_bindings}
        values['refresh'] = 'Ctrl+='
        self.assertIn('Ctrl+=', conflicts(w, values))
        dialog = ShortcutConfigurationDialog(w)
        dialog.restore_defaults()
        self.assertTrue(dialog.apply())
        self.assertFalse(w.settings.contains('shortcuts/select-all'))
        self.assertIn(QKeySequence('Ctrl+='), w.zoom_in_action.shortcuts())
        dialog.close()

    def test_selection_clipboard_and_path_command_work_in_every_view(self):
        for mode in (0, 1, 2):
            with self.subTest(view=mode):
                self.window.change_view(mode)
                view = self.focus()
                self.press('Ctrl+A')
                self.assertEqual(len(view.selectionModel().selectedRows()), 5)
                self.press('Ctrl+Shift+A')
                self.assertEqual(len(view.selectionModel().selectedRows()), 0)
                self.select(1)
                paths = [str(self.window.row(index).path) for index in self.window.selected_indexes()]
                self.press('Ctrl+Alt+C')
                self.assertEqual(QApplication.clipboard().text().splitlines(), paths)
                self.press('Ctrl+Ins')
                self.assertEqual(len(QApplication.clipboard().mimeData().urls()), 1)

    def test_filter_repeated_shortcuts_focus_instead_of_hiding(self):
        self.focus()
        self.press('/')
        self.assertTrue(self.window.quick_filter.hasFocus())
        self.window.quick_filter.setText('file-1')
        self.press('Ctrl+I')
        self.assertTrue(self.window.filter_panel.isVisible())
        self.assertEqual(self.window.quick_filter.selectedText(), 'file-1')
        self.assertEqual(self.window.proxy.rowCount(), 1)
        self.press('Escape')
        self.assertFalse(self.window.filter_panel.isVisible())
        self.assertEqual(self.window.proxy.rowCount(), 5)
        self.assertTrue(self.window.active_file_view_has_focus())

    def test_editor_shortcuts_do_not_touch_files_or_file_history(self):
        w = self.window
        self.focus()
        self.select(1)
        w.filter_panel.show()
        field = w.quick_filter
        field.setFocus()
        field.setText('file')
        self.drain()
        with patch.object(w, 'delete_selected') as delete, patch.object(w, 'copy_selection') as copy:
            self.press('Ctrl+A', field)
            self.press('Ctrl+C', field)
            self.assertEqual(QApplication.clipboard().text(), 'file')
            self.press('Shift+Delete', field)
            self.assertEqual(field.text(), '')
            self.press('Ctrl+Z', field)
            self.assertEqual(field.text(), 'file')
            self.press('Ctrl+A', field)
            self.press('Shift+Insert', field)
            self.assertEqual(field.text(), 'file')
            self.press('Backspace', field)
            self.assertEqual(field.text(), 'fil')
            delete.assert_not_called()
            copy.assert_not_called()
        self.assertEqual(len(w.selected_indexes()), 1)

    def test_tab_shortcuts_and_focus_other_pane(self):
        w = self.window
        for _ in range(2):
            w.open_new_tab(w.folder, active=False)
        self.focus()
        for sequence, index in (('Alt+2', 1), ('Alt+0', 2), ('Alt+1', 0),
                                ('Ctrl+PgDown', 1), ('Ctrl+Tab', 2),
                                ('Ctrl+Shift+Tab', 1), ('Ctrl+PgUp', 0)):
            self.press(sequence)
            self.assertEqual(w.tab_bar.currentIndex(), index, sequence)
        w.set_split_view(True, navigate_new=False)
        previous = w.bound_pane
        self.focus()
        self.press('Ctrl+F3')
        self.assertIsNot(w.bound_pane, previous)
        self.assertTrue(w.active_file_view_has_focus())

    def test_terminal_shortcuts_distinguish_current_folder_and_selection(self):
        w = self.window
        self.focus()
        # A directory and a file have distinct target directories.
        self.select('subfolder')
        with patch('mirivue.platform_services.services.start_terminal', return_value=True) as terminal:
            self.press('Shift+F4')
            terminal.assert_called_once_with(w.folder)
            terminal.reset_mock()
            self.press('Alt+Shift+F4')
            terminal.assert_called_once_with(str(self.root/'left'/'subfolder'))
            terminal.reset_mock()
            self.select('file-0.txt')
            self.press('Alt+Shift+F4')
            terminal.assert_called_once_with(str(self.root/'left'))

    def test_rename_editor_keeps_native_editing_in_all_views(self):
        for mode in (0, 1, 2):
            with self.subTest(view=mode):
                self.window.change_view(mode)
                view = self.focus()
                self.select('file-0.txt')
                self.press('F2')
                editor = next((e for e in view.findChildren(QTextEdit) if e.isVisible()), None)
                self.assertIsNotNone(editor)
                self.assertEqual(editor.textCursor().selectedText(), 'file-0')
                self.press('Ctrl+A', editor)
                self.assertEqual(editor.textCursor().selectedText(), 'file-0.txt')
                self.press('Escape', editor)
                self.assertTrue((self.root/'left'/'file-0.txt').exists())

    def test_native_navigation_selection_and_activation_in_all_views(self):
        for mode in (0, 1, 2):
            with self.subTest(view=mode):
                self.window.change_view(mode)
                view = self.focus()
                self.select('file-0.txt')
                self.press('End')
                self.assertEqual(view.currentIndex().row(), self.window.proxy.rowCount()-1)
                self.press('Home')
                self.assertEqual(view.currentIndex().row(), 0)
                self.press('Shift+End')
                self.assertEqual(len(view.selectionModel().selectedRows()), 5)
                self.press('Escape')
                self.assertEqual(len(view.selectionModel().selectedRows()), 0)
                self.select('file-0.txt')
                self.press('Ctrl+Space')
                self.assertEqual(len(view.selectionModel().selectedRows()), 0)
                activated = []
                view.activated.disconnect()
                view.activated.connect(lambda index: activated.append(index.data()))
                self.select('file-0.txt')
                self.press('Return')
                self.assertEqual(activated, ['file-0.txt'])

    def test_path_and_search_shortcuts_focus_their_editor(self):
        for mode in (0, 1, 2):
            with self.subTest(view=mode):
                self.window.change_view(mode)
                self.focus()
                self.press('Alt+D')
                self.assertTrue(self.window.bound_pane.path_input.hasFocus())
                self.assertEqual(self.window.bound_pane.path_input.selectedText(), self.window.folder)
                self.press('Escape')
                self.assertTrue(self.window.active_file_view_has_focus())
                self.press('Ctrl+F')
                self.assertTrue(self.window.search.hasFocus())
                self.press('Escape')
                self.assertTrue(self.window.active_file_view_has_focus())
                self.press('F6')
                self.assertTrue(self.window.bound_pane.path_input.hasFocus())
                self.press('F6')
                self.assertTrue(self.window.active_file_view_has_focus())

    def test_backspace_only_navigates_from_file_views(self):
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            self.focus()
            with patch.object(self.window, 'navigate_history') as back:
                self.press('Backspace')
                back.assert_called_once_with(-1)

    def test_kde_global_shortcut_settings_and_personal_priority(self):
        import json
        import subprocess
        config = self.root/'kde'
        config.mkdir()
        (config/'kdeglobals').write_text('[Shortcuts]\nCopy=Ctrl+Alt+Y\nReload=none\n')
        script = '''
import json, os
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from mirivue.app import Window
app=QApplication([])
s=QSettings(os.environ['XDG_CONFIG_HOME']+'/mirivue.ini',QSettings.IniFormat)
s.setValue('media/start-preview-panel',False)
with patch('mirivue.app.mirivue_settings',return_value=s):w=Window()
standard={b['id']:b['sequences'] for b in w.shortcut_bindings}
w.apply_shortcut_bindings({'copy':'Ctrl+Alt+U'})
personal={b['id']:b['sequences'] for b in w.shortcut_bindings}
print('KEYS_JSON='+json.dumps([standard['copy'],standard['refresh'],personal['copy']]))
w.quit_requested=w.closing=True
w.close()
'''
        env = dict(os.environ, XDG_CONFIG_HOME=str(config))
        result = subprocess.run([__import__('sys').executable, '-c', script],
                                env=env, text=True, capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        data = next(line[len('KEYS_JSON='):] for line in result.stdout.splitlines() if line.startswith('KEYS_JSON='))
        self.assertEqual(json.loads(data), [['Ctrl+Alt+Y'], [], ['Ctrl+Alt+U']])

    def test_custom_rename_binding_does_not_steal_text_selection(self):
        w = self.window
        self.focus()
        self.select('file-0.txt')
        w.apply_shortcut_bindings({'rename': 'Ctrl+A', 'select-all': ''})
        w.filter_panel.show()
        w.quick_filter.setFocus()
        w.quick_filter.setText('file')
        self.drain()
        self.press('Ctrl+A')
        self.assertEqual(w.quick_filter.selectedText(), 'file')
        self.assertTrue(w.quick_filter.hasFocus())
        self.assertFalse(any(e.isVisible() for e in w.active_view().findChildren(QTextEdit)))

    def test_keyboard_context_events_reach_native_view_in_every_layout(self):
        # Offscreen QPA does not synthesize the platform's Menu-key event.
        # Deliver its keyboard ContextMenu event, as Qt's platform plugin does.
        from PySide6.QtGui import QContextMenuEvent
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            view = self.focus()
            self.select('file-0.txt')
            contexts = []
            view.customContextMenuRequested.disconnect()
            view.customContextMenuRequested.connect(contexts.append)
            point = view.visualRect(view.currentIndex()).center()
            self.app.sendEvent(view.viewport(), QContextMenuEvent(
                QContextMenuEvent.Reason.Keyboard, point, view.viewport().mapToGlobal(point)))
            self.drain()
            self.assertEqual(len(contexts), 1)

    def test_view_panel_preview_and_zoom_commands_change_the_actual_ui(self):
        w = self.window
        self.focus()
        for sequence, mode in (('Ctrl+1', 1), ('Ctrl+2', 2), ('Ctrl+3', 0)):
            self.press(sequence)
            self.assertEqual(w.content_stack.currentIndex(), mode)
        for sequence, widget in (('F9', w.places_panel), ('F7', w.browser),
                                 ('F4', w.terminal_dock), ('F11', w.preview_dock)):
            before = widget.isVisible()
            self.press(sequence)
            self.assertEqual(widget.isVisible(), not before, sequence)
            self.press(sequence)
            self.assertEqual(widget.isVisible(), before, sequence)
        before = w.model.show_thumbnails
        with patch.object(w, 'start_thumbnails'):
            self.press('F12')
            self.assertEqual(w.model.show_thumbnails, not before)
            self.press('F12')
            self.assertEqual(w.model.show_thumbnails, before)
        w.change_view(1)
        self.focus()
        before = w.active_view().iconSize().width()
        self.press('Ctrl+=')
        self.assertGreater(w.active_view().iconSize().width(), before)
        self.press('Ctrl+-')
        self.assertEqual(w.active_view().iconSize().width(), before)
        checked = w.hidden.isChecked()
        self.press('Alt+.')
        self.assertEqual(w.hidden.isChecked(), not checked)
        self.press('Alt+.')
        self.assertEqual(w.hidden.isChecked(), checked)
