"""A KIO deletion must not reload an unrelated split pane."""

import ast
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

try:
    from PySide6.QtCore import QUrl
except ImportError:
    from urllib.parse import urlsplit, unquote

    class QUrl:
        """Minimal URL adapter for testing the pane selection without Qt."""
        def __init__(self, value):
            self.parts = urlsplit(value)

        def scheme(self):
            return self.parts.scheme

        def authority(self):
            return self.parts.netloc

        def path(self):
            return unquote(self.parts.path)

        def isLocalFile(self):
            return self.scheme() == 'file'

        def toLocalFile(self):
            return self.path()


class TestDeletionPaneRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'mirivue' / 'movement.py').read_text())
        mixin = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MovementMixin')
        selected = [node for node in mixin.body if isinstance(node, ast.FunctionDef)
                    and node.name in ('pane_affected_by_deletion', 'refresh_kio_panes', 'reconcile_deleted_panes')]
        namespace = {'BackgroundTransfers': object, 'QUrl': QUrl, 'Path': Path}
        tree = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
            name='MovementMixin', bases=[ast.Name(id='BackgroundTransfers', ctx=ast.Load())],
            keywords=[], body=selected, decorator_list=[])], type_ignores=[]))
        exec(compile(tree,
                     '<deletion refresh>', 'exec'), namespace)
        cls.mixin = namespace['MovementMixin']

    def pane(self, folder, entries=()):
        model = SimpleNamespace(rows=list(entries))
        model.remove_paths = lambda paths: model.rows.__setitem__(
            slice(None), [entry for entry in model.rows if entry not in paths])
        return SimpleNamespace(folder=str(folder), model=model, scanning=False, search_active=False)

    def window(self, panes):
        window = self.mixin()
        window.bound_pane = panes[0]
        window.panes = panes
        window.capture_pane = lambda: None
        window.recursive = SimpleNamespace(isChecked=lambda: False)
        window.rescans = []
        window.queue_pane_rescan = window.rescans.append
        window.summaries = []
        window.update_summary = lambda: None
        window.run_in_pane_silent = lambda pane, callback: window.summaries.append(pane)
        window.navigation = []
        window.navigate = lambda folder: None
        window.run_in_pane = lambda pane, callback, folder: window.navigation.append((pane, folder))
        return window

    def test_removes_only_missing_rows_and_preserves_other_pane(self):
        with TemporaryDirectory() as root:
            folder = Path(root)
            survivor = folder / 'survivor.mkv'
            survivor.touch()
            removed = folder / 'removed.mkv'
            affected = self.pane(folder, [removed, survivor])
            unrelated = self.pane(folder / 'elsewhere', [survivor])
            window = self.window([affected, unrelated])
            window.refresh_kio_panes([removed.as_uri()], 'delete')
            self.assertEqual(affected.model.rows, [survivor])
            self.assertEqual(unrelated.model.rows, [survivor])
            self.assertEqual(window.summaries, [affected])
            self.assertEqual(window.rescans, [])

    def test_two_panes_same_folder_and_open_trash(self):
        with TemporaryDirectory() as root:
            missing = Path(root) / 'gone.mkv'
            first = self.pane(root, [missing])
            second = self.pane(root, [missing])
            trash = self.pane('trash:/')
            window = self.window([first, second, trash])
            window.refresh_kio_panes([missing.as_uri()], 'trash')
            self.assertEqual(first.model.rows, [])
            self.assertEqual(second.model.rows, [])
            self.assertEqual(window.rescans, [trash])

    def test_existing_source_and_open_deleted_directory(self):
        with TemporaryDirectory() as root:
            folder = Path(root)
            existing = folder / 'still-here.mkv'
            existing.touch()
            listing = self.pane(folder, [existing])
            missing_dir = folder / 'deleted-dir'
            inside = self.pane(missing_dir)
            window = self.window([listing, inside])
            window.refresh_kio_panes([existing.as_uri()], 'delete')
            self.assertEqual(listing.model.rows, [existing])
            self.assertEqual(window.rescans, [])
            window.refresh_kio_panes([missing_dir.as_uri()], 'delete')
            self.assertEqual(window.navigation, [(inside, str(folder))])

    def test_remote_and_permanent_deletion(self):
        affected = self.mixin.pane_affected_by_deletion
        self.assertTrue(affected('smb://server/share/a', ['smb://server/share/a/file.mkv'], 'delete'))
        self.assertFalse(affected('smb://server/share/b', ['smb://server/share/a/file.mkv'], 'delete'))
        self.assertFalse(affected('trash:/', ['file:///tmp/mirivue-refresh/a/video.mkv'], 'delete'))
        self.assertTrue(affected('trash:/', ['trash:/0-video.mkv'], 'delete'))


if __name__ == '__main__':
    unittest.main()
