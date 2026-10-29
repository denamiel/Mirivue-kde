from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestMimeFileIcons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')

    def test_non_media_files_are_not_forced_to_text_icon(self):
        decoration = self.source.split(
            "if role == Qt.ItemDataRole.DecorationRole and column == 0:", 1
        )[1].split("if role == Qt.ItemDataRole.UserRole:", 1)[0]
        self.assertIn('return self.file_icon(row)', decoration)
        self.assertNotIn("tr('text-x-generic')", decoration)

    def test_file_icon_uses_exact_then_generic_mime_theme_icons(self):
        method = self.source.split('    def file_icon(self, row):', 1)[1].split(
            '\n    def rowCount(', 1
        )[0]
        self.assertIn('self.mime_database.mimeTypeForFile', method)
        self.assertIn('mime.iconName()', method)
        self.assertIn('mime.genericIconName()', method)
        self.assertIn('QIcon.fromTheme(name)', method)

    def test_remote_kio_mime_type_is_used(self):
        method = self.source.split('    def file_icon(self, row):', 1)[1].split(
            '\n    def rowCount(', 1
        )[0]
        self.assertIn("mime_name = str(row.values[10] or '')", method)
        self.assertIn('self.mime_database.mimeTypeForName(mime_name)', method)


if __name__ == '__main__':
    unittest.main()
