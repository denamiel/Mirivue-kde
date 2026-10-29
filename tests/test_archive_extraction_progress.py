"""Archive extraction uses the visible, cancellable KIO progress path."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestArchiveExtractionProgress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.movement = (ROOT / 'mirivue' / 'movement.py').read_text(encoding='utf-8')
        cls.services = (ROOT / 'mirivue' / 'platform_services.py').read_text(encoding='utf-8')

    def test_archive_is_listed_off_the_ui_thread(self):
        self.assertIn('class ArchiveEntriesWorker(QThread):', self.app)
        self.assertIn('services.list_kio_location(self.location)', self.app)
        self.assertIn("self.bar.setRange(0, 0)", self.app)

    def test_whole_archive_and_selection_use_kio_progress(self):
        self.assertGreaterEqual(
            self.app.count("self.start_kio_transfer("), 2)
        self.assertGreaterEqual(
            self.app.count("operation=tr('extract')"), 2)
        self.assertIn("'extract': (tr('Extraction')", self.movement)

    def test_dolphin_archive_menu_and_destinations(self):
        self.assertIn('def add_archive_extract_menu(self, menu, path):', self.app)
        self.assertIn("tr('Extraire ici')", self.app)
        self.assertIn("tr('Extraire ici et déplacer l’archive dans la corbeille')", self.app)
        self.assertIn("tr('Extraire vers…')", self.app)
        self.assertIn('target, target.parent', self.app)
        self.assertIn('target.parent / archive_subfolder_name(target)', self.app)
        self.assertIn('create_destination=True', self.app)
        self.assertIn('trash_after=True', self.app)

    def test_archive_is_trashed_only_after_success(self):
        self.assertIn('on_success=after', self.app)
        self.assertIn('if on_success is not None:', self.movement)
        self.assertIn('QTimer.singleShot(0, on_success)', self.movement)

    def test_extract_maps_to_native_kio_copy(self):
        self.assertIn("if command == tr('extract'):", self.services)
        self.assertIn("command = tr('copy')", self.services)

    def test_rar_uses_safe_ark_fallback(self):
        locations = (ROOT / 'mirivue' / 'locations.py').read_text(encoding='utf-8')
        backend = (ROOT / 'mirivue' / 'archive_backend.py').read_text(encoding='utf-8')
        self.assertIn("if name.endswith('.rar')", locations)
        self.assertIn("if not protocol or protocol == 'rar'", locations)
        self.assertIn("if archive_protocol(path) == 'rar':", self.app)
        self.assertIn('class RarExtractWorker(QThread):', self.app)
        self.assertIn("prefix='.mirivue-extraction-'", backend)
        self.assertIn('rename_noreplace(child, target)', backend)
        self.assertIn('shutil.rmtree(staging, ignore_errors=True)', backend)


if __name__ == '__main__':
    unittest.main()
