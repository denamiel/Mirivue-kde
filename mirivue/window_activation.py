"""Activate with KDE's Wayland token support, as Dolphin does."""
import ctypes
import os
import shiboken6
from .platform_services import services


def activate_window(window, token=''):
    library_path = services.tool_path('libmirivue-kio-places-widget.so')
    if library_path and os.environ.get('QT_QPA_PLATFORM', '').casefold() not in {'offscreen', 'minimal'}:
        library = ctypes.CDLL(library_path)
        activate = library.mirivue_activate_window
        activate.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        activate.restype = None
        activate(shiboken6.getCppPointer(window)[0], token.encode('utf-8'))
        window._activation_library = library
    else:
        window.activateWindow()
