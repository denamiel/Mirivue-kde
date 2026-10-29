"""The top of the window follows Plasma without manufactured colours."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestNativePlasmaChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.desktop = (ROOT / 'mirivue' / 'desktop.py').read_text(encoding='utf-8')
        cls.configuration = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')

    def test_folder_count_has_no_visible_loading_label(self):
        self.assertNotIn("tr('Calcul en attente')", self.app)
        self.assertNotIn("tr('Informations du dossier en cours de calcul.')", self.app)
        self.assertIn("entry.values[1] = ''", self.app)

    def test_application_chrome_is_left_to_the_native_style(self):
        start = self.desktop.index('    def apply_chrome_background(self):')
        end = self.desktop.index('\n    def toolbar_state(', start)
        method = self.desktop[start:end]
        self.assertNotIn('self.setStyleSheet(', method)
        self.assertNotIn('self.menuBar().setStyleSheet(', method)
        self.assertNotIn('self.navigation_bar.setStyleSheet(', method)
        self.assertNotIn('background:', method)
        self.assertNotIn('BackgroundNormal', method)
        self.assertNotIn('self.setStyleSheet(', self.app[self.app.index('class Window('):self.app.index('        self.thumbnail_worker = None')])

    def test_native_palette_is_not_replaced_after_app_creation(self):
        start = self.app.index('    def set_theme(self, mode):')
        end = self.app.index('\n    def show_activity_message(', start)
        self.assertNotIn('setPalette(', self.app[start:end])
        start = self.desktop.index('    def follow_desktop(self, force=False):')
        end = self.desktop.index('\n    def empty_trash(', start)
        self.assertNotIn('QApplication.setPalette(', self.desktop[start:end])
        self.assertNotIn('QApplication.setStyle(', self.desktop[start:end])

    def test_no_extra_rule_is_drawn_below_the_toolbar(self):
        self.assertNotIn('mirivueNavigationSeparator', self.app)
        self.assertNotIn('self.navigation_separator', self.app)

    def test_breeze_receives_a_real_kde_tools_area(self):
        self.assertIn('self.navigation_bar = create_native_toolbar(self)', self.app)
        native = (ROOT / 'native' / 'kio-places-widget.cpp').read_text(encoding='utf-8')
        self.assertIn('new KToolBar(', native)
        self.assertIn('self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.navigation_bar)', self.app)
        self.assertIn('self.navigation_bar.setMovable(False)', self.app)
        self.assertNotIn("self.navigation_bar = QWidget()", self.app)
        self.assertNotIn('mirivueNavigationSection', self.app)

    def test_location_bar_height_is_owned_by_the_native_style(self):
        panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertNotIn('bar.setFixedHeight(', panes)
        self.assertIn('QSizePolicy.Policy.Preferred', panes)

    def test_active_and_inactive_colours_remain_native(self):
        start = self.desktop.index('    def apply_chrome_background(self):')
        end = self.desktop.index('\n    def toolbar_state(', start)
        method = self.desktop[start:end]
        self.assertNotIn('Colors:Header', method)
        self.assertNotIn('setPalette(', method)

    def test_no_fixed_light_or_dark_application_palette_remains(self):
        start = self.app.index('    def set_theme(self, mode):')
        end = self.app.index('\n    def show_activity_message(', start)
        method = self.app[start:end]
        for colour in ('#25282d', '#f2f3f5', '#1c1f24', '#30353d', '#2867ad'):
            self.assertNotIn(colour, method)
        self.assertNotIn("tr('Clair')", self.configuration)
        self.assertNotIn("tr('Sombre')", self.configuration)


if __name__ == '__main__':
    unittest.main()
