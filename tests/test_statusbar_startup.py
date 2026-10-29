from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestStartupStatusBar(unittest.TestCase):
    def test_normal_folder_load_clears_activity_message(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('Dossier chargé. Clic droit pour lire les métadonnées non lues.', source)
        self.assertIn("elif isinstance(self.worker, Scanner):", source)
        self.assertIn('self.clear_activity_message()', source)

    def test_feedback_does_not_create_an_extra_bar(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        translations = (ROOT / 'mirivue' / 'i18n.py').read_text(encoding='utf-8')
        self.assertNotIn('statusBar()', source)
        self.assertIn('self.sync_feedback_in_pane_footers()', source)
        self.assertNotIn('status_bar_action', source)
        self.assertNotIn('Afficher la barre d’état', translations)

    def test_removed_tip_is_not_translated(self):
        source = (ROOT / 'mirivue' / 'i18n.py').read_text(encoding='utf-8')
        self.assertNotIn('Dossier chargé. Clic droit pour lire les métadonnées non lues.', source)

    def test_short_folder_loads_do_not_flash_a_progress_bar(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertIn('self.folder_load_progress_timer.setInterval(450)', source)
        self.assertIn('self.schedule_folder_progress()', source)
        self.assertIn('self.refresh_scan_progress_visibility()', source)
        self.assertNotIn('self.bar.setVisible(any_scanning)', panes)

    def test_search_progress_remains_immediate(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        search_start = source.index("self.bar.setFormat(tr('Recherche en cours…'))")
        self.assertIn('self.bar.show()', source[search_start:search_start + 180])


if __name__ == '__main__':
    unittest.main()
