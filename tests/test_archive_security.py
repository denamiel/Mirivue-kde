import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mirivue.archive_backend import preflight_archive_members, safe_archive_entry_name, safe_archive_member_path, validate_extracted_tree


class TestArchiveSecurity(unittest.TestCase):
    def test_archive_listing_accepts_names_but_not_paths(self):
        self.assertTrue(safe_archive_entry_name('dossier'))
        self.assertTrue(safe_archive_entry_name('été.txt'))
        for value in ('', '.', '..', '../secret', '/absolu', 'a/b', 'a\\b', 'nul\x00nom'):
            self.assertFalse(safe_archive_entry_name(value), value)

    def test_archive_member_paths_cannot_escape_staging(self):
        for value in ('folder/file.txt', 'dossier/été/image.png'):
            self.assertTrue(safe_archive_member_path(value), value)
        for value in ('../secret', 'folder/../../secret', '/etc/passwd',
                      r'C:\Windows\file', r'folder\..\secret', 'folder//file'):
            self.assertFalse(safe_archive_member_path(value), value)

    def test_archive_preflight_rejects_traversal_before_extraction(self):
        listing = b'header\n----------\nPath = dossier/fichier.txt\nPath = ../secret\n'
        result = SimpleNamespace(returncode=0, stdout=listing, stderr=b'')
        with patch('mirivue.archive_backend.shutil.which', return_value='/usr/bin/7z'), \
             patch('mirivue.archive_backend.subprocess.run', return_value=result):
            with self.assertRaises(OSError):
                preflight_archive_members('dangereux.rar')

    def test_regular_tree_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'dossier').mkdir()
            (root / 'dossier' / 'fichier.txt').write_text('ok', encoding='utf-8')
            self.assertEqual(validate_extracted_tree(root), 2)

    def test_absolute_and_escaping_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            os.symlink('/etc/passwd', root / 'absolu')
            with self.assertRaises(OSError):
                validate_extracted_tree(root)
            (root / 'absolu').unlink()
            os.symlink('../hors-zone', root / 'sortie')
            with self.assertRaises(OSError):
                validate_extracted_tree(root)

    def test_internal_relative_link_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'cible').write_text('ok', encoding='utf-8')
            os.symlink('cible', root / 'lien')
            self.assertEqual(validate_extracted_tree(root), 2)


if __name__ == '__main__':
    unittest.main()
