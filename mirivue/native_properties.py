# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Public KDE properties dialog; permission changes belong to KIO."""
import ctypes
import json
from pathlib import Path
import shiboken6
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QDialog, QMessageBox
from .native_desktop_dialogs import load
from .locations import Location
from .i18n import tr


def has_media_companion(path):
    from .media import companion, AUDIO_EXT, IMAGE_EXT
    from .metadata import EXTENSIONS
    path = Path(path)
    return path.suffix.lower() in EXTENSIONS | AUDIO_EXT | IMAGE_EXT and companion(path).is_file()


def show_properties(window, paths):
    urls = [Location.from_value(path).uri for path in paths]
    readonly_name = any(not Location.from_value(path).is_uri and has_media_companion(path) for path in paths)
    library = load()
    callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
    def changed(raw):
        payload = json.loads(raw.decode('utf-8'))
        QTimer.singleShot(0, lambda: reconcile_properties(window, payload))
    callback = callback_type(changed)
    library.mirivue_properties_create.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, callback_type]
    library.mirivue_properties_create.restype = ctypes.c_void_p
    pointer = library.mirivue_properties_create(shiboken6.getCppPointer(window)[0],
        json.dumps(urls).encode(), readonly_name, callback)
    if not pointer:
        raise OSError(tr('Les propriétés KDE ne sont pas disponibles pour cette sélection.'))
    dialog = shiboken6.wrapInstance(pointer, QDialog)
    dialog._mirivue_library = library
    dialog._mirivue_callback = callback
    dialogs = getattr(window, '_native_properties_dialogs', [])
    window._native_properties_dialogs = dialogs
    dialogs.append(dialog)
    dialog.destroyed.connect(lambda: dialogs.remove(dialog) if dialog in dialogs else None)
    return dialog


def reconcile_properties(window, payload):
    if window.closing:
        return
    renamed = {}
    for pair in payload.get('renamed', []):
        source, target = QUrl(pair['source']), QUrl(pair['target'])
        if source.isLocalFile() and target.isLocalFile():
            renamed[Path(source.toLocalFile())] = Path(target.toLocalFile())
    if renamed:
        panes = [pane for tab in window._tabs for pane in tab.panes]
        for pane in panes:
            if any(row.path in renamed for row in pane.model.rows):
                window.run_in_pane_silent(pane, lambda: window.update_renamed_rows(renamed, reset=False))
            if pane.folder and not Location.from_value(pane.folder).is_uri:
                folder = Path(pane.folder)
                for source, target in renamed.items():
                    if folder == source or source in folder.parents:
                        window.run_in_pane(pane, window.navigate, str(target / folder.relative_to(source)))
                        break
    window.refresh_kio_panes()
    window.watch_visible_directories()
