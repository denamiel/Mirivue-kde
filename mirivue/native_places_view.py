"""In-process adapter for KDE's own KFilePlacesView widget."""

import ctypes
import os
import json

import shiboken6
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QWidget, QToolBar, QMenu

from .platform_services import services
from .i18n import tr


def create_native_service_menu(parent_menu, window, paths):
    """Attach KF6 service menus and file action plugins to the popup lifetime."""
    library_path = services.tool_path('libmirivue-kio-places-widget.so')
    if not library_path or os.environ.get('QT_QPA_PLATFORM', '').casefold() in {'offscreen', 'minimal'}:
        return None
    library = ctypes.CDLL(library_path)
    library.mirivue_service_actions_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
    library.mirivue_service_actions_create.restype = ctypes.c_void_p
    urls = [value if '://' in value else QUrl.fromLocalFile(value).toString() for value in map(str, paths)]
    pointer = library.mirivue_service_actions_create(
        shiboken6.getCppPointer(parent_menu)[0], shiboken6.getCppPointer(window)[0],
        json.dumps(urls).encode('utf-8'))
    if not pointer:
        return None
    menu = shiboken6.wrapInstance(pointer, QMenu)
    menu._mirivue_library = library
    menu.setTitle(tr('Actions KDE'))
    return menu


class NativeTerminal:
    """Host KonsolePart in Mirivue's Qt window through the KF6 bridge."""

    def __init__(self, parent, directory_changed):
        library_path = services.tool_path('libmirivue-kio-places-widget.so')
        if not library_path or os.environ.get('QT_QPA_PLATFORM', '').casefold() in {'offscreen', 'minimal'}:
            raise RuntimeError('KonsolePart est indisponible dans cette session.')
        self.library = ctypes.CDLL(library_path)
        self.callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

        def changed(raw):
            try:
                path = raw.decode('utf-8')
                QTimer.singleShot(0, lambda: directory_changed(path))
            except (UnicodeError, RuntimeError):
                return

        self.callback = self.callback_type(changed)
        self.library.mirivue_terminal_create.argtypes = [ctypes.c_void_p, self.callback_type]
        self.library.mirivue_terminal_create.restype = ctypes.c_void_p
        self.library.mirivue_terminal_set_directory.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.library.mirivue_terminal_focus.argtypes = [ctypes.c_void_p]
        self.pointer = self.library.mirivue_terminal_create(shiboken6.getCppPointer(parent)[0], self.callback)
        if not self.pointer:
            raise RuntimeError('Le panneau Terminal KDE n’a pas pu être créé.')
        self.widget = shiboken6.wrapInstance(self.pointer, QWidget)
        self.widget._mirivue_terminal = self

    def set_directory(self, path):
        self.library.mirivue_terminal_set_directory(self.pointer, os.fsencode(path))

    def focus(self):
        self.library.mirivue_terminal_focus(self.pointer)


def create_native_toolbar(parent):
    """Give the window the same KF6 main toolbar class used by Dolphin."""
    library_path = services.tool_path('libmirivue-kio-places-widget.so')
    if not library_path or os.environ.get('QT_QPA_PLATFORM', '').casefold() in {'offscreen', 'minimal'}:
        return QToolBar(parent)
    library = ctypes.CDLL(library_path)
    library.mirivue_toolbar_create.argtypes = [ctypes.c_void_p]
    library.mirivue_toolbar_create.restype = ctypes.c_void_p
    pointer = library.mirivue_toolbar_create(shiboken6.getCppPointer(parent)[0])
    if not pointer:
        raise RuntimeError('KToolBar could not be created')
    toolbar = shiboken6.wrapInstance(pointer, QToolBar)
    toolbar._mirivue_library = library
    return toolbar


