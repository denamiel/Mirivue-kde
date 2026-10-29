"""The bitrate writer and the tag writer share the original-file policy."""

import ast
import errno
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mirivue.atomic_io import durable_replace, fsync_directory
from mirivue.backup_policy import reserve_backup, record_backup, discard_new_backup, _legacy_signature
from test_safe_metadata_backup import load_safe_edit


ROOT = Path(__file__).resolve().parents[1]


def load_persist():
    tree = ast.parse((ROOT / 'mirivue' / 'persistence.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'persist')

    def fingerprint(path):
        status = Path(path).lstat()
        return status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns

    def native_matroska(source, destination, _value, _cancelled):
        shutil.copy2(source, destination)
        with destination.open('ab') as stream:
            stream.write(b'-tagged')

    namespace = dict(Path=Path, os=os, stat=stat, shutil=shutil, tempfile=tempfile, json=json,
                     tr=lambda value: value, trf=lambda value, *values: value,
                     TAG='test-tag', MARKER='test-marker', fingerprint=fingerprint,
                     probe=lambda path, cancelled: {'format': {'tags': {}}},
                     capture=lambda command, cancelled: {'media': {'track': [{'@type': 'General', 'Format': 'Matroska'}]}},
                     packet_digest=lambda path, cancelled: b'same-stream',
                     native_matroska=native_matroska, verify_structure=lambda before, after: None,
                     decode_saved=lambda tags: (123,), durable_replace=durable_replace,
                     fsync_directory=fsync_directory, reserve_backup=reserve_backup,
                     record_backup=record_backup, discard_new_backup=discard_new_backup)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 '<persist>', 'exec'), namespace)
    return namespace['persist']


class TestSharedBackupPolicy(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'film.mkv'
        self.path.write_bytes(b'original')
        self.write = load_persist()

    def persist(self):
        return Path(self.write(self.path, (123,)))

    def test_bit_rate_edits_keep_one_initial_original(self):
        first = self.persist()
        second = self.persist()
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), b'original')
        self.assertEqual(list(self.path.parent.glob('film.mkv.mirivue-original')), [first])

    def test_bit_rate_writer_uses_copy_without_hardlinks(self):
        with patch.object(os, 'link', side_effect=OSError(errno.EPERM, 'no hardlinks')):
            original = self.persist()
        self.assertEqual(original.read_bytes(), b'original')

    def test_copy_survives_unsupported_directory_fsync(self):
        real_fsync = os.fsync

        def limited_fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError(errno.EINVAL, 'directory sync unsupported')
            return real_fsync(descriptor)

        with (patch.object(os, 'link', side_effect=OSError(errno.EPERM, 'no hardlinks')),
              patch.object(os, 'fsync', side_effect=limited_fsync)):
            original = self.persist()
        self.assertEqual(original.read_bytes(), b'original')

    def test_changed_file_does_not_claim_old_bit_rate_backup(self):
        original = self.persist()
        self.path.write_bytes(b'unrelated-file')
        with self.assertRaisesRegex(ValueError, 'ne correspond plus'):
            self.persist()
        self.assertEqual(original.read_bytes(), b'original')

    def test_same_size_and_date_but_changed_contents_is_rejected(self):
        original = self.persist()
        previous = self.path.stat()
        self.path.write_bytes(b'X' * previous.st_size)
        os.utime(self.path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'ne correspond plus'):
            self.persist()
        self.assertEqual(original.read_bytes(), b'original')

    def test_legacy_backup_is_left_alone(self):
        legacy = Path(str(self.path) + '.mirivue-original.bak')
        legacy.write_bytes(b'old-copy')
        self.persist()
        self.assertEqual(legacy.read_bytes(), b'old-copy')

    def test_tags_and_bit_rate_reuse_the_same_initial_original(self):
        edit, signature = load_safe_edit()
        row = SimpleNamespace(path=self.path, file_signature=signature(self.path))
        first = Path(edit(row, {'title': 'new'}, 'mkv'))
        second = self.persist()
        self.assertEqual(first, second)
        self.assertEqual(first.read_bytes(), b'original')

    def test_rc150_record_migrates_when_old_identity_still_matches(self):
        original = self.persist()
        marker = self.path.with_name('.film.mkv.mirivue-backup.json')
        marker.write_text(json.dumps({'version': 1, 'current': _legacy_signature(self.path),
                                      'original': _legacy_signature(original)}), encoding='utf-8')
        self.assertEqual(self.persist(), original)
        migrated = json.loads(marker.read_text(encoding='utf-8'))
        self.assertEqual(migrated['version'], 2)
        self.assertEqual(len(migrated['current']), 3)

    def test_rc150_record_with_changed_mount_identity_is_not_guessed(self):
        original = self.persist()
        marker = self.path.with_name('.film.mkv.mirivue-backup.json')
        older = _legacy_signature(self.path)
        older[0] += 1
        marker.write_text(json.dumps({'version': 1, 'current': older,
                                      'original': _legacy_signature(original)}), encoding='utf-8')
        current_bytes = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'suivi RC150'):
            self.persist()
        self.assertEqual(marker.read_text(encoding='utf-8').count('"version": 1'), 1)
        self.assertEqual(self.path.read_bytes(), current_bytes)
        self.assertEqual(original.read_bytes(), b'original')

    def test_current_record_does_not_store_mount_or_inode_numbers(self):
        self.persist()
        marker = self.path.with_name('.film.mkv.mirivue-backup.json')
        saved = json.loads(marker.read_text(encoding='utf-8'))
        self.assertEqual(saved['version'], 2)
        self.assertEqual(len(saved['current']), 3)
        self.assertEqual(len(saved['current'][2]), 64)
        self.assertEqual(saved['current'][0], self.path.stat().st_size)

    def test_remounted_device_and_inode_ids_do_not_block_v2(self):
        original = self.persist()
        real_lstat, real_fstat = Path.lstat, os.fstat
        media_inodes = {real_lstat(self.path).st_ino, real_lstat(original).st_ino}

        def changed_identity(info):
            if info.st_ino not in media_inodes:
                return info
            return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink,
                                   st_dev=info.st_dev + 100, st_ino=info.st_ino + 100,
                                   st_size=info.st_size, st_mtime_ns=info.st_mtime_ns)

        def remounted_lstat(path):
            return changed_identity(real_lstat(path))

        def remounted_fstat(descriptor):
            return changed_identity(real_fstat(descriptor))

        with (patch.object(Path, 'lstat', remounted_lstat),
              patch.object(os, 'fstat', remounted_fstat)):
            self.assertEqual(reserve_backup(self.path), (original, False))


if __name__ == '__main__':
    unittest.main()
