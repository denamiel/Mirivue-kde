# SPDX-License-Identifier: MIT
"""Capture the KWin workspace through org.kde.KWin.ScreenShot2 into a PNG.

Usage: kwin_screenshot.py OUTPUT.png
Runs on the session bus given by DBUS_SESSION_BUS_ADDRESS. KWin writes the raw
image into a pipe and returns its geometry and QImage format. The disposable
KWin runs with KWIN_WAYLAND_NO_PERMISSION_CHECKS=1, so no desktop-file
authorization is needed. PySide6 is already a dependency of Mirivue.
"""
import os
import sys
import threading

from PySide6.QtCore import QCoreApplication
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage, QDBusUnixFileDescriptor
from PySide6.QtGui import QImage


def main(output):
    QCoreApplication(['kwin-screenshot'])
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        sys.exit('Bus de session indisponible.')
    reader, writer = os.pipe()
    chunks = []

    def drain():
        while True:
            data = os.read(reader, 1 << 20)
            if not data:
                break
            chunks.append(data)
    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    interface = QDBusInterface('org.kde.KWin.ScreenShot2', '/org/kde/KWin/ScreenShot2',
                               'org.kde.KWin.ScreenShot2', bus)
    interface.setTimeout(20000)
    reply = interface.call('CaptureWorkspace', {'native-resolution': True}, QDBusUnixFileDescriptor(writer))
    os.close(writer)
    if reply.type() == QDBusMessage.MessageType.ErrorMessage:
        sys.exit(f'ScreenShot2 : {reply.errorName()} {reply.errorMessage()}')
    thread.join(20)
    os.close(reader)
    metadata = reply.arguments()[0]
    data = b''.join(chunks)
    image = QImage(data, int(metadata['width']), int(metadata['height']), int(metadata['stride']),
                   QImage.Format(int(metadata['format'])))
    if image.isNull() or not image.copy().save(output, 'PNG'):
        sys.exit('Image ScreenShot2 invalide.')
    print(f"{metadata['width']}x{metadata['height']}")


if __name__ == '__main__':
    main(sys.argv[1])
