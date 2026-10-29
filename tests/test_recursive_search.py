from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestRecursiveSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.background = (ROOT / 'mirivue' / 'background_listing.py').read_text(encoding='utf-8')
        cls.panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        cls.desktop = (ROOT / 'mirivue' / 'desktop.py').read_text(encoding='utf-8')

    def test_search_walks_from_active_folder_and_does_not_follow_links(self):
        self.assertIn('class RecursiveSearchWorker(QThread):', self.background)
        self.assertIn('os.walk(self.folder, onerror=walk_error, followlinks=False)', self.background)
        self.assertIn("recursive=self.search_criteria['recursive']", self.app)
        self.assertIn('show_hidden=self.hidden.isChecked()', self.app)

    def test_search_is_cancellable_and_reports_live_progress(self):
        self.assertIn('self.requestInterruption()', self.background)
        self.assertIn('self.progress.emit(self.scanned, self.found', self.background)
        self.assertIn("self.stop.setText(tr('Arrêter la recherche'))", self.app)
        self.assertIn('Recherche interrompue', self.app)

    def test_old_live_filter_and_separate_filter_toolbar_are_removed(self):
        self.assertNotIn('self.search.textChanged.connect(self.filter)', self.app)
        self.assertNotIn("('filter', tr('Filtrer'), tr('Ctrl+I')", self.app)
        self.assertNotIn("(tr('state_filter')", self.desktop)

    def test_unified_panel_offers_scope_type_state_and_location(self):
        self.assertIn("self.search_scope.addItem(tr('Dossier et sous-dossiers'), 'recursive')", self.app)
        self.assertIn("(tr('Dossiers'), 'folders')", self.app)
        self.assertIn("tr('Tous les états')", self.app)
        self.assertIn("self.table.setColumnHidden(12, False)", self.app)
        self.assertIn("HEADERS", (ROOT / 'mirivue' / 'metadata.py').read_text(encoding='utf-8'))
        self.assertIn("tr('Emplacement')", (ROOT / 'mirivue' / 'metadata.py').read_text(encoding='utf-8'))

    def test_exact_duplicates_are_a_recursive_search_mode(self):
        self.assertIn("state == tr('Doublons exacts')", self.app)
        self.assertIn("'duplicates': duplicate_search", self.app)
        self.assertIn('self.start_search_duplicate_analysis', self.app)
        self.assertIn("self.enqueue_analysis(tr('duplicates'), paths)", self.app)
        self.assertIn("self.proxy.state_filter = tr('Doublons exacts')", self.app)

    def test_each_split_pane_keeps_its_search_state(self):
        self.assertIn("tr('search_active')", self.panes)
        self.assertIn('p.search_scope = self.search_scope.currentData()', self.panes)
        self.assertIn('self.table.setColumnHidden(12, not self.search_active)', self.panes)


if __name__ == '__main__':
    unittest.main()
