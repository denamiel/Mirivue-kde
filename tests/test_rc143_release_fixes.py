"""Behavioral checks for the launcher, language and per-user cleanup."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from mirivue.i18n import configured_language, tr, trf


ROOT = Path(__file__).resolve().parents[1]


class TestReleaseFixes(unittest.TestCase):
    def test_ui_contract_matches_removed_language_control(self):
        contract = (ROOT / 'mirivue/ui_contract.py').read_text()
        configuration = (ROOT / 'mirivue/configuration.py').read_text()
        self.assertNotIn('dialog.language', contract)
        self.assertNotIn('self.language', configuration)

    def test_draft_english_setting_cannot_change_internal_values(self):
        with patch.dict(os.environ, {'LANG': 'en_US.UTF-8'}):
            self.assertEqual(configured_language(), 'fr')
            for value in ('rb', '_preview_fullscreen', 'trash:/', '-overwrite_original', 'Lecture'):
                self.assertEqual(tr(value), value)
            self.assertEqual(trf('Fichier \x1f0\x1f', 'essai.mkv'), 'Fichier essai.mkv')

    def test_launcher_resolves_relative_paths_before_changing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'Mes vidéos').mkdir()
            environment = dict(os.environ, XDG_STATE_HOME=str(folder / 'state'))
            result = subprocess.run(
                ['bash', '-x', str(ROOT / 'Lancer.sh'), '--version', 'Mes vidéos', 'trash:/'],
                cwd=folder, env=environment, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(folder / 'Mes vidéos'), result.stderr)
            self.assertIn('trash:/', result.stderr)
            self.assertNotIn(str(ROOT / 'Mes vidéos'), result.stderr)

    def test_uninstaller_removes_only_its_own_activation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            bin_dir = folder / 'bin'
            bin_dir.mkdir()
            pacman = bin_dir / 'pacman'
            pacman.write_text('#!/bin/sh\nexit 1\n')
            pacman.chmod(0o755)
            service = folder / 'data/dbus-1/services/org.freedesktop.FileManager1.service'
            service.parent.mkdir(parents=True)
            environment = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}',
                               XDG_DATA_HOME=str(folder / 'data'))
            script = ROOT / 'Desinstaller-paquet-CachyOS.sh'
            service.write_text('[D-BUS Service]\nName=org.freedesktop.FileManager1\nExec=/usr/bin/dolphin\n')
            result = subprocess.run(['bash', str(script)], env=environment,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(service.exists())
            service.write_text('# Managed by Mirivue KDE\n[D-BUS Service]\n'
                               'Name=org.freedesktop.FileManager1\n'
                               'Exec=/usr/bin/mirivue-kde --file-manager-service\n')
            result = subprocess.run(['bash', str(script)], env=environment,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(service.exists())


if __name__ == '__main__':
    unittest.main()
