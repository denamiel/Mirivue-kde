"""KIO owns transfer progress; each operation keeps its own cancellation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject, Signal, QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QTreeWidget, QMessageBox
from mirivue.app import Window
from mirivue.metadata import basic_entry
from mirivue.platform_services import services


class ControlledTransfer(QObject):
    progress = Signal(int)
    completed = Signal(bool, str)
    finished = Signal()

    def __init__(self, sources, destination, move=False, operation=None):
        super().__init__()
        self.sources, self.destination = list(sources), destination
        self.operation = operation or ('move' if move else 'copy')
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class TestKioProgressRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-progress-')
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root/'settings.ini'), QSettings.IniFormat)
        with patch('mirivue.app.mirivue_settings', return_value=settings):
            self.window = Window()
        self.window.show()
        self.workers = []
        original_start = self.window.start_runtime_worker
        def start(worker, *args, **kwargs):
            if isinstance(worker, ControlledTransfer):
                worker.setParent(self.window)
                self.workers.append(worker)
            else:
                return original_start(worker, *args, **kwargs)
        original_tool = services.tool_path
        for substitute in (
            patch('mirivue.movement.KioTransferWorker', ControlledTransfer),
            patch.object(self.window, 'start_runtime_worker', side_effect=start),
            patch.object(services, 'tool_path', side_effect=lambda name:
                         '/test/kio-service' if name == 'mirivue-kio-service' else original_tool(name)),
            patch.object(self.window, 'record_kio_history'),
            patch.object(self.window, 'refresh_kio_panes'),
            patch.object(self.window, 'update_local_kio_transfer', return_value=True),
        ):
            substitute.start()
            self.addCleanup(substitute.stop)
        self.drain()

    def tearDown(self):
        w = self.window
        for worker in tuple(w.kio_transfer_workers()):
            worker.completed.emit(False, 'Transfert annulé.')
        w.active_job = None
        w.job_queue = []
        w.quit_requested = w.closing = True
        w.close()
        self.drain()
        self.temporary.cleanup()

    def drain(self):
        for _ in range(5):
            self.app.processEvents()

    def start(self, name='first', operation='copy', on_success=None):
        return self.window.start_kio_transfer(
            [f'smb://example.invalid/source/{name}'], 'smb://example.invalid/destination',
            operation=operation, on_success=on_success)

    def test_two_transfers_keep_loading_progress_and_stop_state_untouched(self):
        w = self.window
        w.stop.setEnabled(True)
        w.stop.setText('Arrêter le chargement du dossier')
        w.bar.setRange(0, 100)
        w.bar.setValue(17)
        w.bar.show()
        first, second = self.start(), self.start('second')
        first.progress.emit(20)
        second.progress.emit(70)
        self.assertEqual(w.bar.value(), 17)
        first.completed.emit(True, '')
        self.assertTrue(w.bar.isVisible())
        self.assertEqual(w.kio_transfer_workers(), [second])
        self.assertTrue(w.stop.isEnabled())
        self.assertEqual(w.stop.text(), 'Arrêter le chargement du dossier')
        second.completed.emit(True, '')
        self.assertTrue(w.bar.isVisible())
        self.assertTrue(w.stop.isEnabled())
        self.assertIsNone(w.kio_transfer_worker)

    def test_native_transfers_have_no_internal_progress_bar_and_remain_accessible(self):
        w = self.window
        worker = self.start()
        worker.progress.emit(65)
        self.drain()
        self.assertTrue(w.bar.isHidden())
        self.assertTrue(w.transfer_bar.isHidden())
        self.assertTrue(w.job_button.isVisible())
        self.assertTrue(w.jobs_action.isEnabled())
        w.sidebar.hide()
        w.update_activity_entry_points()
        self.assertTrue(w.job_button.isHidden())
        self.assertTrue(w.activity_fallback_button.isVisible())
        worker.completed.emit(True, '')
        self.assertTrue(w.job_button.isHidden())
        self.assertTrue(w.activity_fallback_button.isHidden())
        self.assertTrue(w.jobs_action.isEnabled())  # History remains available.

    def test_cancel_selected_transfer_does_not_cancel_another(self):
        w = self.window
        first, second = self.start(), self.start('second')
        page = w.create_transfers_page(w)
        page.resize(900, 450)
        page.show()
        self.drain()
        tree = page.findChild(QTreeWidget)
        tree.setCurrentItem(tree.topLevelItem(0))
        button = next(b for b in page.findChildren(QPushButton)
                      if b.text() == 'Arrêter le transfert sélectionné')
        QTest.mouseClick(button, Qt.LeftButton)
        self.assertTrue(first.cancelled)
        self.assertFalse(second.cancelled)
        first.completed.emit(False, 'Transfert annulé.')
        self.assertEqual(w.transfer_history[0]['state'], 'Interrompu')
        self.assertEqual(w.kio_transfer_workers(), [second])
        page.close()

    def close_choice(self, text):
        def choose():
            box = self.app.activeModalWidget()
            if isinstance(box, QMessageBox):
                next(button for button in box.buttons() if button.text() == text).click()
        QTimer.singleShot(0, choose)
        self.window.quit_requested = True
        self.window.close()
        self.drain()

    def test_close_can_be_cancelled_without_cancelling_transfers(self):
        first, second = self.start(), self.start('second')
        self.close_choice('Revenir à Mirivue')
        self.assertTrue(self.window.isVisible())
        self.assertFalse(first.cancelled)
        self.assertFalse(second.cancelled)

    def test_stop_and_quit_waits_until_every_transfer_finishes(self):
        w = self.window
        first, second = self.start(), self.start('second')
        self.close_choice('Arrêter les transferts et quitter')
        self.assertTrue(first.cancelled)
        self.assertTrue(second.cancelled)
        self.assertTrue(w.isVisible())
        first.completed.emit(False, 'Transfert annulé.')
        self.drain()
        self.assertTrue(w.isVisible())
        second.completed.emit(False, 'Transfert annulé.')
        self.drain()
        self.assertFalse(w.isVisible())

    def test_stop_folder_loading_does_not_cancel_file_operations(self):
        w = self.window
        first, second = self.start(), self.start('second')
        class Loading:
            cancelled = False
            def cancel(self): self.cancelled = True
        loading = Loading()
        w.worker = loading
        try:
            w.cancel()
            self.assertTrue(loading.cancelled)
            self.assertFalse(first.cancelled)
            self.assertFalse(second.cancelled)
        finally:
            w.worker = None

    def test_clearing_history_keeps_pending_native_operation(self):
        w = self.window
        first, second = self.start(), self.start('second')
        first.completed.emit(True, '')
        self.assertEqual(w.clear_transfer_history(), 1)
        self.assertEqual(w.kio_transfer_workers(), [second])
        self.assertEqual(len(w.transfer_history), 1)

    def test_cancelled_operation_cannot_start_its_success_follow_up(self):
        callback = unittest.mock.Mock()
        worker = self.start(on_success=callback)
        worker.cancel()
        worker.completed.emit(True, '')  # Native completion won the race.
        self.drain()
        callback.assert_not_called()

    def test_cancelled_native_job_is_not_reported_as_failure(self):
        w = self.window
        worker = self.start(operation='copyas')
        worker.completed.emit(False, 'Transfert annulé.')
        self.assertEqual(w.transfer_history[-1]['state'], 'Interrompu')
        self.assertEqual(w.transfer_history[-1]['errors'], [])

    def test_known_folder_duration_stays_visible_during_queued_and_running_analysis(self):
        w = self.window
        folder = self.root/'media'
        folder.mkdir()
        row = basic_entry(folder, is_dir=True)
        row.total_duration = 123
        w.folder = w.bound_pane.folder = str(self.root)
        w.model.add(row)
        job = dict(kind='duration', label='Calcul des durées', rows=[row], paths={row.path},
                   done=set(), started=set(), message='', errors=[], state='En attente')
        w.job_history.append(job)
        for active in (False, True):
            w.job_queue = [] if active else [job]
            w.active_job = job if active else None
            job['started'] = {row.path} if active else set()
            for mode in (0, 1, 2):
                w.change_view(mode)
                self.drain()
                self.assertEqual(w.model.index(0, 2).data(), '00:02:03')
            w.render_job_footer()
            self.assertTrue(w.job_progress.isVisible())
