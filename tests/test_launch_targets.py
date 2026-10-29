from pathlib import Path
import os
from tempfile import TemporaryDirectory
import unittest

from mirivue.launch_targets import is_browsable_location, parse_launch_arguments


class TestLaunchTargets(unittest.TestCase):
    def test_plain_folder_and_local_file_url(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'Dossier été'
            folder.mkdir()
            request = parse_launch_arguments([folder.as_uri()])
            self.assertEqual(request.folder, str(folder.absolute()))
            self.assertEqual(request.files, ())

    def test_file_opens_its_parent_and_is_selected(self):
        with TemporaryDirectory() as temporary:
            file = Path(temporary) / 'vidéo test.mkv'
            file.write_bytes(b'test')
            request = parse_launch_arguments([file.as_uri()])
            self.assertEqual(request.folder, str(file.parent.absolute()))
            self.assertEqual(request.files, (str(file.absolute()),))

    def test_kio_urls_are_preserved_for_the_native_backend(self):
        for location in ('trash:/', 'smb://serveur/partage', 'sftp://serveur/dossier', 'mtp:/telephone'):
            with self.subTest(location=location):
                request = parse_launch_arguments([location])
                self.assertEqual(request.folder, location)
                self.assertTrue(is_browsable_location(location))

    def test_localhost_file_url_is_treated_as_a_local_folder(self):
        with TemporaryDirectory() as temporary:
            location = 'file://localhost' + Path(temporary).as_posix()
            request = parse_launch_arguments([location])
            self.assertEqual(request.folder, str(Path(temporary).absolute()))

    def test_options_and_missing_local_paths_are_ignored(self):
        request = parse_launch_arguments(['--version', '/chemin/qui/n’existe/pas'])
        self.assertEqual(request.folder, '')
        self.assertEqual(request.files, ())

    def test_existing_relative_path_with_colon_is_a_folder_not_a_kio_url(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'Saison:2'
            folder.mkdir()
            original = Path.cwd()
            try:
                os.chdir(temporary)
                request = parse_launch_arguments(['Saison:2'])
                self.assertEqual(request.folder, str(folder))
                self.assertTrue(is_browsable_location('Saison:2'))
            finally:
                os.chdir(original)

    def test_local_socket_rejects_missing_folder(self):
        with TemporaryDirectory() as temporary:
            missing = str(Path(temporary) / 'absent')
            self.assertFalse(is_browsable_location(missing))


if __name__ == '__main__':
    unittest.main()
