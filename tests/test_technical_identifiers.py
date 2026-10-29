from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestTechnicalIdentifiers(unittest.TestCase):
    def test_desktop_and_single_instance_ids_are_not_translated(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertIn("INSTANCE_SERVER_NAME = 'org.pdenams.Mirivue.instance.'", source)
        self.assertIn("app.setDesktopFileName('org.pdenams.Mirivue.Qt')", source)
        self.assertNotIn("tr('org.pdenams.Mirivue", source)

    def test_process_options_are_not_translated(self):
        services = (ROOT / 'mirivue' / 'platform_services.py').read_text(encoding='utf-8')
        self.assertIn("[helper, '--service'", services)
        self.assertNotIn("tr('--service')", services)

    def test_settings_keys_are_not_sent_to_the_ui_translator(self):
        for path in (ROOT / 'mirivue').glob('*.py'):
            source = path.read_text(encoding='utf-8')
            for method in ('value', 'setValue', 'remove', 'contains'):
                self.assertNotIn(f"settings.{method}(tr('", source, path.name)


if __name__ == '__main__':
    unittest.main()
