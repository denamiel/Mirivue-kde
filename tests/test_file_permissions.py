import stat
import tempfile
from pathlib import Path
import unittest

from mirivue.permissions import (access_level, apply_permissions,
                                 replace_access_level, set_file_executable)


class TestFilePermissions(unittest.TestCase):
    def test_basic_access_replaces_only_requested_category(self):
        mode = 0o754
        changed = replace_access_level(mode, 1, 6, directory=False)
        self.assertEqual(changed & 0o777, 0o774)

    def test_directory_access_includes_traversal(self):
        mode = replace_access_level(0o700, 1, 5, directory=True)
        self.assertEqual(access_level(mode, 1, directory=True), 5)
        self.assertTrue(mode & stat.S_IXGRP)

    def test_executable_switch_controls_all_execute_bits(self):
        self.assertEqual(set_file_executable(0o644, True) & 0o777, 0o755)
        self.assertEqual(set_file_executable(0o755, False) & 0o777, 0o644)

    def test_permissions_are_applied_and_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'script.sh'
            path.write_text('#!/bin/sh\n', encoding='utf-8')
            self.assertEqual(apply_permissions(path, 0o754), 0o754)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o754)

    def test_symbolic_link_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'target'
            target.write_text('x', encoding='utf-8')
            link = Path(folder) / 'link'
            link.symlink_to(target)
            with self.assertRaises(OSError):
                apply_permissions(link, 0o777)


if __name__ == '__main__':
    unittest.main()
