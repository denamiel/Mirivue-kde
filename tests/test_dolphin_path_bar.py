"""Dolphin-compatible location bar behavior."""

from pathlib import Path
import unittest

from mirivue.path_bar import local_place_breadcrumb


class TestDolphinPathBar(unittest.TestCase):
    def setUp(self):
        self.places = [
            ('Emplacements', 'Dossier personnel', '/home/p', 'user-home'),
            ('Emplacements', 'Documents', '/home/p/Documents', 'folder-documents'),
            ('Favoris', 'Projet', '/home/p/Documents/Travail/Projet', 'folder-favorites'),
            ('Volumes', 'Archives', '/run/media/p/Archives', 'drive-removable-media'),
            ('Emplacements', 'Système de fichiers', '/', 'drive-harddisk'),
        ]

    def test_exact_place_hides_its_origin(self):
        self.assertEqual(
            local_place_breadcrumb('/home/p/Documents', self.places, '/home/p'),
            [(Path('/home/p/Documents'), 'Documents')],
        )

    def test_children_start_at_deepest_matching_place(self):
        self.assertEqual(
            local_place_breadcrumb('/home/p/Documents/Travail/Projet/src', self.places, '/home/p'),
            [
                (Path('/home/p/Documents/Travail/Projet'), 'Projet'),
                (Path('/home/p/Documents/Travail/Projet/src'), 'src'),
            ],
        )

    def test_mounted_volume_uses_its_place_name(self):
        self.assertEqual(
            local_place_breadcrumb('/run/media/p/Archives/2026', self.places, '/home/p'),
            [
                (Path('/run/media/p/Archives'), 'Archives'),
                (Path('/run/media/p/Archives/2026'), '2026'),
            ],
        )

    def test_full_path_starts_at_filesystem_root(self):
        self.assertEqual(
            local_place_breadcrumb('/home/p/Documents', self.places, '/home/p', show_full=True),
            [(Path('/'), '/'), (Path('/home'), 'home'),
             (Path('/home/p'), 'p'), (Path('/home/p/Documents'), 'Documents')],
        )

    def test_location_menu_preserves_folder_name_and_dolphin_actions(self):
        root = Path(__file__).resolve().parents[1]
        panes = (root / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        for label in ('Copier', 'Coller', 'Modifier', 'Naviguer',
                      'Afficher le chemin complet', 'Copier le nom du dossier'):
            self.assertIn(f"tr('{label}')", panes)
        self.assertIn("pane.rendered_full_path == show_full", panes)
        self.assertIn("for entry in getattr(self, '_current_places'", panes)

    def test_frame_is_drawn_by_the_native_style_without_manual_colours(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        app = (root / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        start = source.index('    def style_pane_path_bars(')
        end = source.index('\n    def toggle_pane_path_mode(', start)
        styling = source[start:end]
        self.assertIn('pane.path_bar.set_active(', styling)
        self.assertNotIn('setStyleSheet', styling)
        self.assertNotIn('QColor(', styling)
        self.assertIn('class HoverPathBar(QLineEdit):', source)
        self.assertIn('self.initStyleOption(option)', source)
        self.assertIn('PE_PanelLineEdit', source)
        crumb_start = app.index('    def style_crumb(')
        crumb_end = app.index('\n    def refresh_symbolic_icons(', crumb_start)
        self.assertNotIn('setStyleSheet', app[crumb_start:crumb_end])

    def test_each_path_starts_with_dolphins_leading_chevron(self):
        source = (Path(__file__).resolve().parents[1] / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertIn("self.add_breadcrumb_chevron(pane, 'trash:/')", source)
        self.assertIn('self.add_breadcrumb_chevron(pane, previous)', source)
        self.assertIn('self.add_breadcrumb_chevron(pane, part.parent if position == 0', source)

    def test_single_path_expands_from_the_file_view_edge(self):
        source = (Path(__file__).resolve().parents[1] / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        start = source.index('    def sync_path_toolbar_alignment(')
        end = source.index('\n    def create_second_pane(', start)
        alignment = source[start:end]
        self.assertIn('if not self.split_enabled:', alignment)
        self.assertIn('pane.path_bar.setMaximumWidth(16777215)', alignment)
        self.assertIn('pane.path_bar.setSizePolicy(QSizePolicy.Policy.Expanding', alignment)

    def test_toolbar_group_cannot_stretch_past_places_boundary(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        alignment = source.split('    def sync_path_toolbar_alignment(', 1)[1].split('    def create_second_pane(', 1)[0]
        self.assertIn('self.left_toolbar_group.setMaximumWidth(command_width)', alignment)
        self.assertIn('self.left_toolbar_group.setPreferredWidth(command_width)', alignment)
        self.assertIn('if self.places_panel.isVisible():', alignment)
        self.assertIn('self.left_toolbar_group.setPreferredWidth(None)', alignment)
        self.assertIn('natural_width = self.left_toolbar_group.sizeHint().width()', alignment)
        self.assertIn('self.left_toolbar_group.setMaximumWidth(natural_width)', alignment)
        contract = (root / 'mirivue' / 'ui_contract.py').read_text(encoding='utf-8')
        self.assertIn('def check_path_positions():', contract)
        self.assertIn('window.set_split_view(True, navigate_new=False)', contract)
        self.assertIn('window.set_places_panel_visible(False)', contract)
        self.assertIn('window.back.isHidden()', contract)
        self.assertIn('check_hidden_places_toolbar()', contract)

    def test_empty_file_view_click_restores_breadcrumb_buttons(self):
        root = Path(__file__).resolve().parents[1]
        panes = (root / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        selection = (root / 'mirivue' / 'dolphin_view.py').read_text(encoding='utf-8')
        self.assertIn('view.activation_handler = lambda p=pane: self.activate_pane_from_empty_area(p)', panes)
        self.assertIn('def activate_pane_from_empty_area(self, pane):', panes)
        self.assertIn('self.toggle_pane_path_mode(pane, False)', panes)
        # Both DetailsView and IconView use this callback only after indexAt()
        # has established that the click occurred outside an item.
        self.assertIn('elif view.activation_handler: view.activation_handler()', selection)

    def test_trash_root_has_a_visible_breadcrumb_button(self):
        source = (Path(__file__).resolve().parents[1] / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertIn("url.scheme().casefold() == 'trash'", source)
        self.assertIn("QPushButton(tr('Corbeille'), pane.crumbs)", source)
        self.assertIn("trash_button.setToolTip('trash:/')", source)
        self.assertIn("self.navigate, 'trash:/')", source)


if __name__ == '__main__':
    unittest.main()
