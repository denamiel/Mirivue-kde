"""The Size column can show direct item count or recursive folder size."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestFolderSizeDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.background = (ROOT / 'mirivue' / 'background_listing.py').read_text(encoding='utf-8')
        cls.config = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')
        cls.metadata = (ROOT / 'mirivue' / 'metadata.py').read_text(encoding='utf-8')
        cls.panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')

    def test_configuration_offers_both_meanings_and_defaults_to_count(self):
        self.assertIn("addItem(tr('Nombre d’éléments'), 'count')", self.config)
        self.assertIn("addItem(tr('Taille totale'), 'size')", self.config)
        self.assertIn("value('view/folder-size-display', 'count')", self.config)

    def test_count_is_direct_and_size_is_recursive(self):
        self.assertIn('sum(1 for _entry in folder.iterdir())', self.background)
        self.assertIn('for root, _dirs, files in os.walk(folder', self.background)
        self.assertIn("mode if mode in ('count', 'size') else 'count'", self.background)

    def test_folder_results_are_published_as_one_stable_model_update(self):
        worker_start = self.background.index('class FolderSizeWorker')
        worker = self.background[worker_start:]
        start = self.app.index('def start_folder_sizes(self):')
        end = self.app.index('def row(self, index):', start)
        launcher = self.app[start:end]
        batch_start = self.app.index('def set_folder_sizes(self, results, mode):')
        batch_end = self.app.index('def set_folder_size_display(self, mode):', batch_start)
        batch = self.app[batch_start:batch_end]

        self.assertIn('results_ready = Signal(object, str)', worker)
        self.assertIn('results = []', worker)
        self.assertEqual(worker.count('self.results_ready.emit('), 1)
        self.assertNotIn('folder_size.emit(', worker)
        self.assertIn('worker.results_ready.connect(', launcher)
        self.assertNotIn("row.values[1] = ''", launcher)
        self.assertEqual(batch.count('self.model.dataChanged.emit('), 1)

    def test_media_content_column_is_retired_but_slot_stays_hidden(self):
        self.assertNotIn("tr('Contenu multimédia')", self.metadata)
        self.assertIn('self.table.setColumnHidden(36, True)', self.app)
        self.assertIn('self.table.setColumnHidden(36, True)', self.panes)


if __name__ == '__main__':
    unittest.main()
