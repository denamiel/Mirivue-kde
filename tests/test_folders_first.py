from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestFoldersFirst(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.configuration = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')
        cls.panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')

    def test_option_is_visible_and_persistent(self):
        self.assertIn('Trier les dossiers avant les fichiers', self.configuration)
        self.assertIn("'sorting/folders-first'", self.configuration)
        self.assertIn("'sorting/folders-first'", self.panes)

    def test_proxy_handles_both_sort_directions(self):
        self.assertIn('left_item.is_dir != right_item.is_dir', self.app)
        self.assertIn('self.sortOrder() == Qt.SortOrder.AscendingOrder', self.app)


if __name__ == '__main__':
    unittest.main()
