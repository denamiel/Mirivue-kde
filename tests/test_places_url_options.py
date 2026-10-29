"""Real PySide URL comparison with populated KDE bookmarks, including fallback."""
from contextlib import nullcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.sax.saxutils import quoteattr
from mirivue.places import location_identity
import test_dolphin_parity_gui as parity


class TestPlacesUrlOptions(unittest.TestCase):
    def resolve(self, bookmark_url, target):
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            (data/'user-places.xbel').write_text('<xbel><bookmark href='+quoteattr(bookmark_url)+'><title>Mes médias</title></bookmark></xbel>')
            with patch('mirivue.places.QStandardPaths.standardLocations', return_value=[str(data)]):
                return location_identity(target)

    def test_local_bookmark_matches_with_or_without_trailing_slash(self):
        path = Path('/tmp/Mes films é')
        self.assertEqual(self.resolve(path.as_uri()+'/', path), ('Mes médias', 'folder'))

    def test_remote_bookmark_matches_with_or_without_trailing_slash(self):
        self.assertEqual(self.resolve('smb://serveur/films/', 'smb://serveur/films'), ('Mes médias', 'folder'))

    def test_different_bookmark_does_not_claim_current_folder(self):
        self.assertEqual(self.resolve('file:///tmp/ailleurs', '/tmp/dossier-test-179')[0], 'dossier-test-179')


class TestPlacesFallbackSplit(unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle

    def test_split_view_and_tab_titles_with_real_bookmarks_and_native_caption_unavailable(self):
        data = self.root/'data'; data.mkdir()
        (data/'user-places.xbel').write_text('<xbel><bookmark href='+quoteattr(self.folders[0].as_uri()+'/')+'><title>Mes médias</title></bookmark></xbel>')
        native = self.window.native_places
        fallback = patch.object(native, 'location_identity', return_value=None) if native is not None else nullcontext()
        with fallback, patch('mirivue.places.QStandardPaths.standardLocations', return_value=[str(data)]):
            self.assertEqual(self.window.tab_title(self.folders[0]), 'Mes médias')
            for mode in (0, 1, 2):
                self.window.change_view(mode)
                self.window.set_split_view(True, navigate_new=False)
                self.assertEqual(len(self.window.panes), 2)
                self.window.refresh_tab_title(self.window._active_tab)
                self.assertIn('Mes médias', self.window.tab_bar.tabText(self.window._active_tab))
                self.window.set_split_view(False)
