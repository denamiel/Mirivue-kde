from dataclasses import dataclass
import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / 'mirivue' / 'paste_behavior.py'
spec = importlib.util.spec_from_file_location('mirivue_paste_behavior_test', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
context_paste_destination = module.context_paste_destination
paste_action_label = module.paste_action_label


@dataclass
class Row:
    path: object
    is_dir: bool


class TestPasteBehavior(unittest.TestCase):
    def test_single_directory_is_the_context_destination(self):
        folder = Path('/tmp/current/inside')
        self.assertEqual(context_paste_destination([Row(folder, True)], Path('/tmp/current')), folder)

    def test_single_file_has_no_context_paste_action(self):
        self.assertIsNone(context_paste_destination([Row(Path('/tmp/current/file'), False)], Path('/tmp/current')))

    def test_multiple_selection_targets_current_folder(self):
        current = Path('/tmp/current')
        rows = [Row(current / 'inside', True), Row(current / 'file', False)]
        self.assertEqual(context_paste_destination(rows, current), current)

    def test_background_targets_current_folder(self):
        current = Path('/tmp/current')
        self.assertEqual(context_paste_destination([], current), current)

    def test_dynamic_labels_match_clipboard_contents(self):
        self.assertEqual(paste_action_label(1, False), 'Coller un fichier')
        self.assertEqual(paste_action_label(1, True), 'Coller un dossier')
        self.assertEqual(paste_action_label(3), 'Coller 3 éléments')

    def test_context_target_is_forwarded_to_the_transfer(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        transfers = (root / 'mirivue' / 'transfers.py').read_text(encoding='utf-8')
        self.assertIn('paste_destination=context_paste_destination(selected, self.folder)', app)
        self.assertIn('def paste_selection(self, destination=None):', transfers)
        self.assertIn('destination = self.folder if destination is None else destination', transfers)
        self.assertIn('self.paste_selection(paste_destination)', transfers)


if __name__ == '__main__':
    unittest.main()