class NativePlacesView:
    def __init__(self, parent, activated, drop_completed, split_requested, tab_requested,
                 active_tab_requested, window_requested, error_reported,
                 trash_completed, trash_has_items):
        library_path = services.tool_path('libmirivue-kio-places-widget.so')
        if (services.name != 'linux' or not library_path
                or os.environ.get('QT_QPA_PLATFORM', '').casefold() in {'offscreen', 'minimal'}):
            raise RuntimeError('KFilePlacesView is unavailable in this session')
        self.library = ctypes.CDLL(library_path)
        self.callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
        self.trash_state_type = ctypes.CFUNCTYPE(ctypes.c_int)
        self.library.mirivue_places_create.argtypes = [ctypes.c_void_p, self.callback_type,
                                                        self.callback_type, self.callback_type,
                                                        self.callback_type, self.callback_type,
                                                        self.callback_type, self.callback_type,
                                                        self.callback_type, self.trash_state_type,
                                                        ctypes.c_char_p]
        self.library.mirivue_places_create.restype = ctypes.c_void_p
        self.library.mirivue_places_set_url.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.library.mirivue_places_set_url.restype = None
        self.library.mirivue_places_location_identity.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.library.mirivue_places_location_identity.restype = ctypes.c_char_p
        self._activated = activated
        self._drop_completed = drop_completed
        self._split_requested = split_requested
        self._tab_requested = tab_requested
        self._active_tab_requested = active_tab_requested
        self._window_requested = window_requested
        self._error_reported = error_reported
        self._trash_completed = trash_completed
        self._trash_has_items = trash_has_items
        self._url = None

        def on_place(raw):
            try:
                url = raw.decode('utf-8')
                target = QUrl(url)
                location = target.toLocalFile() if target.isLocalFile() else url
                QTimer.singleShot(0, lambda: self._activated(location))
            except (UnicodeError, RuntimeError):
                return

        def on_drop(raw):
            if raw == b'completed':
                QTimer.singleShot(0, self._drop_completed)

        def on_split(raw):
            try:
                url = QUrl(raw.decode('utf-8'))
                location = url.toLocalFile() if url.isLocalFile() else url.toString()
                QTimer.singleShot(0, lambda: self._split_requested(location))
            except (UnicodeError, RuntimeError):
                return

        def on_error(raw):
            try:
                message = raw.decode('utf-8')
                if message:
                    QTimer.singleShot(0, lambda: self._error_reported(message))
            except (UnicodeError, RuntimeError):
                return

        def on_window(raw):
            try:
                url = QUrl(raw.decode('utf-8'))
                location = url.toLocalFile() if url.isLocalFile() else url.toString()
                QTimer.singleShot(0, lambda: self._window_requested(location))
            except (UnicodeError, RuntimeError):
                return

        def on_tab(raw, active):
            try:
                url = QUrl(raw.decode('utf-8'))
                location = url.toLocalFile() if url.isLocalFile() else url.toString()
                callback = self._active_tab_requested if active else self._tab_requested
                QTimer.singleShot(0, lambda: callback(location, active=active))
            except (UnicodeError, RuntimeError):
                return

        # Hold both callback objects until the Qt parent destroys the widget.
        self.place_callback = self.callback_type(on_place)
        self.drop_callback = self.callback_type(on_drop)
        self.split_callback = self.callback_type(on_split)
        self.tab_callback = self.callback_type(lambda raw: on_tab(raw, False))
        self.active_tab_callback = self.callback_type(lambda raw: on_tab(raw, True))
        self.window_callback = self.callback_type(on_window)
        self.error_callback = self.callback_type(on_error)
        self.trash_callback = self.callback_type(
            lambda raw: QTimer.singleShot(0, self._trash_completed)
            if raw == b'completed' else None)
        self.trash_state_callback = self.trash_state_type(
            lambda: int(self._trash_has_items()))
        self.pointer = self.library.mirivue_places_create(
            shiboken6.getCppPointer(parent)[0], self.place_callback, self.drop_callback,
            self.split_callback, self.tab_callback, self.active_tab_callback,
            self.window_callback, self.error_callback, self.trash_callback,
            self.trash_state_callback,
            tr('Ouvrir en vue scindée').encode('utf-8'))
        if not self.pointer:
            raise RuntimeError('KFilePlacesView could not be created')
        self.widget = shiboken6.wrapInstance(self.pointer, QWidget)

    def location_identity(self, location):
        raw = self.library.mirivue_places_location_identity(self.pointer, str(location or '').encode('utf-8'))
        if not raw:
            return None
        result = json.loads(raw.decode('utf-8'))
        return str(result['name']), str(result['icon'])

    def set_url(self, url):
        value = str(url or '')
        if value and value != self._url:
            self._url = value
            self.library.mirivue_places_set_url(self.pointer, value.encode('utf-8'))


