"""Cancellation remains attached to one request, including queued requests."""
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from mirivue.platform_services import PlatformServices


class TestKioRequestCancellation(unittest.TestCase):
    def test_cancelled_queued_request_is_never_started(self):
        entered = threading.Event()
        gate = threading.Lock()
        gate.acquire()
        cancelled = threading.Event()
        class Lock:
            def acquire(self, **kwargs):
                entered.set()
                return gate.acquire(**kwargs)
            def release(self): gate.release()
        started = []
        fake = SimpleNamespace(_kio_lock=Lock(), _start_kio_service=lambda: started.append(True))
        result = []
        thread = threading.Thread(target=lambda: result.append(
            PlatformServices._kio_service_request(fake, 'copy', cancelled=cancelled.is_set)))
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            cancelled.set()
            thread.join(2)
            self.assertFalse(thread.is_alive(), 'annuler la demande en attente ne doit pas attendre l’autre transfert')
        finally:
            gate.release()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [(False, 'Transfert annulé.')])
        self.assertEqual(started, [])

    def test_plasma_cancelled_completion_is_recognized_for_every_operation(self):
        for command in ('copy', 'move', 'copyas', 'moveas', 'link', 'trash', 'delete', 'restore'):
            with self.subTest(command=command):
                reply = []
                def send(payload):
                    reply.append(json.dumps(dict(event='complete', id=payload['id'],
                                                 ok=False, cancelled=True)).encode()+b'\n')
                fake = SimpleNamespace(_kio_lock=threading.Lock(), _kio_output_fd=123,
                    _start_kio_service=lambda: SimpleNamespace(poll=lambda: None), _write_kio_service=send)
                selector = SimpleNamespace(register=lambda *_: None,
                    select=lambda **_: True, close=lambda: None)
                with patch('mirivue.platform_services.selectors.DefaultSelector', return_value=selector), \
                     patch('mirivue.platform_services.os.read', side_effect=lambda *_: reply.pop(0)):
                    self.assertEqual(PlatformServices._kio_service_request(fake, command),
                                     (False, 'Transfert annulé.'))

    def test_long_or_paused_transfer_has_no_application_deadline(self):
        reply = []
        def send(payload):
            reply.append(json.dumps(dict(event='complete', id=payload['id'], ok=True)).encode()+b'\n')
        fake = SimpleNamespace(_kio_lock=threading.Lock(), _kio_output_fd=123,
            _start_kio_service=lambda: SimpleNamespace(poll=lambda: None), _write_kio_service=send)
        selector = SimpleNamespace(register=lambda *_: None, select=lambda **_: True, close=lambda: None)
        with patch('mirivue.platform_services.selectors.DefaultSelector', return_value=selector), \
             patch('mirivue.platform_services.os.read', side_effect=lambda *_: reply.pop(0)), \
             patch('mirivue.platform_services.time.monotonic', side_effect=[0, 3600, 3601]):
            self.assertEqual(PlatformServices._kio_service_request(fake, 'copy', timeout=None), (True, ''))

    def test_transfer_requests_use_kde_lifetime_without_fixed_timeout(self):
        fake = SimpleNamespace(tool_path=lambda _: '/test/kio-service')
        with patch.object(fake, '_kio_service_request', create=True, return_value=(True, '')) as request:
            self.assertEqual(PlatformServices.transfer_kio(fake, ['file:///source'], 'file:///target'), (True, ''))
            self.assertIsNone(request.call_args.kwargs['timeout'])
