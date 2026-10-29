"""Guard the active KIO deletion path against a selected mount root."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mirivue.deletion_guard import selected_mount_points


class TestDeletionAtPartitionRoot(unittest.TestCase):
    def test_regular_items_under_mount_root_are_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            mount = Path(temporary)
            child = mount / 'file.txt'
            child.write_text('sample')
            with patch('mirivue.deletion_guard.os.path.ismount', side_effect=lambda path: path == mount):
                self.assertEqual(selected_mount_points([child]), [])
                self.assertEqual(selected_mount_points([mount, child]), [mount])

    def test_active_deletion_checks_before_starting_kio_job(self):
        source = (Path(__file__).resolve().parents[1] / 'mirivue' / 'app.py').read_text()
        block = source.split('    def delete_selected(self, requested_mode=None):', 1)[1].split('\n    def pick(self):', 1)[0]
        self.assertLess(block.index('selected_mount_points(paths)'), block.index('self.start_kio_transfer('))


if __name__ == '__main__':
    unittest.main()