class NativePathNavigator:
    """An actual KF6 KUrlNavigator sharing the sidebar's Places model."""

    def __init__(self, parent, places, location, changed, tab_requested, window_requested,
                 drop_completed, error_reported):
        self.library = places.library
        callback_type = places.callback_type
        self.library.mirivue_navigator_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_char_p, callback_type, callback_type, callback_type, callback_type,
            callback_type, callback_type]
        self.library.mirivue_navigator_create.restype = ctypes.c_void_p
        self.library.mirivue_navigator_set_url.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.library.mirivue_navigator_set_editable.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_is_editable.argtypes = [ctypes.c_void_p]
        self.library.mirivue_navigator_is_editable.restype = ctypes.c_int
        self.library.mirivue_navigator_set_active.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_set_split_mode.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_set_full_path.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_set_places_selector_visible.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_is_places_selector_visible.argtypes = [ctypes.c_void_p]
        self.library.mirivue_navigator_is_places_selector_visible.restype = ctypes.c_int
        self.library.mirivue_navigator_set_hidden_folders.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.mirivue_navigator_shows_hidden_folders.argtypes = [ctypes.c_void_p]
        self.library.mirivue_navigator_shows_hidden_folders.restype = ctypes.c_int
        self.library.mirivue_navigator_has_background.argtypes = [ctypes.c_void_p]
        self.library.mirivue_navigator_has_background.restype = ctypes.c_int

        def relay(callback, raw, active=None):
            try:
                url = QUrl(raw.decode('utf-8'))
                location_value = url.toLocalFile() if url.isLocalFile() else url.toString()
                if active is None:
                    QTimer.singleShot(0, lambda value=location_value: callback(value))
                else:
                    QTimer.singleShot(0, lambda value=location_value: callback(value, active=active))
            except (UnicodeError, RuntimeError):
                pass

        self.callbacks = (
            callback_type(lambda raw: relay(changed, raw)),
            callback_type(lambda raw: relay(tab_requested, raw, False)),
            callback_type(lambda raw: relay(tab_requested, raw, True)),
            callback_type(lambda raw: relay(window_requested, raw)),
            callback_type(lambda raw: QTimer.singleShot(0, drop_completed) if raw == b'completed' else None),
            callback_type(lambda raw: QTimer.singleShot(0, lambda: error_reported(raw.decode('utf-8')))),
        )
        self.pointer = self.library.mirivue_navigator_create(
            shiboken6.getCppPointer(parent)[0], places.pointer, str(location or '').encode('utf-8'),
            *self.callbacks)
        if not self.pointer:
            raise RuntimeError('KUrlNavigator could not be created')
        self.widget = shiboken6.wrapInstance(self.pointer, QWidget)

    def set_url(self, location):
        if location:
            self.library.mirivue_navigator_set_url(self.pointer, str(location).encode('utf-8'))

    def set_editable(self, editable):
        self.library.mirivue_navigator_set_editable(self.pointer, bool(editable))

    def is_editable(self):
        return bool(self.library.mirivue_navigator_is_editable(self.pointer))

    def set_active(self, active):
        self.library.mirivue_navigator_set_active(self.pointer, bool(active))

    def set_split_mode(self, split):
        self.library.mirivue_navigator_set_split_mode(self.pointer, bool(split))

    def set_full_path(self, enabled):
        self.library.mirivue_navigator_set_full_path(self.pointer, bool(enabled))

    def set_places_selector_visible(self, visible):
        self.library.mirivue_navigator_set_places_selector_visible(self.pointer, bool(visible))

    def is_places_selector_visible(self):
        return bool(self.library.mirivue_navigator_is_places_selector_visible(self.pointer))

    def set_hidden_folders(self, show):
        self.library.mirivue_navigator_set_hidden_folders(self.pointer, bool(show))

    def shows_hidden_folders(self):
        return bool(self.library.mirivue_navigator_shows_hidden_folders(self.pointer))

    def has_background(self):
        return bool(self.library.mirivue_navigator_has_background(self.pointer))
