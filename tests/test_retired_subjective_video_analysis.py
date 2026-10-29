import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestRetiredSubjectiveVideoAnalysis(unittest.TestCase):

    def test_engine_and_user_interface_are_removed(self):
        self.assertFalse((ROOT / 'mirivue' / 'quality.py').exists())
        sources = '\n'.join(
            (ROOT / 'mirivue' / name).read_text(encoding='utf-8')
            for name in ('app.py', 'configuration.py', 'jobs.py', 'metadata.py')
        )
        for obsolete in ('Diagnostic qualité', 'Qualité estimée',
                         'QualityScanner', 'start_quality_scan'):
            self.assertNotIn(obsolete, sources)

    def test_retired_column_slot_is_never_user_visible(self):
        metadata = (ROOT / 'mirivue' / 'metadata.py').read_text(encoding='utf-8')
        app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        configuration = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')
        media_ui = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')
        self.assertIn("tr('Emplacement'), '', tr('Date de modification')", metadata)
        for source in (app, configuration, media_ui):
            self.assertIn('(10, 12, 13, 15, 16, 36)', source)


if __name__ == '__main__':
    unittest.main()
