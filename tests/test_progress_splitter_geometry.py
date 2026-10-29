"""Progress text must not change either vertical splitter's position."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 indisponible')
class TestProgressSplitterGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication(['Mirivue-test'])

    def test_progress_updates_keep_places_and_split_panes_fixed(self):
        from mirivue.app import Window

        with TemporaryDirectory(prefix='mirivue-progress-') as root:
            settings = QSettings(str(Path(root, 'settings.ini')), QSettings.Format.IniFormat)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
            try:
                window.prepare_startup_browsing(root)
                window.set_split_view(True, navigate_new=False)
                window.show()
                self.application.processEvents()
                window.main_splitter.setSizes([240, 1000])
                window.pane_splitter.setSizes([500, 500])
                self.application.processEvents()
                self.application.processEvents()
                before = (window.main_splitter.sizes(), window.pane_splitter.sizes())
                for value in (1, 9, 10, 99, 100):
                    window.bar.setRange(0, 100)
                    window.bar.setFormat('Suppression définitive : %p%')
                    window.bar.setValue(value)
                    window.bar.show()
                    self.application.processEvents()
                    self.assertEqual((window.main_splitter.sizes(), window.pane_splitter.sizes()), before)
                window.bar.hide()
                self.application.processEvents()
                self.assertEqual((window.main_splitter.sizes(), window.pane_splitter.sizes()), before)
            finally:
                window.quit_requested = True
                window.close()


if __name__ == '__main__':
    unittest.main()
