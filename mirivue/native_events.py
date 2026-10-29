"""Native event masks keep drawing/layout notifications out of Python."""
import ctypes
import json
import traceback

import shiboken6
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import (QKeyEvent, QMouseEvent, QWheelEvent, QContextMenuEvent,
                           QResizeEvent, QFocusEvent)
from .dolphin_view import _load, _pointer

_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
_EVENT_CLASSES = {
    QEvent.Type.KeyPress: QKeyEvent,
    QEvent.Type.KeyRelease: QKeyEvent,
    QEvent.Type.ShortcutOverride: QKeyEvent,
    QEvent.Type.MouseButtonPress: QMouseEvent,
    QEvent.Type.MouseButtonRelease: QMouseEvent,
    QEvent.Type.MouseButtonDblClick: QMouseEvent,
    QEvent.Type.MouseMove: QMouseEvent,
    QEvent.Type.Wheel: QWheelEvent,
    QEvent.Type.ContextMenu: QContextMenuEvent,
    QEvent.Type.Resize: QResizeEvent,
    QEvent.Type.FocusIn: QFocusEvent,
}


def install_event_gate(target, owner, event_types):
    library = _load()
    function = library.mirivue_event_gate_create
    function.argtypes = [ctypes.c_void_p, ctypes.c_void_p, _CALLBACK, ctypes.c_char_p]
    function.restype = ctypes.c_void_p
    def forward(watched, event, kind):
        if not shiboken6.isValid(owner):
            return 0
        try:
            watched = shiboken6.wrapInstance(watched, QObject)
            event = shiboken6.wrapInstance(event, _EVENT_CLASSES.get(QEvent.Type(kind), QEvent))
            return int(bool(owner.eventFilter(watched, event)))
        except Exception:
            traceback.print_exc()
            return 0
    callback = _CALLBACK(forward)
    pointer = function(_pointer(target), _pointer(owner), callback,
                       json.dumps([kind.value for kind in event_types]).encode())
    gate = shiboken6.wrapInstance(pointer, QObject)
    gate._mirivue_callback = callback
    gate._mirivue_library = library
    if not hasattr(owner, '_native_event_gates'):
        owner._native_event_gates = []
    owner._native_event_gates.append(gate)
    return gate
