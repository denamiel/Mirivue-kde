# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Real KShortcutsDialog, with effective keys persisted only in Mirivue's settings."""
import ctypes
import json
import shiboken6
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMessageBox
from .i18n import tr
from .native_desktop_dialogs import load


def create_dialog(window):
    library=load()
    notify_type=ctypes.CFUNCTYPE(None,ctypes.c_char_p)
    create=library.mirivue_shortcuts_create
    create.argtypes=[ctypes.c_void_p,ctypes.c_char_p,notify_type];create.restype=ctypes.c_void_p
    values=library.mirivue_shortcuts_values
    values.argtypes=[ctypes.c_void_p];values.restype=ctypes.c_char_p
    defaults=library.mirivue_shortcuts_defaults
    defaults.argtypes=[ctypes.c_void_p];defaults.restype=None
    show=library.mirivue_shortcuts_show
    show.argtypes=[ctypes.c_void_p];show.restype=None

    def apply(data):
        snapshot={binding['id']:(window.settings.contains('shortcuts/'+binding['id']),
                                window.settings.value('shortcuts/'+binding['id'])) for binding in window.shortcut_bindings}
        try:
            decoded=json.loads(data)
            known={b['id']:b for b in window.shortcut_bindings}
            if not isinstance(decoded,dict) or set(decoded)!=set(known): raise ValueError('Liste de commandes invalide.')
            if any(not isinstance(keys,list) or not all(isinstance(key,str) for key in keys) for keys in decoded.values()):
                raise ValueError('Raccourcis invalides.')
            changed={identifier:keys for identifier,keys in decoded.items() if keys!=known[identifier].get('sequences',[])}
            if changed:window.apply_shortcut_bindings(changed)
            if window.settings.status()!=QSettings.Status.NoError:raise OSError('Les raccourcis n’ont pas pu être enregistrés.')
            return True
        except Exception as error:
            for identifier,(present,value) in snapshot.items():
                if present:window.settings.setValue('shortcuts/'+identifier,value)
                else:window.settings.remove('shortcuts/'+identifier)
            window.settings.sync()
            try:window.apply_shortcut_bindings()
            except Exception:pass
            QMessageBox.warning(window,tr('Raccourcis non enregistrés'),str(error))
            return False
    callback=notify_type(lambda data: apply(data))
    payload=[dict(id=b['id'],title=b['title'],defaults=b.get('defaults',[b['default']]),
                  sequences=b.get('sequences',[])) for b in window.shortcut_bindings]
    pointer=create(shiboken6.getCppPointer(window)[0],json.dumps(payload,ensure_ascii=False).encode(),callback)
    if not pointer:raise RuntimeError('Le dialogue KDE des raccourcis n’a pas pu être créé.')
    dialog=shiboken6.wrapInstance(pointer,QDialog)
    # Keep the C callback and library alive for the entire modeless dialog lifetime.
    dialog._native_callback=callback;dialog._native_library=library
    dialog.restore_defaults=lambda:defaults(pointer)
    dialog.apply=lambda:apply(values(pointer))
    dialog.show_native=lambda:show(pointer)
    return dialog
