"""Real native header input must not trigger empty-background navigation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from mirivue.app import Window
from mirivue.metadata import basic_entry


class TestHeaderDoubleClick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-header-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root/'settings.ini'), QSettings.IniFormat)
        settings.setValue('navigation/empty-double-click-up', True)
        settings.setValue('media/start-preview-panel', False)
        with patch('mirivue.app.mirivue_settings', return_value=settings):
            self.window = Window()
        self.window.show()
        self.window.folder = self.window.bound_pane.folder = str(self.root)
        path = self.root/'fichier.txt'
        path.write_text('test')
        self.window.model.clear()
        self.window.model.add(basic_entry(path))
        self.window.content_stack.setCurrentIndex(0)
        for column in range(self.window.model.columnCount()):
            self.window.table.setColumnHidden(column, column not in (0, 1))
        self.window.set_pane_fill_view_width(self.window.bound_pane, False)
        self.window.set_pane_column_width_mode(self.window.bound_pane, 'custom')
        self.window.table.horizontalHeader().resizeSection(0, 350)
        self.window.table.horizontalHeader().resizeSection(1, 180)
        self.drain()

    def tearDown(self):
        self.window.quit_requested = True
        self.window.close()
        self.drain()

    def drain(self):
        for _ in range(5):
            self.app.processEvents()

    def double_click(self, view, point):
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseRelease(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.drain()

    def test_header_title_keeps_sorting_without_navigating(self):
        view = self.window.table
        point = QPoint(40, 8)
        self.assertFalse(view.indexAt(point).isValid())
        self.assertFalse(view.is_view_background(point))
        with patch.object(self.window, 'navigate') as navigate:
            initial = view.horizontalHeader().sortIndicatorOrder()
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
            self.drain()
            self.assertNotEqual(view.horizontalHeader().sortIndicatorOrder(), initial)
            self.double_click(view, point)
            navigate.assert_not_called()

    def test_header_grip_autosizes_without_navigating(self):
        view = self.window.table
        width = view._backend.query(op='widths')['widths'][0]
        self.assertGreater(width, 300)
        with patch.object(self.window, 'navigate') as navigate:
            self.double_click(view, QPoint(round(width), 8))
            navigate.assert_not_called()
        resized = view._backend.query(op='widths')['widths'][0]
        self.assertLess(resized, width)
        self.assertEqual(view.horizontalHeader().sectionSize(0), round(resized))

    def test_real_background_still_navigates_only_when_enabled_in_each_view(self):
        window = self.window
        for mode in (0, 1, 2):
            with self.subTest(mode=mode):
                window.change_view(mode)
                self.drain()
                view = window.active_view()
                point = QPoint(view.viewport().width() - 20, view.viewport().height() - 25)
                self.assertTrue(view.is_view_background(point))
                with patch.object(window, 'navigate') as navigate:
                    window.settings.setValue('navigation/empty-double-click-up', False)
                    self.double_click(view, point)
                    navigate.assert_not_called()
                    window.settings.setValue('navigation/empty-double-click-up', True)
                    self.double_click(view, point)
                    navigate.assert_called_once_with(str(self.root.parent))
