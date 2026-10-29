from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestRetiredDeepScanners(unittest.TestCase):
    def test_removed_media_scanners_are_not_shipped(self):
        app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        analysis = (ROOT / 'mirivue' / 'analysis_extra.py').read_text(encoding='utf-8')
        self.assertFalse((ROOT / 'mirivue' / 'deep_scan.py').exists())
        for obsolete in ('SaveScanner', 'HealthScanner', 'VerifyScanner', 'calculate_bitrate'):
            self.assertNotIn(obsolete, app + analysis)

    def test_resume_policy_uses_only_current_job_fields(self):
        source = (ROOT / 'mirivue' / 'enhancements.py').read_text(encoding='utf-8')
        start = source.index('def resume_operations')
        end = source.index('def discard_pending', start)
        block = source[start:end]
        self.assertIn("policy = (job[tr('kind')], job[tr('samples')])", block)
        self.assertNotIn("job[tr('embed')]", block)
        self.assertNotIn("job[tr('delete_backup')]", block)


if __name__ == '__main__':
    unittest.main()
