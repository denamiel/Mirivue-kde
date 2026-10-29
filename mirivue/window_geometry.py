"""Restore the main window inside the available desktop area."""

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QGuiApplication


def initial_window_size():
    screen = QGuiApplication.primaryScreen()
    if screen is None or QGuiApplication.platformName() == 'offscreen':
        return 1500, 800
    available = screen.availableGeometry()
    return min(1500, available.width()), min(800, available.height())


def restore_window_geometry(window):
    saved = window.settings.value('window/geometry')
    if isinstance(saved, (QByteArray, bytes)) and saved:
        window.restoreGeometry(QByteArray(saved))


def geometry_to_save(window):
    """Keep the normal geometry when a media preview owns fullscreen mode."""
    if getattr(window, '_preview_fullscreen', False):
        saved = getattr(window, '_preview_window_geometry', None)
        if isinstance(saved, (QByteArray, bytes)) and saved:
            return QByteArray(saved)
    return window.saveGeometry()
