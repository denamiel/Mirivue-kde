"""Details rows should visually reach the pane edge like Dolphin."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestDetailsRowWidth(unittest.TestCase):
    def test_dolphin_fill_is_the_default_and_old_false_default_is_migrated(self):
        source = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertIn("'columns/fill-view-width-dolphin-v1'", source)
        self.assertIn('True if self._dolphin_fill_width_migration', source)
        self.assertIn("fill-width-v1', True, type=bool", source)
        self.assertIn('configure_details_header(pane.table,', source)


if __name__ == '__main__':
    unittest.main()
