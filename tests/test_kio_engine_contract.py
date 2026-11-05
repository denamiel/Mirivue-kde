"""KIO failures are terminal, visible, and never retried through another engine."""
from pathlib import Path
import unittest
from unittest.mock import patch
from mirivue.movement import KioTransferWorker
from mirivue.platform_services import services

class TestKioEngineContract(unittest.TestCase):
    def test_backend_exception_emits_failure_once(self):
        worker = KioTransferWorker(['file:///source'], 'file:///destination')
        results = []
        worker.completed.connect(lambda ok, error: results.append((ok, error)))
        with patch.object(services, 'transfer_kio', side_effect=RuntimeError('test backend failure')), \
             patch('mirivue.diagnostics._logger') as logger:
            worker.run()
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0][0])
        self.assertIn('source et la destination', results[0][1])
        logger.return_value.exception.assert_called_once()

    def test_backend_failure_is_not_retried(self):
        worker = KioTransferWorker(['file:///source'], 'file:///destination')
        results = []
        worker.completed.connect(lambda ok, error: results.append((ok, error)))
        with patch.object(services, 'transfer_kio', return_value=(False, 'destination indisponible')) as transfer:
            worker.run()
        transfer.assert_called_once()
        self.assertEqual(results, [(False, 'destination indisponible')])

if __name__ == '__main__': unittest.main()
