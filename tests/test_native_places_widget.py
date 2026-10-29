from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestNativePlacesWidgetPackage(unittest.TestCase):
    def test_native_widget_is_built_and_packaged_with_its_adapter(self):
        cmake = (ROOT / 'native' / 'CMakeLists.txt').read_text(encoding='utf-8')
        source = (ROOT / 'native' / 'kio-places-widget.cpp').read_text(encoding='utf-8')
        package = (ROOT / 'packaging' / 'PKGBUILD.template').read_text(encoding='utf-8')
        verifier = (ROOT / 'Verifier-installation-RC194.sh').read_text(encoding='utf-8')
        self.assertIn('add_library(mirivue-kio-places-widget SHARED kio-places-widget.cpp)', cmake)
        self.assertIn('KF6::KIOFileWidgets', cmake)
        self.assertIn('class MirivuePlacesView final : public KFilePlacesView', source)
        self.assertIn('new MirivuePlacesView(', source)
        self.assertIn('new KFilePlacesModel(', source)
        self.assertIn('KFilePlacesView::contextMenuAboutToShow', source)
        self.assertIn('splitRequested(value.constData())', source)
        self.assertIn('libmirivue-kio-places-widget.so', package)
        self.assertIn('ctypes.CDLL(sys.argv[1])', verifier)

    def test_operations_button_is_outside_native_places_widget(self):
        app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        native = app.index('places_layout.addWidget(self.native_places.widget)')
        footer = app.index('side_layout.addWidget(self.operations_sidebar_slot)')
        self.assertLess(native, footer)
        self.assertIn('operations_sidebar_layout.setContentsMargins(0, 0, 0, 0)', app)

    def test_split_place_opens_in_the_other_pane(self):
        panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
        self.assertIn('self.set_split_view(True, navigate_new=False)', panes)
        self.assertIn('self.activate_pane(destination)\n            self.navigate(location)', panes)



if __name__ == '__main__':
    unittest.main()
