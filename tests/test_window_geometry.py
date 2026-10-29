"""The saved main-window state survives a new window on the same Qt desktop."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(subprocess.run([sys.executable, '-c', 'import PySide6'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0,
                     'PySide6 absent de cet environnement')
class TestWindowGeometry(unittest.TestCase):
    def test_geometry_is_restored_from_settings(self):
        script = '''
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QWidget
from mirivue.window_geometry import restore_window_geometry
import sys
app = QApplication([])
settings = QSettings(sys.argv[1], QSettings.Format.IniFormat)
first = QWidget()
first.resize(780, 520)
settings.setValue('window/geometry', first.saveGeometry())
second = QWidget()
second.settings = settings
restore_window_geometry(second)
assert second.size() == first.size(), (second.size(), first.size())
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c', script, str(Path(directory) / 'window.ini')],
                                    cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fullscreen_preview_restores_the_previous_window_geometry(self):
        script = '''
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QWidget
from mirivue.window_geometry import geometry_to_save, restore_window_geometry
import sys
app = QApplication([])
settings = QSettings(sys.argv[1], QSettings.Format.IniFormat)
first = QWidget()
first.resize(780, 520)
first.show()
app.processEvents()
first._preview_window_geometry = first.saveGeometry()
first._preview_fullscreen = True
first.showFullScreen()
app.processEvents()
assert first.isFullScreen()
settings.setValue('window/geometry', geometry_to_save(first))
second = QWidget()
second.settings = settings
restore_window_geometry(second)
second.show()
app.processEvents()
assert not second.isFullScreen(), 'La fenêtre rouvre en plein écran'
assert (second.width(), second.height()) == (780, 520), second.size()
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-c', script, str(Path(directory) / 'window.ini')],
                                    cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
