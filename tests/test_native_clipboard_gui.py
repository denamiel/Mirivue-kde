"""Real KIO paste dialogs, payloads and chronological undo/redo in the GUI process."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, QTimer, QUrl
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QComboBox
from PySide6.QtTest import QTest
import test_dolphin_parity_gui as parity
from mirivue.platform_services import services

class TestNativeClipboardGui(parity.unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle

    def wait_for(self, predicate):
        end = time.monotonic() + 8
        while not predicate() and time.monotonic() < end:
            self.app.processEvents()
            QTest.qWait(10)
        self.assertTrue(predicate(), 'native clipboard job did not finish')

    def text(self, value='Été 日本 — Mirivue'):
        mime = QMimeData()
        mime.setText(value)
        self.app.clipboard().setMimeData(mime)
        return mime

    def dialogs(self, name=None, conflict='cancel', format=None, mutate=None):
        # The real KDE dialog is driven by Qt events, no KIO implementation is mocked.
        self.dialog_errors = []
        state = dict(named=False)
        timer = QTimer(self.window)
        def answer():
            modal = self.app.activeModalWidget()
            if not isinstance(modal, QDialog):
                return
            if not state['named']:
                edits = modal.findChildren(QLineEdit)
                if not edits:
                    return
                if name is None:
                    modal.reject()
                else:
                    edits[0].setText(name)
                    if format:
                        combos = modal.findChildren(QComboBox)
                        for combo in combos:
                            for index in range(combo.count()):
                                if format in combo.itemText(index).lower(): combo.setCurrentIndex(index)
                    if mutate: mutate()
                    modal.accept()
                state['named'] = True
            elif conflict == 'cancel':
                modal.reject()
            else:
                button = next((b for b in modal.findChildren(QPushButton)
                               if 'overwrite' in b.text().replace('&','').lower()), None)
                if button: button.click()
        timer.timeout.connect(answer)
        timer.start(20)
        self.addCleanup(timer.stop)
        return timer

    def paste(self, name='pasted.txt', **kwargs):
        timer = self.dialogs(name, **kwargs)
        destination = self.folders[0]
        self.assertTrue(self.window.paste_available(destination))
        self.window.active_view().setFocus()
        self.window.paste_selection(destination)
        self.wait_for(lambda: self.window._native_clipboard_operation is None)
        timer.stop()
        return destination/name if name else destination

    def test_text_unicode_and_native_undo_redo(self):
        self.text()
        path = self.paste()
        self.assertEqual(path.read_text(), 'Été 日本 — Mirivue')
        self.assertEqual(self.window.file_undo_history()[-1][0], 'main-kio')
        self.window.undo_remote_transfer()
        self.wait_for(lambda: self.window._native_history_operation is None)
        self.assertFalse(path.exists())
        self.window.redo_kio_operation()
        self.wait_for(lambda: self.window._native_history_operation is None)
        self.assertEqual(path.read_text(), 'Été 日本 — Mirivue')

    def test_cancel_filename_creates_nothing(self):
        self.text()
        before = set(self.folders[0].iterdir())
        self.paste(None)
        self.assertEqual(set(self.folders[0].iterdir()), before)
        self.assertFalse(self.window.file_undo_history())

    def test_cancel_conflict_preserves_existing_bytes(self):
        target = self.folders[0]/'existing.txt'
        target.write_bytes(b'keep')
        self.text('replacement')
        self.paste('existing.txt')
        self.assertEqual(target.read_bytes(), b'keep')

    def test_explicit_overwrite_uses_native_confirmation(self):
        target = self.folders[0]/'existing.txt'
        target.write_bytes(b'old')
        self.text('new')
        self.paste('existing.txt', conflict='overwrite')
        self.assertEqual(target.read_text(), 'new')

    def test_png_payload_and_selection(self):
        image = QImage(4, 3, QImage.Format_ARGB32)
        image.fill(QColor('red'))
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        self.assertTrue(image.save(buffer, 'PNG'))
        mime = QMimeData()
        mime.setData('image/png', buffer.data())
        self.app.clipboard().setMimeData(mime)
        path = self.paste('image.png')
        copied = QImage(str(path))
        self.assertEqual(copied.size(), image.size())
        self.assertEqual(copied.pixelColor(0,0), QColor('red'))
        self.settle()
        self.wait_for(lambda: path in self.window.selected_entries())

    def test_image_format_choice_preserves_selected_jpeg_format(self):
        image = QImage(4, 3, QImage.Format_RGB32)
        image.fill(QColor('red'))
        mime = QMimeData()
        for format in ('PNG', 'JPEG'):
            buffer = QBuffer()
            buffer.open(QIODevice.WriteOnly)
            self.assertTrue(image.save(buffer, format))
            mime.setData('image/' + format.lower(), buffer.data())
        self.app.clipboard().setMimeData(mime)
        path = self.paste('chosen.jpg', format='jpeg')
        self.assertTrue(path.read_bytes().startswith(bytes.fromhex('ffd8')))
        self.assertEqual(QImage(str(path)).size(), image.size())

    def test_clipboard_change_during_format_dialog_is_handled_natively(self):
        mime = QMimeData()
        mime.setData('application/octet-stream', QByteArray(b'original'))
        mime.setData('image/png', QByteArray(b'original png'))
        self.app.clipboard().setMimeData(mime)
        path = self.paste('changed.bin', mutate=lambda: self.text('different'))
        self.assertFalse(path.exists())

    def test_native_and_service_history_stay_in_order(self):
        # Actual service KIO job follows the in-process clipboard job.
        self.text('pasted')
        pasted = self.paste('first.txt')
        origin = self.folders[1]/'service.txt'
        origin.write_text('service')
        worker = self.window.start_kio_transfer([origin.as_uri()], self.folders[0].as_uri())
        self.assertIsNotNone(worker)
        self.wait_for(lambda: not self.window.pending_transfers())
        self.assertEqual([entry[0] for entry in self.window.file_undo_history()], ['main-kio','kio'])
        self.window.undo_remote_transfer()
        self.wait_for(lambda: self.window.kio_undo_worker is None)
        self.assertFalse((self.folders[0]/'service.txt').exists())
        self.assertTrue(pasted.exists())
        self.window.undo_remote_transfer()
        self.wait_for(lambda: self.window._native_history_operation is None)
        self.assertFalse(pasted.exists())
