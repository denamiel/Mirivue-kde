import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtWidgets import QApplication
    from mirivue.app import VideoModel
    from mirivue.i18n import tr
    from mirivue.metadata import basic_entry
except ImportError:
    QApplication = VideoModel = basic_entry = None
    tr = lambda value: value


@unittest.skipIf(QApplication is None, 'PySide6 absent de cet environnement')
class TestVisibleEntryRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication(['Mirivue-tests'])

    def test_new_visible_file_is_added_without_obsolete_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nouveau.txt'
            path.write_text('contenu', encoding='utf-8')
            model = VideoModel()

            model.add(basic_entry(path))

            self.assertEqual(model.rowCount(), 1)
            self.assertEqual(model.rows[0].path, path)
            self.assertEqual(model.rows[0].values[0], path.name)

    def test_completed_refresh_replaces_the_preliminary_row(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'actualise.txt'
            path.write_text('contenu', encoding='utf-8')
            model = VideoModel()
            preliminary = basic_entry(path)
            preliminary.values[10] = tr('Lecture des informations…')
            model.add_preliminary([preliminary])

            completed = basic_entry(path)
            model.add(completed)

            self.assertEqual(model.rowCount(), 1)
            self.assertIs(model.rows[0], completed)
            self.assertNotIn(path, model.preliminary)


if __name__ == '__main__':
    unittest.main()
