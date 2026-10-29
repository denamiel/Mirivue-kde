from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestNativeTrashView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.movement = (ROOT / 'mirivue' / 'movement.py').read_text(encoding='utf-8')
        cls.platform = (ROOT / 'mirivue' / 'platform_services.py').read_text(encoding='utf-8')
        cls.service = (ROOT / 'native' / 'kio-service.cpp').read_text(encoding='utf-8')
        cls.places = (ROOT / 'native' / 'kio-places-widget.cpp').read_text(encoding='utf-8')

    def test_places_opens_the_virtual_trash_url(self):
        adapter = (ROOT / 'mirivue' / 'native_places_view.py').read_text(encoding='utf-8')
        self.assertIn('target.toLocalFile() if target.isLocalFile() else url', adapter)
        self.assertIn('self._activated(location)', adapter)
        self.assertIn('self.navigate, self.native_drop_completed', self.app)

    def test_trash_view_is_recognized_by_its_kio_scheme(self):
        self.assertIn("QUrl(str(self.folder)).scheme().casefold() == 'trash'", self.app)

    def test_restore_and_permanent_delete_use_native_kio_jobs(self):
        self.assertIn("operation='restore'", self.app)
        self.assertIn("operation='delete'", self.app)
        self.assertIn('KIO::restoreFromTrash(sources)', self.service)
        self.assertIn('new KIO::DeleteOrTrashJob(sources, KIO::AskUserActionInterface::Delete,', self.service)
        self.assertIn('static_cast<KIO::DeleteOrTrashJob *>(job)->start()', self.service)
        self.assertIn("tr('restore'), tr('delete')", self.platform)
        self.assertIn("'restore': (tr('Restauration')", self.movement)

    def test_remote_rows_do_not_require_pathlib_methods(self):
        open_selected = self.app.split('    def open_selected(', 1)[1].split('    def basic_properties', 1)[0]
        self.assertIn('folders = [row.path for row in rows if row.is_dir]', open_selected)
        self.assertIn('remote_files = [path for path in files if Location.from_value(path).is_uri]', open_selected)
        properties = self.app.split('    def basic_properties(', 1)[1].split('    def force_metadata', 1)[0]
        self.assertIn('if Location.from_value(path).is_uri:', properties)

    def test_native_places_trash_job_reports_completion_to_all_panes(self):
        self.assertIn('KIO::DeleteOrTrashJob', self.places)
        self.assertIn('Ask::EmptyTrash', self.places)
        self.assertIn('trashEmptied("completed")', self.places)
        self.assertIn('trashHasItems && trashHasItems()', self.places)


if __name__ == '__main__':
    unittest.main()
