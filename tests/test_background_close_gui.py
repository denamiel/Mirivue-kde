"""Real Qt window lifecycle with a controlled transfer completion boundary."""
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
import test_dolphin_parity_gui as parity

class TestBackgroundClose(unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle
    def test_window_hides_without_cancelling_and_finishes_after_last_transfer(self):
        window = self.window
        jobs = [object()]
        with patch.object(window, 'pending_transfers', side_effect=lambda: list(jobs)), \
             patch.object(window, 'cancel_transfer') as cancel:
            window.close()
            self.assertFalse(window.isVisible())
            self.assertFalse(window.closing)
            self.assertTrue(window._background_transfer_close_timer.isActive())
            QTest.qWait(300)
            cancel.assert_not_called()
            jobs.clear()
            QTest.qWait(400)
            self.assertFalse(window._background_transfer_close_timer.isActive())

    def test_reopen_before_completion_keeps_window_open(self):
        window = self.window
        jobs = [object()]
        with patch.object(window, 'pending_transfers', side_effect=lambda: list(jobs)):
            window.close()
            window.show()
            QTest.qWait(300)
            jobs.clear()
            QTest.qWait(300)
            self.assertTrue(window.isVisible())
            self.assertFalse(window.closing)
            self.assertFalse(window._background_transfer_close_timer.isActive())

