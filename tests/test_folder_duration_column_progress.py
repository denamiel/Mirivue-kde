"""Folder totals share Duration with media and report measurable progress."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestFolderDurationColumnProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.actions = (ROOT / 'mirivue' / 'actions_extra.py').read_text(encoding='utf-8')
        cls.analysis = (ROOT / 'mirivue' / 'analysis_extra.py').read_text(encoding='utf-8')
        cls.jobs = (ROOT / 'mirivue' / 'jobs.py').read_text(encoding='utf-8')
        cls.config = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')
        cls.media_ui = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')

    def test_folder_total_uses_duration_column(self):
        self.assertIn('column == 2 and row.is_dir', self.app)
        self.assertIn('row.values[2] = duration(total)', self.actions)

    def test_legacy_columns_are_not_user_visible(self):
        self.assertIn('column in (10, 12, 13, 15, 16, 36)', self.app)
        self.assertIn('column in (10, 12, 13, 15, 16, 36)', self.config)
        self.assertIn('column in (10, 12, 13, 15, 16, 36)', self.media_ui)
        self.assertNotIn('setColumnHidden(36, False)', self.actions)

    def test_media_composition_moves_to_duration_tooltip(self):
        self.assertIn("tr('\\nMédias trouvés : ')", self.app)

    def test_inventory_and_measured_scan_progress_are_emitted(self):
        self.assertIn('inventory_progress = Signal(object, int, str)', self.analysis)
        self.assertIn('scan_progress = Signal(object, int, int, str)', self.analysis)
        self.assertIn("self.job_progress.setFormat(tr('%v/%m médias'))", self.jobs)


if __name__ == '__main__':
    unittest.main()
