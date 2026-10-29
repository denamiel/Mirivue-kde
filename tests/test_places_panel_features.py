import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('mirivue_kde_places', ROOT / 'mirivue' / 'kde_places.py')
KDE_PLACES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(KDE_PLACES)
kde_places_bookmarks = KDE_PLACES.kde_places_bookmarks
merge_kde_places = KDE_PLACES.merge_kde_places


class TestPlacesPanelFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.native = (ROOT / 'native' / 'kio-places-widget.cpp').read_text(encoding='utf-8')

    def test_native_view_owns_place_interaction(self):
        self.assertIn('KFilePlacesView', self.native)
        helper = (ROOT / 'native' / 'kio-places.cpp').read_text(encoding='utf-8')
        self.assertIn('model.setPlaceHidden(', helper)
        self.assertIn('model.setGroupHidden(', helper)
        self.assertIn('model.isGroupHidden(', helper)
        self.assertNotIn('PlacesTree', self.source)
        self.assertFalse((ROOT / 'mirivue' / 'favorites.py').exists())

    def test_live_bookmarks_feed_breadcrumbs_and_moves(self):
        self.assertIn('places = services.list_places()', self.source)
        self.assertIn('merge_kde_places(places, bookmarks)', self.source)
        self.assertIn('self._current_places = places', self.source)
        self.assertIn("services.change_place('add'", self.source)

    def test_reads_hidden_bookmarks_and_hidden_groups_from_kde_xbel(self):
        xbel = '''<?xml version="1.0" encoding="UTF-8"?>
<xbel xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks">
  <bookmark href="file:///home/test/Documents">
    <title>Documents</title>
    <info><metadata owner="http://www.kde.org"><IsHidden>true</IsHidden></metadata>
    <metadata owner="http://freedesktop.org"><bookmark:icon name="folder-documents"/></metadata></info>
  </bookmark>
  <bookmark href="recentlyused:/files"><title>Fichiers récents</title></bookmark>
  <info><metadata owner="http://www.kde.org">
    <GroupState-RecentlySaved-IsHidden>true</GroupState-RecentlySaved-IsHidden>
  </metadata></info>
</xbel>'''
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'user-places.xbel'
            path.write_text(xbel, encoding='utf-8')
            places = kde_places_bookmarks(path)
        self.assertEqual([place['name'] for place in places], ['Documents', 'Fichiers récents'])
        self.assertTrue(places[0]['sharedHidden'])
        self.assertEqual(places[0]['icon'], 'folder-documents')
        self.assertEqual(places[1]['group'], 2)
        self.assertFalse(places[1]['sharedHidden'])
        self.assertTrue(places[1]['sharedGroupHidden'])

    def test_hidden_xbel_rows_are_merged_with_live_kio_rows(self):
        live = [{'name': 'Documents live', 'url': 'file:///home/test/Documents', 'group': 0,
                 'icon': 'folder', 'device': False}]
        bookmarks = [
            {'name': 'Documents', 'url': 'file:///home/test/Documents', 'group': 0,
             'icon': 'folder-documents', 'sharedHidden': False},
            {'name': 'Images', 'url': 'file:///home/test/Images', 'group': 0,
             'icon': 'folder-pictures', 'sharedHidden': True},
            {'name': 'Fichiers récents', 'url': 'recentlyused:/files', 'group': 2,
             'icon': 'document-open-recent', 'sharedHidden': False, 'sharedGroupHidden': True},
        ]
        merged = merge_kde_places(live, bookmarks)
        self.assertEqual([place['url'] for place in merged],
                         ['file:///home/test/Documents', 'file:///home/test/Images', 'recentlyused:/files'])
        self.assertEqual(merged[0]['name'], 'Documents live')
        self.assertTrue(merged[1]['sharedHidden'])
        self.assertTrue(merged[2]['sharedGroupHidden'])


if __name__ == '__main__':
    unittest.main()
