"""Folder display preferences survive navigation and a fresh Qt window."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication, QStyleOptionViewItem
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class TestFolderDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication(['Mirivue-test'])

    def wait_for_listing(self, window):
        deadline = time.monotonic() + 5
        while window.scanning and time.monotonic() < deadline:
            self.application.processEvents()
        self.assertFalse(window.scanning)
        self.application.processEvents()

    def close_window(self, window):
        from PySide6.QtTest import QTest
        window.quit_requested = True
        window.close()
        deadline = time.monotonic() + 5
        while window.runtime_tasks.running() and time.monotonic() < deadline:
            QTest.qWait(5)
        self.application.processEvents()
        window.close()
        self.application.processEvents()
        self.assertFalse(window.runtime_tasks.running())

    def test_folder_sort_previews_hidden_and_icon_information(self):
        from mirivue.app import Window
        from mirivue.metadata import HEADERS

        with tempfile.TemporaryDirectory(prefix='mirivue-view-') as temporary:
            first, second = Path(temporary, 'first'), Path(temporary, 'second')
            first.mkdir()
            second.mkdir()
            (first / 'note.txt').write_text('test')
            settings = QSettings(str(Path(temporary, 'settings.ini')), QSettings.Format.IniFormat)
            settings.setValue('view/remember-per-folder', True)
            settings.setValue('view/hidden', False)
            settings.setValue('view/previews', False)
            # An explicit folder exception must survive changes to the default.
            settings.setValue('view/folder-styles-v1', {str(second): {'previews': False}})
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
                try:
                    window.prepare_startup_browsing(str(first))
                    self.wait_for_listing(window)
                    window.table.sortByColumn(1, Qt.SortOrder.DescendingOrder)
                    window.hidden.setChecked(True)
                    self.wait_for_listing(window)
                    window.preview_action.setChecked(True)
                    window.set_icon_extra_information(1, True)
                    index = window.proxy.index(0, 0)
                    window.content_stack.setCurrentIndex(1)
                    self.application.processEvents()
                    snapshot = window.icons._backend.query(op='item', row=0)
                    self.assertEqual(snapshot['cells'][1], index.siblingAtColumn(1).data())

                    window.navigate(str(second))
                    self.wait_for_listing(window)
                    self.assertFalse(window.hidden.isChecked())
                    self.assertFalse(window.model.show_thumbnails)
                    self.assertEqual(window.bound_pane.extra_columns, ())

                    window.navigate(str(first))
                    self.wait_for_listing(window)
                    self.assertEqual(window.table.horizontalHeader().sortIndicatorSection(), 1)
                    self.assertEqual(window.table.horizontalHeader().sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)
                    self.assertTrue(window.hidden.isChecked())
                    self.assertTrue(window.model.show_thumbnails)
                    self.assertEqual(window.bound_pane.extra_columns, (1,))
                finally:
                    self.close_window(window)
                settings.sync()

                reopened = Window()
                try:
                    reopened.prepare_startup_browsing(str(first))
                    self.wait_for_listing(reopened)
                    self.assertEqual(reopened.table.horizontalHeader().sortIndicatorSection(), 1)
                    self.assertTrue(reopened.hidden.isChecked())
                    self.assertTrue(reopened.model.show_thumbnails)
                    self.assertEqual(reopened.bound_pane.extra_columns, (1,))
                finally:
                    self.close_window(reopened)

    def test_toolbar_thumbnail_choice_becomes_default_and_survives_reopening(self):
        from mirivue.app import Window
        from PySide6.QtTest import QTest

        with tempfile.TemporaryDirectory(prefix='mirivue-preview-default-') as temporary:
            root = Path(temporary)
            folders = [root / name for name in ('first', 'second', 'third')]
            for folder in folders:
                folder.mkdir()
                (folder / 'note.txt').write_text('test')
            settings = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            settings.setValue('view/previews', False)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
                window.show()
                try:
                    window.prepare_startup_browsing(str(folders[0]))
                    self.wait_for_listing(window)
                    self.assertFalse(window.preview_action.isChecked())
                    QTest.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
                    self.assertTrue(window.model.show_thumbnails)
                    self.assertTrue(settings.value('view/previews', False, type=bool))
                    window.navigate(str(folders[1]))
                    self.wait_for_listing(window)
                    self.assertTrue(window.model.show_thumbnails)
                    self.close_window(window)
                    settings.sync()
                    window = Window()
                    window.show()
                    window.prepare_startup_browsing(str(folders[1]))
                    self.wait_for_listing(window)
                    for mode in (0, 1, 2):
                        window.change_view(mode)
                        self.application.processEvents()
                        self.assertTrue(window.model.show_thumbnails)
                        self.assertTrue(window.preview_button.isChecked())
                    QTest.mouseClick(window.preview_button, Qt.MouseButton.LeftButton)
                    self.assertFalse(settings.value('view/previews', True, type=bool))
                    window.navigate(str(folders[0]))
                    self.wait_for_listing(window)
                    # Restoring this folder's explicit True must not change
                    # the default False chosen in the second folder.
                    self.assertFalse(window.model.show_thumbnails)
                    self.assertFalse(settings.value('view/previews', True, type=bool))
                finally:
                    self.close_window(window)
                settings.sync()
                reopened = Window()
                try:
                    reopened.prepare_startup_browsing(str(folders[2]))
                    self.wait_for_listing(reopened)
                    self.assertFalse(reopened.model.show_thumbnails)
                    reopened.navigate(str(folders[0]))
                    self.wait_for_listing(reopened)
                    self.assertFalse(reopened.model.show_thumbnails)
                finally:
                    self.close_window(reopened)


if __name__ == '__main__':
    unittest.main()
