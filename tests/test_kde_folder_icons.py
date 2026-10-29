from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestKdeFolderIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.icons = (ROOT / 'mirivue' / 'folder_icons.py').read_text(encoding='utf-8')
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')

    def test_xdg_directories_use_kde_semantic_icons(self):
        for location, icon in (
            ('DesktopLocation', 'user-desktop'),
            ('DownloadLocation', 'folder-download'),
            ('DocumentsLocation', 'folder-documents'),
            ('MoviesLocation', 'folder-videos'),
            ('PicturesLocation', 'folder-pictures'),
            ('MusicLocation', 'folder-music'),
            ('TemplatesLocation', 'folder-templates'),
            ('PublicShareLocation', 'folder-publicshare'),
        ):
            self.assertIn(location, self.icons)
            self.assertIn(icon, self.icons)

    def test_directory_metadata_icon_has_priority(self):
        namespace = {}
        # Keep this parser test independent from PySide6 in the CI container.
        method = self.icons.split('def directory_icon_name(path: Path) -> str:', 1)[1].split(
            '\n\ndef themed_folder_icon', 1)[0]
        source = 'def directory_icon_name(path: Path) -> str:' + method
        exec(source, {'Path': Path, 'OSError': OSError}, namespace)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / '.directory').write_text(
                '[Desktop Entry]\nName=Dossier personnalisé\nIcon=folder-green\n',
                encoding='utf-8',
            )
            self.assertEqual(namespace['directory_icon_name'](folder), 'folder-green')

    def test_file_model_uses_folder_resolver_in_both_panes(self):
        method = self.app.split('    def file_icon(self, row):', 1)[1].split(
            '\n    def rowCount(', 1)[0]
        self.assertIn('themed_folder_icon(row.path, self.standard_folder_icons)', method)
        self.assertIn("QIcon.fromTheme(\n                'folder'", method)


if __name__ == '__main__':
    unittest.main()
