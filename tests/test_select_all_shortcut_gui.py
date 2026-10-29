"""Real key presses through the native views, with the menu bar hidden."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QElapsedTimer, QPoint, QSettings, Qt, QItemSelectionModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit
from mirivue.app import Window
from mirivue.metadata import basic_entry


class TestSelectAllShortcut(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-select-all-')
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root / 'settings.ini'), QSettings.IniFormat)
        settings.setValue('media/start-preview-panel', False)
        with patch('mirivue.app.mirivue_settings', return_value=settings):
            self.window = Window()
        self.window.show()
        self.window.activateWindow()
        self.drain()
        self.left = self.window.panes[0]
        self.seed(self.left, 4)

    def tearDown(self):
        self.window.quit_requested = True
        self.window.closing = True
        self.window.close()
        self.drain()
        self.temporary.cleanup()

    def drain(self):
        for _ in range(5):
            self.app.processEvents()

    def seed(self, pane, count):
        self.window.activate_pane(pane)
        directory = self.root / f'files-{count}'
        directory.mkdir()
        pane.folder = self.window.folder = str(directory)
        for number in range(count):
            path = directory / f'file-{number}.txt'
            path.write_text('temporary test content')
            pane.model.add(basic_entry(path))
        child = directory / 'subfolder'
        child.mkdir()
        pane.model.add(basic_entry(child))
        self.window.update_main_menu_states()
        self.drain()

    def selected(self, pane):
        view = pane.content_stack.currentWidget()
        return [index.data() for index in view.selectionModel().selectedRows()]

    def press(self, target=None):
        QTest.keyClick(target or self.app.focusWidget(), Qt.Key_A, Qt.ControlModifier)
        self.drain()

    def focus_view(self):
        view = self.window.active_view()
        QTest.mouseClick(view.viewport(), Qt.LeftButton,
                         pos=QPoint(12, max(10, view.viewport().height() - 20)))
        self.drain()
        self.assertTrue(self.window.active_file_view_has_focus())
        return view

    def test_all_three_views_with_menus_hidden_and_visible(self):
        for menus in (False, True):
            self.window.menu_visibility.action.setChecked(menus)
            for mode in (0, 1, 2):
                with self.subTest(menus=menus, mode=mode):
                    self.window.change_view(mode)
                    self.drain()
                    view = self.focus_view()
                    view.clearSelection()
                    self.press()
                    self.assertEqual(len(self.selected(self.left)), 5)
                    self.assertIn('subfolder', self.selected(self.left))

    def test_only_the_active_pane_changes_in_each_view(self):
        self.window.set_split_view(True, navigate_new=False)
        self.drain()
        right = self.window.panes[1]
        self.seed(right, 2)
        for pane, other, expected in ((right, self.left, 3), (self.left, right, 5)):
            for mode in (0, 1, 2):
                with self.subTest(pane=expected, mode=mode):
                    self.window.activate_pane(pane)
                    self.window.change_view(mode)
                    self.drain()
                    before = self.selected(other)
                    view = self.focus_view()
                    view.clearSelection()
                    self.press()
                    self.assertEqual(len(self.selected(pane)), expected)
                    self.assertEqual(self.selected(other), before)

    def test_only_filtered_entries_are_selected(self):
        self.window.quick_filter.setText('file-1')
        self.drain()
        view = self.focus_view()
        view.clearSelection()
        self.press()
        self.assertEqual(self.selected(self.left), ['file-1.txt'])

    def test_text_fields_keep_native_select_all(self):
        for name, field in (('filter', self.window.quick_filter),
                            ('path', self.left.path_input), ('search', self.window.search)):
            with self.subTest(field=name):
                self.window.quick_filter.clear()
                if name == 'filter':
                    self.window.filter_panel.show()
                elif name == 'path':
                    self.window.toggle_pane_path_mode(self.left, True)
                else:
                    self.window.search_panel.show()
                field.setText('file')
                field.setFocus()
                self.drain()
                self.window.active_view().clearSelection()
                self.assertTrue(self.window.select_all_action.isEnabled())
                self.press(field)
                self.assertEqual(field.selectedText(), 'file')
                self.assertEqual(self.selected(self.left), [])

    def test_inline_rename_selects_the_text_without_selecting_other_files(self):
        view = self.focus_view()
        index = next(self.window.proxy.index(row, 0)
                     for row in range(self.window.proxy.rowCount())
                     if self.window.proxy.index(row, 0).data() == 'file-0.txt')
        view.setCurrentIndex(index)
        view.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        self.window.rename_f2()
        self.drain()
        editor = next((editor for editor in view.findChildren(QTextEdit) if editor.isVisible()), None)
        self.assertIsNotNone(editor)
        self.press(editor)
        self.assertEqual(editor.textCursor().selectedText(), 'file-0.txt')
        self.assertEqual(len(self.selected(self.left)), 1)
        QTest.keyClick(editor, Qt.Key_Escape)
        self.drain()

    def test_shortcut_is_enabled_after_loading_a_real_directory(self):
        directory = self.root / 'another-folder'
        directory.mkdir()
        for name in ('a.txt', 'b.txt'):
            (directory / name).write_text('temporary test content')
        self.window.navigate(str(directory))
        timer = QElapsedTimer()
        timer.start()
        while self.window.scanning and timer.elapsed() < 10000:
            QTest.qWait(10)
        self.drain()
        self.assertFalse(self.window.scanning)
        view = self.focus_view()
        view.clearSelection()
        self.press()
        self.assertEqual(set(self.selected(self.window.bound_pane)), {'a.txt', 'b.txt'})
