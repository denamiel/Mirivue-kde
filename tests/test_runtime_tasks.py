import time
import unittest

try:
    from PySide6.QtCore import QCoreApplication, QThread
    from shiboken6 import delete, isValid
    from mirivue.runtime_tasks import RuntimeTask, RuntimeTaskRegistry
except ImportError:  # The source-only CI remains useful without Qt.
    QCoreApplication = QThread = RuntimeTaskRegistry = None


@unittest.skipIf(QThread is None, 'PySide6 absent de cet environnement')
class TestRuntimeTaskRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_registry_owns_starts_and_stops_a_worker(self):
        class Worker(QThread):
            def run(self):
                while not self.isInterruptionRequested():
                    time.sleep(0.005)

        owner = QCoreApplication.instance()
        registry = RuntimeTaskRegistry(owner)
        worker = Worker()
        registry.start(worker, 'contrôle')
        self.assertTrue(worker.isRunning())
        self.assertEqual(registry.descriptions(), ['contrôle'])
        registry.request_stop_all()
        self.assertTrue(worker.wait(1000))
        self.application.processEvents()
        self.assertEqual(registry.running(), [])

    def test_deleted_worker_cannot_break_other_task_status(self):
        owner = QCoreApplication.instance()
        registry = RuntimeTaskRegistry(owner)
        first = QThread()
        registry.track(first, 'ancien calcul des dossiers')
        # A completion handler may delete its worker before the registry's
        # queued finished callback, as happened with FolderSizeWorker.
        delete(first)
        self.assertFalse(isValid(first))
        registry._threads[id(first)] = (first, RuntimeTask('ancien calcul des dossiers'))
        self.assertEqual(registry.running(), [])
        self.assertEqual(registry.descriptions(), [])
        self.assertEqual(registry.request_stop_all(), [])

    def test_explicitly_protected_transfer_is_not_cancelled_with_lookup_tasks(self):
        class Worker(QThread):
            def run(self):
                while not self.isInterruptionRequested():
                    time.sleep(0.005)
        registry = RuntimeTaskRegistry(self.application)
        transfer, lookup = Worker(), Worker()
        registry.start(transfer, 'transfert')
        registry.start(lookup, 'lecture')
        try:
            self.assertEqual(registry.request_stop_all(exclude=[transfer]), [lookup])
            self.assertTrue(lookup.wait(1000))
            self.assertFalse(transfer.isInterruptionRequested())
            self.assertTrue(transfer.isRunning())
        finally:
            transfer.requestInterruption()
            lookup.requestInterruption()
            self.assertTrue(transfer.wait(1000))
            self.assertTrue(lookup.wait(1000))
            self.application.processEvents()


if __name__ == '__main__':
    unittest.main()
