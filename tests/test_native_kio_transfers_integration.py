"""Real KIO service, local disposable data and actual filesystem boundaries."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from mirivue.platform_services import services


def manifest(root):
    result = {}
    for p in root.rglob('*'):
        name = str(p.relative_to(root))
        if p.is_symlink(): result[name] = ('link', os.readlink(p))
        elif p.is_dir(): result[name] = ('dir',)
        else: result[name] = ('file', hashlib.sha256(p.read_bytes()).hexdigest())
    return result


class TestNativeKioTransfers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['Mirivue-KIO-test'])
        if not services.tool_path('mirivue-kio-service'):
            raise RuntimeError('Compiled KIO service required')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mirivue-real-kio-')
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(services.shutdown_kio_service)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'Été_日本').mkdir()
        (self.source / 'Été_日本/data').write_bytes(bytes(range(256)) * 4096)
        (self.source / '.hidden').write_bytes(b'hidden')
        (self.source / 'empty').write_bytes(b'')
        (self.source / 'link').symlink_to('.hidden')
        self.expected = manifest(self.source)
        self.target = self.root / 'destination'
        self.target.mkdir()

    def request(self, command, source, destination, cancelled=None):
        return services._kio_service_request(command, sources=[source.as_uri()],
            destination=destination.as_uri(), timeout=15, cancelled=cancelled)

    def test_copy_preserves_complete_manifest_and_source(self):
        ok, error = self.request('copy', self.source, self.target)
        self.assertTrue(ok, error)
        self.assertEqual(manifest(self.source), self.expected)
        self.assertEqual(manifest(self.target / 'source'), self.expected)

    def test_move_preserves_manifest_and_removes_source(self):
        ok, error = self.request('move', self.source, self.target)
        self.assertTrue(ok, error)
        self.assertFalse(self.source.exists())
        self.assertEqual(manifest(self.target / 'source'), self.expected)

    def test_cancel_native_request_preserves_source(self):
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 3
        ok, _ = self.request('copy', self.source, self.target, cancelled)
        self.assertFalse(ok)
        self.assertEqual(manifest(self.source), self.expected)

    def test_conflict_cancel_does_not_overwrite_destination(self):
        source = self.source / '.hidden'
        existing = self.target / source.name
        existing.write_bytes(b'preserve destination')
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 4
        ok, _ = self.request('copy', source, self.target, cancelled)
        self.assertFalse(ok)
        self.assertEqual(existing.read_bytes(), b'preserve destination')
        self.assertEqual(source.read_bytes(), b'hidden')

    def test_missing_source_reports_failure_without_destination(self):
        ok, _ = self.request('copy', self.root / 'absent', self.target)
        self.assertFalse(ok)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_cross_filesystem_round_trip(self):
        shared = Path('/dev/shm')
        self.assertTrue(shared.is_dir())
        self.assertNotEqual(shared.stat().st_dev, self.root.stat().st_dev)
        with tempfile.TemporaryDirectory(prefix='mirivue-kio-cross-', dir=shared) as folder:
            other = Path(folder)
            ok, error = self.request('move', self.source, other)
            self.assertTrue(ok, error)
            self.assertFalse(self.source.exists())
            self.assertEqual(manifest(other / 'source'), self.expected)
            ok, error = self.request('move', other / 'source', self.target)
            self.assertTrue(ok, error)
            self.assertFalse((other / 'source').exists())
            self.assertEqual(manifest(self.target / 'source'), self.expected)



    def test_cancel_move_after_request_submission_preserves_both_files(self):
        # The first three checks are before submission. The fourth is in the
        # response loop, after the real native job has been requested.
        source = self.source / '.hidden'
        existing = self.target / source.name
        existing.write_bytes(b'keep destination')
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls >= 4
        ok, error = self.request('move', source, self.target, cancelled)
        self.assertFalse(ok)
        self.assertEqual(error, 'Transfert annulé.')
        self.assertGreaterEqual(calls, 4)
        self.assertEqual(source.read_bytes(), b'hidden')
        self.assertEqual(existing.read_bytes(), b'keep destination')

    def test_read_only_destination_preserves_source(self):
        readonly = Path('/sys')
        self.assertTrue(os.statvfs(readonly).f_flag & os.ST_RDONLY,
                        'CI requires a read-only /sys mount')
        source = self.source / '.hidden'
        # A unique absent name avoids any existing system entry. /sys is
        # read-only even for root inside the Fedora CI container.
        source = source.rename(self.source / ('mirivue-test-' + self.root.name))
        ok, error = self.request('move', source, readonly)
        self.assertFalse(ok)
        self.assertTrue(error)
        self.assertNotEqual(error, 'Transfert annulé.', 'a timeout must not masquerade as the filesystem error')
        self.assertNotIn('ne répond pas', error)
        self.assertEqual(source.read_bytes(), b'hidden')
        self.assertFalse((readonly / source.name).exists())

    def test_full_destination_preserves_cross_filesystem_move_source(self):
        # Docker's /dev/shm is a private, bounded tmpfs (not the host's disk).
        # Actually exhaust it instead of injecting an error in another engine.
        shared = Path('/dev/shm')
        total = os.statvfs(shared).f_blocks * os.statvfs(shared).f_frsize
        self.assertLessEqual(total, 128 * 1024 * 1024,
                             'Only run this test in a small private CI tmpfs')
        self.assertNotEqual(shared.stat().st_dev, self.root.stat().st_dev)
        source = self.source / 'large.bin'
        payload = bytes(range(256)) * 8192
        source.write_bytes(payload)
        with tempfile.TemporaryDirectory(prefix='mirivue-full-', dir=shared) as folder:
            destination = Path(folder)
            with (destination / 'filler').open('wb') as filler:
                free = os.statvfs(shared).f_bavail * os.statvfs(shared).f_frsize
                os.posix_fallocate(filler.fileno(), 0, free - 65536)
                ok, error = self.request('move', source, destination)
            self.assertFalse(ok)
            self.assertTrue(error)
            self.assertNotEqual(error, 'Transfert annulé.', 'a timeout must not masquerade as the filesystem error')
            self.assertNotIn('ne répond pas', error)
            self.assertEqual(source.read_bytes(), payload)
            # Partial-copy naming/cleanup belongs to KIO. Do not promise its
            # atomic publication or unconditional removal of every partial.


if __name__ == '__main__': unittest.main()
