import stat
from pathlib import Path
import tempfile
import unittest

from mirivue.execution import is_executable_text_file


class MimeType:
    def __init__(self, inherited, name=''):
        self.inherited = set(inherited)
        self.mime_name = name

    def inherits(self, name):
        return name in self.inherited

    def name(self):
        return self.mime_name


EXECUTABLE_TEXT = MimeType({'application/x-executable', 'text/plain'})
ROOT = Path(__file__).resolve().parents[1]


class TestExecutableTextFiles(unittest.TestCase):
    def test_executable_text_file_matches_dolphin_predicate(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'outil.sh'
            script.write_text('#!/bin/sh\necho ok\n')
            script.chmod(script.stat().st_mode | stat.S_IXUSR)
            self.assertTrue(is_executable_text_file(script, EXECUTABLE_TEXT))

    def test_plain_text_without_execute_permission_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'outil.sh'
            script.write_text('#!/bin/sh\necho ok\n')
            script.chmod(0o644)
            self.assertFalse(is_executable_text_file(script, EXECUTABLE_TEXT))

    def test_shell_script_does_not_depend_on_kio_mime_inheritance(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'outil.sh'
            script.write_text('#!/bin/sh\necho ok\n')
            script.chmod(0o755)
            qt_only_mime = MimeType(set(), 'application/x-shellscript')
            self.assertTrue(is_executable_text_file(script, qt_only_mime))

    def test_textual_shebang_recovers_from_a_generic_qt_mime(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'outil-sans-extension'
            script.write_text('#!/usr/bin/env bash\necho ok\n')
            script.chmod(0o755)
            generic_text = MimeType({'text/plain'}, 'text/plain')
            self.assertTrue(is_executable_text_file(script, generic_text))

    def test_executable_binary_and_folder_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            binary_mime = MimeType({'application/x-executable'})
            binary = Path(folder) / 'outil'
            binary.write_bytes(b'\x7fELF')
            binary.chmod(0o755)
            self.assertFalse(is_executable_text_file(binary, binary_mime))
            self.assertFalse(is_executable_text_file(Path(folder), EXECUTABLE_TEXT))

    def test_context_menu_describes_execution_actions(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text()
        self.assertIn("tr('Exécuter le fichier')", source)
        self.assertIn("tr('Lancer dans Konsole')", source)
        self.assertIn("tr('utilities-terminal')", source)

    def test_konsole_action_keeps_the_terminal_open_without_a_shell(self):
        source = (ROOT / 'mirivue' / 'platform_services.py').read_text()
        self.assertIn("[tr('--hold'), tr('-e'), str(path)]", source)
        self.assertNotIn('shell=True', source)


if __name__ == '__main__':
    unittest.main()
