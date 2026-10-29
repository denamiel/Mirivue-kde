from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestCreateNewMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')

    def test_background_menu_has_only_requested_creation_entries(self):
        start = self.source.index("create_menu = menu.addMenu(tr('Créer un nouveau'))")
        end = self.source.index('menu.addSeparator()', start)
        block = self.source[start:end]
        self.assertIn('create_menu.addAction(self.new_folder_action)', block)
        self.assertIn("tr('Fichier texte…')", block)
        self.assertNotIn('HTML', block)
        self.assertNotIn('Lien vers', block)
        self.assertNotIn('Fichier vide', block)

    def test_context_menu_reuses_the_registered_terminal_command(self):
        # The physical shortcuts and their target directories are exercised by
        # test_keyboard_gui, including the selection/current-folder distinction.
        self.assertIn('menu.addAction(self.terminal_selection_action)', self.source)
        self.assertNotIn('terminal.setShortcut(', self.source)

    def test_text_creation_never_overwrites_an_existing_file(self):
        self.assertIn('os.O_CREAT | os.O_EXCL | os.O_WRONLY', self.source)


if __name__ == '__main__':
    unittest.main()
