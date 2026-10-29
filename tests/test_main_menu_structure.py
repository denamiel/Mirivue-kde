from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestMainMenuStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.media = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')
        cls.organization = (ROOT / 'mirivue' / 'organization.py').read_text(encoding='utf-8')

    def test_top_level_menus_follow_file_manager_conventions(self):
        self.assertIn("go_menu = self.menuBar().addMenu(tr('Aller'))", self.app)
        self.assertIn("tools_menu = self.menuBar().addMenu(tr('Outils'))", self.app)
        self.assertNotIn("self.menuBar().addMenu(tr('Organiser'))", self.app)
        self.assertNotIn("self.menuBar().addMenu(tr('Opérations'))", self.app)
        self.assertNotIn("analysis_menu = self.menuBar().addMenu(tr('Analyse'))", self.app)
        self.assertNotIn("search_menu = self.menuBar().addMenu(tr('Recherche'))", self.app)
        self.assertIn("self.search_action = edit_menu.addAction(tr('Rechercher…')", self.app)

    def test_terminal_command_uses_dolphins_tools_menu_and_shortcut(self):
        self.assertIn("tr('Shift+F4')", self.app)
        self.assertIn("self.open_terminal_action", self.app)
        self.assertIn("self.rename_menu, menus['organize'], self.folder_duration_action, self.collections_menu, menus['operations']", self.app)

    def test_bitrate_writing_and_full_file_measurement_are_retired(self):
        forbidden = (
            'Calculer les débits vidéo manquants', 'Mesurer le débit vidéo',
            'Enregistrer les débits calculés', 'self.embed_checkbox',
            'self.complete_incomplete_action', 'self.deep_button',
        )
        for text in forbidden:
            self.assertNotIn(text, self.app)

    def test_folder_duration_and_operations_have_clear_roles(self):
        self.assertIn('self.folder_duration_action', self.app)
        self.assertIn("populate(menus['operations']", self.app)
        self.assertIn("self.jobs_action", self.app)

    def test_file_and_edit_actions_are_grouped_explicitly(self):
        self.assertIn("self.delete_button = QAction(tr('Mettre à la corbeille')", self.app)
        self.assertIn("tr('Supprimer définitivement…')", self.app)
        self.assertIn("self.kio_undo_action, self.kio_redo_action", self.app)
        self.assertIn("self.select_all_action, self.invert_selection_action", self.app)

    def test_view_menu_has_modes_panels_and_theme_state_actions(self):
        self.assertIn("self.view_mode_menu = QMenu(tr('Mode d’affichage')", self.app)
        self.assertIn("self.compact_view_action = view_menu.addAction(tr('Vue compacte')", self.app)
        self.assertIn("tr('Ctrl+2')", self.app)
        self.assertIn("self.panels_menu = QMenu(tr('Panneaux')", self.app)
        self.assertIn("self.menu_visibility.action, None", self.app)
        self.assertNotIn('self.status_bar_action', self.app)
        self.assertIn("self.preview_action = QAction(tr('Afficher les miniatures')", self.app)

    def test_organize_menu_keeps_only_organization_tools(self):
        for label in (
            'Renommage avancé…', 'Renommer à partir des métadonnées…',
            'Corriger les extensions de la sélection…', 'Organiser en sous-dossiers…',
            'Créer une archive…', 'Collections',
        ):
            self.assertIn(label, self.app + self.organization)
        self.assertNotIn('self.duplicates_menu', self.app)
        self.assertNotIn('self.cleanup_action', self.app + self.organization)
        self.assertNotIn('def show_cleanup_guide', self.organization)

    def test_metadata_criteria_belong_to_unified_search(self):
        self.assertIn("self.search_more = QPushButton(tr('Plus de critères…')", self.app)
        self.assertIn("dialog.setWindowTitle(tr('Critères de métadonnées'))", self.media)
        self.assertNotIn("search_menu.addAction(tr('Recherche multimédia…')", self.media)

    def test_cleanup_and_exact_duplicates_belong_to_unified_search(self):
        self.assertIn("tr('Doublons exacts')", self.app)
        self.assertIn("tr('size_mib')", self.app + self.media)
        self.assertIn('self.search_duplicates_manage', self.app)
        self.assertIn('self.start_search_duplicate_analysis', self.app)


if __name__ == '__main__':
    unittest.main()
