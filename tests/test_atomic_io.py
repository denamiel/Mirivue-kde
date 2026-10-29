from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mirivue.atomic_io import durable_replace


class TestAtomicIo(unittest.TestCase):
    def test_durable_replace_publishes_complete_file_and_syncs_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / '.temporaire', root / 'media.mkv'
            source.write_bytes(b'nouveau')
            target.write_bytes(b'ancien')
            with patch('mirivue.atomic_io.fsync_directory') as sync:
                durable_replace(source, target)
            self.assertEqual(target.read_bytes(), b'nouveau')
            self.assertFalse(source.exists())
            sync.assert_called_once_with(root)


if __name__ == '__main__':
    unittest.main()

