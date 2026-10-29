"""Disposable Qt window used only on the test's private D-Bus."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
from mirivue.app import Window
from mirivue.window_instances import register_window

app = QApplication(['Mirivue-test-peer', '--new-window'])
root, folder, output = map(Path, sys.argv[1:4])
settings = QSettings(str(output.with_suffix('.ini')), QSettings.Format.IniFormat)
settings.setValue('startup/allow_multiple_instances', True)
settings.setValue('window/confirm-close-multiple-tabs', False)
with patch('mirivue.app.mirivue_settings', return_value=settings):
    window = Window()
window.prepare_startup_browsing(str(folder))
records = []

def write():
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(tabs=len(window._tabs), records=records)))
    temporary.replace(output)

def activate(token=''):
    records.append(dict(event='activate', token=token))
    write()

def spawn(requests, **options):
    records.append(dict(event='spawn', folders=[r.folder for r in requests], options=options))
    write()
    return True

window.restore_window = activate
window.open_requests_in_new_window = spawn
original = window.receive_launch_payload

def receive(payload):
    original(payload)
    records.append(dict(event='received'))
    write()

window.receive_launch_payload = receive
if not register_window(app, window):
    from PySide6.QtDBus import QDBusConnection
    bus=QDBusConnection.sessionBus()
    error=bus.lastError()
    raise RuntimeError('The disposable window could not register on the test bus: '
                       + 'connected='+str(bus.isConnected())+'; '+error.name()+': '+error.message())
write()
print('READY', flush=True)
QTimer.singleShot(15000, app.quit)
app.exec()
