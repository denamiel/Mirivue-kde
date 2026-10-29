"""The third file view must participate in the same operations as the others."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / 'mirivue'


class TestCompactViewIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'app.py').read_text(encoding='utf-8')
        cls.panes = (ROOT / 'panes.py').read_text(encoding='utf-8')

    def test_split_panes_and_drag_sources_include_compact_view(self):
        self.assertIn("tr('compact'), tr('content_stack')", self.panes)
        self.assertIn('self.content_stack.addWidget(self.compact)', self.panes)
        self.assertIn('p.table, p.icons, p.compact', self.panes)
        self.assertIn('source = next((p for p in self.panes if event.source() in (p.table, p.icons, p.compact))', self.panes)

    def test_navigation_selection_preview_and_zoom_include_compact_view(self):
        self.assertIn('self.content_stack.addWidget(self.compact)', self.app)
        # Desktop selection now lives in external_locations.py and is
        # exercised through all three actual views by the navigation tests.
        self.assertIn('self.compact.viewport().update()', self.app)
        self.assertIn('def zoom_compact(self, delta):', self.app)
        self.assertIn('watched is self.compact.viewport()', self.app)
        self.assertIn("(2, tr('Vue compacte'), 'view-list-details')", self.app)


if __name__ == '__main__':
    unittest.main()
