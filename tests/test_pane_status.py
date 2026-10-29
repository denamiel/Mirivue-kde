import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mirivue_pane_status', ROOT / 'mirivue' / 'pane_status.py')
PANE_STATUS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PANE_STATUS)


def row(is_dir, size=0):
    return SimpleNamespace(is_dir=is_dir, sort_values=['', size])


class TestPaneStatus(unittest.TestCase):
    def test_dolphin_style_folder_and_file_summary(self):
        rows = [row(True) for _ in range(10)] + [row(False, 1024) for _ in range(34)]
        summary = PANE_STATUS.summarize_items(rows, lambda text: text, lambda size: f'{size} octets')
        self.assertEqual(summary, '10 dossiers, 34 fichiers (34816 octets)')

    def test_folder_only_summary_has_no_size(self):
        summary = PANE_STATUS.summarize_items([row(True) for _ in range(11)], lambda text: text, str)
        self.assertEqual(summary, '11 dossiers')

    def test_empty_folder_is_an_item_count_not_an_error_count(self):
        summary = PANE_STATUS.summarize_items([], lambda text: text, str)
        self.assertEqual(summary, '0 élément')

    def test_selection_summary_includes_file_size(self):
        summary = PANE_STATUS.summarize_items([row(False, 2048)], lambda text: text, lambda size: f'{size} octets', selected=True)
        self.assertEqual(summary, '1 fichier sélectionné (2048 octets)')


if __name__ == '__main__':
    unittest.main()
