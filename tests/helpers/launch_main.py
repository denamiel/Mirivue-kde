"""Run the real application entry point and inspect its resulting views."""
import json
from pathlib import Path
import sys
import time
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
import mirivue.app as application

root = Path(sys.argv[1])
arguments, expected = json.loads(sys.argv[2]), json.loads(sys.argv[3])
settings = QSettings(str(root/'launch.ini'), QSettings.Format.IniFormat)
settings.setValue('help/first-use-seen', True)
settings.setValue('window/confirm-close-multiple-tabs', False)
application.mirivue_settings = lambda: settings
original = application.Window

def create():
    window = original()
    deadline = time.monotonic()+8
    def inspect():
        if any(p.scanning for tab in window._tabs for p in tab.panes):
            if time.monotonic()<deadline:
                QTimer.singleShot(10, inspect)
                return
            print('Listing timed out', file=sys.stderr)
            QApplication.instance().exit(2)
            return
        try:
            actual = [str(p.folder) for p in window.panes]
            assert actual == expected['folders'], (actual, expected)
            for pane, paths in zip(window.panes, expected.get('selected', [])):
                chosen = window.run_in_pane(pane, window.selected_entries)
                assert list(map(str, chosen)) == paths, (chosen, paths)
            print('LAUNCH_OK', flush=True)
            window.quit_requested = True
            window.close()
        except Exception:
            import traceback
            traceback.print_exc()
            QApplication.instance().exit(2)
    QTimer.singleShot(100, inspect)
    return window

application.Window = create
sys.argv = ['Mirivue', '--new-window', *arguments]
application.main()
