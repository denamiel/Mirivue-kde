from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestCompactActivityArea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.jobs = (ROOT / 'mirivue' / 'jobs.py').read_text(encoding='utf-8')
        cls.transfers = (ROOT / 'mirivue' / 'background_transfers.py').read_text(encoding='utf-8')
        cls.media = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')
        cls.sources = ''.join(path.read_text(encoding='utf-8') for path in (ROOT / 'mirivue').glob('*.py'))

    def test_feedback_reuses_the_active_pane_footer(self):
        start = self.app.index('    def show_activity_message(')
        end = self.app.index('    def clear_activity_message(', start)
        feedback = self.app[start:end]
        self.assertIn('self.sync_feedback_in_pane_footers()', feedback)
        self.assertIn('pane.summary_label.set_full_text(feedback or summary', self.app)
        self.assertNotIn('statusBar()', self.sources)
        self.assertNotIn('status_bar_action', self.sources)

    def test_activity_is_attached_to_places_and_collapses_when_idle(self):
        self.assertIn('self.places_layout.addWidget(self.activity_message_label)', self.app)
        self.assertIn('self.places_layout.addWidget(self.bar)', self.app)
        self.assertIn('self.errors_slot.hide()', self.app)
        self.assertIn('self.activity_message_label.hide()', self.app)

    def test_only_one_priority_progress_is_visible(self):
        self.assertIn('transfer and not foreground', self.app)
        self.assertIn('task and not foreground and not transfer', self.app)

    def test_narrow_sidebar_uses_vertical_progress_layouts(self):
        self.assertIn('footer = QVBoxLayout()', self.jobs)
        self.assertIn('row = QVBoxLayout()', self.transfers)

    def test_preview_feedback_stays_in_preview_panel(self):
        self.assertIn('def show_preview_message', self.media)
        self.assertIn('box.addWidget(self.preview_status)', self.media)
        self.assertIn('box.addWidget(self.metadata_status)', self.media)

    def test_per_pane_information_is_preserved(self):
        self.assertIn('def update_pane_footer', self.app)
        self.assertIn('pane.summary_label.set_full_text', self.app)
        self.assertIn('pane.disk_label.set_full_text', self.app)


if __name__ == '__main__':
    unittest.main()
