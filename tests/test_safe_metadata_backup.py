"""An interrupted metadata edit must keep the original and remove partial backups."""

import ast
import errno
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
from mirivue.backup_policy import reserve_backup, record_backup, discard_new_backup


ROOT = Path(__file__).resolve().parents[1]


def load_safe_edit():
    tree = ast.parse((ROOT / 'mirivue' / 'media_tags.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'safe_edit')
    function.body = [node for node in function.body if not isinstance(node, ast.ImportFrom)]

    def fingerprint(path):
        status = Path(path).stat()
        return status.st_size, status.st_mtime_ns

    def write_mkv(path, changes, _cancelled):
        with Path(path).open('ab') as stream:
            stream.write(b'-updated')
        return changes

    namespace = dict(Path=Path, os=os, errno=errno, shutil=shutil, tempfile=tempfile,
                     uuid=uuid, tr=lambda value: value, fingerprint=fingerprint,
                     companion=lambda path: path.with_suffix('.xmp'),
                     write_mkv=write_mkv, fsync_directory=lambda _path: None,
                     durable_replace=os.replace, reserve_backup=reserve_backup,
                     record_backup=record_backup, discard_new_backup=discard_new_backup)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 '<safe_edit>', 'exec'), namespace)
    return namespace['safe_edit'], fingerprint


class TestSafeMetadataBackup(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'film.mkv'
        self.path.write_bytes(b'original')
        self.edit, signature = load_safe_edit()
        self.row = SimpleNamespace(path=self.path, file_signature=signature(self.path))

    def test_success_keeps_old_bytes_in_a_hardlink_backup(self):
        old_inode = self.path.stat().st_ino
        backup = Path(self.edit(self.row, {'title': 'new'}, 'mkv'))
        self.assertEqual(backup.read_bytes(), b'original')
        self.assertEqual(backup.stat().st_ino, old_inode)
        self.assertEqual(self.path.read_bytes(), b'original-updated')
        self.assertNotEqual(self.path.stat().st_ino, old_inode)

    def test_failed_fallback_copy_removes_partial_backup_and_temp(self):
        def incomplete(_source, destination):
            destination.write(b'partial')
            raise OSError('disk full')

        with (patch.object(os, 'link', side_effect=OSError(errno.EOPNOTSUPP, 'no hardlinks')),
              patch.object(shutil, 'copyfileobj', side_effect=incomplete)):
            with self.assertRaises(OSError):
                self.edit(self.row, {'title': 'new'}, 'mkv')
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(list(self.path.parent.glob('film.mkv.mirivue-original*')), [])
        self.assertEqual(list(self.path.parent.glob('.mirivue-*')), [])

    def test_repeated_edits_keep_the_first_original(self):
        first = Path(self.edit(self.row, {'title': 'first'}, 'mkv'))
        self.row.file_signature = self.path.stat().st_size, self.path.stat().st_mtime_ns
        second = Path(self.edit(self.row, {'title': 'second'}, 'mkv'))
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), b'original')
        self.assertEqual(list(self.path.parent.glob('film.mkv.mirivue-original*')), [first])

    def test_a_different_file_at_the_same_path_cannot_claim_the_old_backup(self):
        first = Path(self.edit(self.row, {'title': 'first'}, 'mkv'))
        self.path.write_bytes(b'new-media')
        self.row.file_signature = self.path.stat().st_size, self.path.stat().st_mtime_ns
        with self.assertRaisesRegex(ValueError, 'ne correspond plus'):
            self.edit(self.row, {'title': 'second'}, 'mkv')
        self.assertEqual(first.read_bytes(), b'original')
        self.assertEqual(self.path.read_bytes(), b'new-media')

    def test_copy_without_hardlinks_preserves_original(self):
        with patch.object(os, 'link', side_effect=OSError(errno.EPERM, 'no hardlinks')):
            saved = Path(self.edit(self.row, {'title': 'first'}, 'mkv'))
        self.assertEqual(saved.read_bytes(), b'original')
        self.assertNotEqual(saved.stat().st_ino, self.path.stat().st_ino)

    def test_insufficient_space_leaves_source_untouched(self):
        with patch.object(shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(ValueError, 'Espace insuffisant'):
                self.edit(self.row, {'title': 'new'}, 'mkv')
        self.assertEqual(self.path.read_bytes(), b'original')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])


if __name__ == '__main__':
    unittest.main()
