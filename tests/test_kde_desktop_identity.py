from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ID = 'org.pdenams.Mirivue.Qt'


class TestKdeDesktopIdentity(unittest.TestCase):
    def test_application_and_installer_use_same_desktop_id(self):
        app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        installer = (ROOT / 'Installer.sh').read_text(encoding='utf-8')
        self.assertIn("app.setDesktopFileName('" + DESKTOP_ID + "')", app)
        self.assertIn("QApplication.setApplicationName('" + DESKTOP_ID + "')", app)
        self.assertNotIn("tr('" + DESKTOP_ID + "')", app)
        self.assertIn('desktop_id="' + DESKTOP_ID + '"', installer)
        self.assertIn('launcher="$applications_dir/$desktop_id.desktop"', installer)
        self.assertIn('StartupWMClass=$desktop_id', installer)

    def test_cleanup_names_only_known_qt_installations(self):
        installer = (ROOT / 'Installer.sh').read_text(encoding='utf-8')
        self.assertIn('mirivue-0.9.12-essai', installer)
        self.assertIn('version GNOME', installer)
        self.assertNotIn('rm -rf -- "$share_dir/mirivue-gtk', installer)
        self.assertNotIn('rm -rf -- "$share_dir/mirivue-gnome', installer)


if __name__ == '__main__':
    unittest.main()
