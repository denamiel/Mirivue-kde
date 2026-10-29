from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestOperationsButtonPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.jobs = (ROOT / 'mirivue' / 'jobs.py').read_text(encoding='utf-8')
        cls.transfers = (ROOT / 'mirivue' / 'background_transfers.py').read_text(encoding='utf-8')

    def test_operations_button_is_attached_to_the_sidebar_footer(self):
        self.assertIn("setObjectName(tr('mirivueOperationsSidebarSlot'))", self.app)
        self.assertIn('side_layout.addWidget(self.operations_sidebar_slot)', self.app)
        self.assertIn('self.operations_sidebar_slot.layout().addWidget(self.job_button', self.jobs)
        self.assertIn('operations_sidebar_layout.setContentsMargins(0, 0, 0, 0)', self.app)

    def test_idle_icon_does_not_add_a_full_width_footer_row(self):
        self.assertNotIn('footer.addWidget(self.job_button', self.jobs)
        self.assertIn('self.update_activity_entry_points()', self.jobs)
        self.assertIn('self.sync_activity_progress_visibility()', self.jobs)

    def test_native_compact_icon_and_hidden_sidebar_fallback(self):
        self.assertIn("themed_icon(tr('view-more-symbolic')", self.jobs)
        self.assertIn('self.job_button.setAutoRaise(True)', self.jobs)
        self.assertIn('self.activity_fallback_button', self.jobs)
        self.assertIn('live and self.sidebar.isHidden()', self.app)
        self.assertIn('self.operations_sidebar_slot.setVisible(live and not self.sidebar.isHidden())', self.app)
        self.assertIn('self.jobs_action.setEnabled(available)', self.app)

    def test_one_operations_button_covers_analyses_and_transfers(self):
        self.assertIn("self.create_transfers_page(dialog)", self.jobs)
        self.assertNotIn("QPushButton(tr('Transferts'))", self.transfers)
        self.assertIn("self.create_analyses_page(dialog)", self.jobs)
        self.assertNotIn("QPushButton(tr('Voir les copies et déplacements'))", self.jobs)

    def test_overflow_button_uses_the_native_plasma_style(self):
        self.assertEqual(self.app.count("overflow.setStyleSheet('')"), 2)
        self.assertNotIn('QToolButton#mirivueToolbarOverflow:hover { background: palette(mid)', self.app)
        self.assertNotIn("overflow.setStyleSheet(trf(", self.app)


if __name__ == '__main__':
    unittest.main()
