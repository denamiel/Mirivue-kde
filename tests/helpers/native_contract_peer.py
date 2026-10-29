"""Real native widgets on offscreen Qt, with controlled configure latency."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QSettings
from mirivue.platform_services import services

services.initialize_icon_theme()
app = QApplication([])
# The platform was already selected as offscreen. Enable the real native
# adapters in this child only; this does NOT simulate a Wayland compositor.
os.environ['QT_QPA_PLATFORM'] = 'native-contract-fixture'
original_tool = services.tool_path
services.tool_path = lambda name: (os.environ['MIRIVUE_TEST_PLACES_LIBRARY']
                                  if name == 'libmirivue-kio-places-widget.so' else original_tool(name))
from mirivue.app import Window
from mirivue.ui_contract import check_native_places

mode = sys.argv[1]

class ConfigureWindow(Window):
    simulate = False
    initial_path = None

    def prepare_startup_browsing(self, explicit=None):
        assert explicit and Path(explicit).is_dir(), 'Contract sent an empty or invalid initial location'
        self.initial_path = explicit
        return super().prepare_startup_browsing(explicit)

    def resize(self, *args):
        if self.simulate and mode == 'refused' and args[0] < self.width():
            return
        if self.simulate and mode == 'delayed':
            QTimer.singleShot(40, self, lambda: super(ConfigureWindow, self).resize(*args))
        else:
            super().resize(*args)

with tempfile.TemporaryDirectory(prefix='mirivue-contract-settings-') as directory:
    settings = QSettings(str(Path(directory) / 'preferences.ini'), QSettings.Format.IniFormat)
    settings.setValue('window/confirm-close-multiple-tabs', False)
    with patch('mirivue.app.mirivue_settings', return_value=settings):
        window = ConfigureWindow()
    window.simulate = True
    if mode == 'refused':
        try:
            check_native_places(window, app)
        except RuntimeError as error:
            assert 'refuse de rétrécir' in str(error), str(error)
            assert 'minimum=' in str(error), str(error)
            print('PERSISTENT_REFUSAL_DETECTED', flush=True)
        else:
            raise AssertionError('A genuine refusal was accepted')
    else:
        check_native_places(window, app)
        assert window.initial_path
        print('NATIVE_CONTRACT_PASSED', flush=True)
