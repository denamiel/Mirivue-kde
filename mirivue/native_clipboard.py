# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Async public KIO::paste adapter; all clipboard access stays on the GUI thread."""
import ctypes
import json
import shiboken6
from PySide6.QtCore import QObject, QTimer, Signal, QUrl
from PySide6.QtWidgets import QMessageBox
from .native_desktop_dialogs import load
from .i18n import tr
from .platform_services import services

def can_paste_contents():
    try:
        library = load()
        library.mirivue_clipboard_can_paste.restype = ctypes.c_int
        return bool(library.mirivue_clipboard_can_paste())
    except (OSError, AttributeError):
        return False

_recorded_serials = set()

def history_serial():
    library = load()
    library.mirivue_clipboard_history_serial.restype = ctypes.c_ulonglong
    return library.mirivue_clipboard_history_serial()

class ClipboardOperation(QObject):
    completed = Signal(object)

    def __init__(self, window, destination='', history=0):
        super().__init__(window)
        self.cancelled = False
        self.library = load()
        self.library.mirivue_clipboard_start.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.library.mirivue_clipboard_start.restype = ctypes.c_void_p
        self.library.mirivue_clipboard_status.argtypes = [ctypes.c_void_p]
        self.library.mirivue_clipboard_status.restype = ctypes.c_char_p
        for name in ('cancel', 'release'):
            getattr(self.library, 'mirivue_clipboard_' + name).argtypes = [ctypes.c_void_p]
        self.pointer = self.library.mirivue_clipboard_start(
            shiboken6.getCppPointer(window)[0], str(destination).encode(), history)
        if not self.pointer:
            raise OSError(tr('Cette opération native n’est pas disponible.'))
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def cancel(self):
        self.cancelled = True
        if self.pointer:
            self.library.mirivue_clipboard_cancel(self.pointer)

    def poll(self):
        result = json.loads(self.library.mirivue_clipboard_status(self.pointer))
        if not result['done']:
            return
        self.timer.stop()
        self.library.mirivue_clipboard_release(self.pointer)
        self.pointer = None
        self.completed.emit(result)
        self.deleteLater()

class NativeClipboardMixin:
    def record_main_kio_history(self):
        serial = history_serial()
        if not serial or serial in _recorded_serials:
            return
        _recorded_serials.add(serial)
        self.file_undo_history().append(('main-kio', serial))
        self._file_redo_history = []
        self.update_kio_undo_action(services._kio_undo_available)
        self.update_kio_redo_action(services._kio_redo_available)

    def paste_clipboard_content(self, destination, mime):
        if (getattr(self, '_native_clipboard_operation', None) is not None
                or getattr(self, '_native_history_operation', None) is not None):
            return
        if self.transfers_locked([destination]):
            self.show_activity_message(tr('Attendez la fin du transfert vers ce dossier.'), 5000)
            return
        target = QUrl.fromLocalFile(str(destination)).toString()
        try:
            operation = ClipboardOperation(self, target)
        except (OSError, AttributeError) as error:
            QMessageBox.warning(self, tr('Collage indisponible'), str(error))
            return
        self._native_clipboard_operation = operation
        job = self.register_kio_transfer(operation, [], target, 'paste', tr('Collage du presse-papiers'))

        def complete(result):
            self._native_clipboard_operation = None
            ok, cancelled = result['ok'], result['cancelled']
            job['sources'] = result['items']
            message = (tr('Collage terminé.') if ok else tr('Collage annulé.') if cancelled
                       else result['error'] or tr('Le collage a échoué.'))
            self.finish_kio_transfer(job, ok, message, cancelled)
            if ok and result['items']:
                self.record_main_kio_history()
                self.remember_transfer_selection(result['items'], target, 'copy')
            self.refresh_kio_panes()
            self.show_activity_message(message, 5000 if ok or cancelled else 15000)
        operation.completed.connect(complete)

    def apply_main_kio_history(self, undo):
        if getattr(self, '_native_history_operation', None) is not None or self.pending_transfers():
            return
        source = self.file_undo_history() if undo else self.file_redo_history()
        if not source or source[-1][0] != 'main-kio':
            return
        entry = source[-1]
        try:
            if undo and history_serial() != entry[1]:
                raise OSError(tr('L’historique natif a changé. Cette opération ne peut pas être annulée depuis cette fenêtre.'))
            operation = ClipboardOperation(self, history=1 if undo else 2)
        except (OSError, AttributeError) as error:
            QMessageBox.warning(self, tr('Opération indisponible'), str(error))
            return
        self._native_history_operation = operation
        # Keep the window alive until the native history job finishes too.
        job = self.register_kio_transfer(operation, [], '', 'history', tr('Annuler') if undo else tr('Rétablir'))
        job['cancellable'] = False
        def complete(result):
            self._native_history_operation = None
            self.finish_kio_transfer(job, result['ok'], result['error'], result['cancelled'])
            if source and source[-1] is entry:
                source.pop()  # KIO consumes the command even if its undo fails.
                if result['ok']:
                    (self.file_redo_history() if undo else self.file_undo_history()).append(entry)
            self.refresh_kio_panes()
            self.update_kio_undo_action(services._kio_undo_available)
            self.update_kio_redo_action(services._kio_redo_available)
        operation.completed.connect(complete)
