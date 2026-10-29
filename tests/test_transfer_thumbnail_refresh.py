"""A completed transfer must paint an available preview immediately."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    from mirivue.background_transfers import BackgroundTransfers
    from mirivue.app import Window
    from mirivue.metadata import basic_entry
except ImportError:
    BackgroundTransfers = None
    Window = None


class Model:
    def __init__(self, previews=None):
        self.rows = []
        self.thumbnails = dict(previews or {})
        self.show_thumbnails = True
        self.icon_at_insert = []

    def remove_paths(self, paths):
        self.rows = [row for row in self.rows if row.path not in paths]
        for path in paths:
            self.thumbnails.pop(path, None)

    def add(self, row):
        self.icon_at_insert.append(row.path in self.thumbnails)
        self.rows.append(row)

    def index(self, *_args):
        return SimpleNamespace(isValid=lambda: False)


@unittest.skipIf(BackgroundTransfers is None, 'PySide6 absent de cet environnement')
class TestTransferThumbnailRefresh(unittest.TestCase):
    def check_transfer(self, has_source_preview):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            origin, destination = root / 'origin', root / 'destination'
            origin.mkdir()
            destination.mkdir()
            source, target = origin / 'image.png', destination / 'image.png'
            target.write_bytes(b'control')
            source_model = Model({source: 'already-rendered'} if has_source_preview else None)
            dest_model = Model()
            pane = lambda folder, model: SimpleNamespace(
                folder=folder, model=model, scanning=False,
                proxy=SimpleNamespace(mapFromSource=lambda index: index))
            source_pane, dest_pane = pane(origin, source_model), pane(destination, dest_model)
            refreshed = []
            owner = SimpleNamespace(
                panes=[source_pane, dest_pane], bound_pane=source_pane,
                result_cache={}, capture_pane=lambda: None,
                bind_pane=lambda _pane: None, sync_pane_controls=lambda: None,
                update_pane_emphasis=lambda: None,
                start_thumbnails=lambda: None,
                run_in_pane=lambda target_pane, _callback: refreshed.append(target_pane),
            )
            BackgroundTransfers.update_transfer_panes(
                owner, SimpleNamespace(moved={source: target}), copy_only=False)
            self.assertEqual(dest_model.icon_at_insert, [has_source_preview])
            self.assertEqual(dest_model.thumbnails.get(target),
                             'already-rendered' if has_source_preview else None)
            self.assertEqual(refreshed, [] if has_source_preview else [dest_pane])

    def test_cached_preview_is_present_at_row_insertion(self):
        self.check_transfer(True)

    def test_missing_preview_starts_native_generation(self):
        self.check_transfer(False)

    def test_arriving_video_starts_targeted_duration_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            origin, destination = Path(temporary) / 'origin', Path(temporary) / 'destination'
            origin.mkdir()
            destination.mkdir()
            source, target = origin / 'film.mkv', destination / 'film.mkv'
            target.write_bytes(b'control')
            source_model, destination_model = Model(), Model()
            source_pane = SimpleNamespace(folder=origin, model=source_model)
            destination_pane = SimpleNamespace(folder=destination, model=destination_model,
                                               scanning=False,
                                               proxy=SimpleNamespace(mapFromSource=lambda index: index))
            requested = []
            owner = SimpleNamespace(
                panes=[source_pane, destination_pane], bound_pane=source_pane,
                result_cache={}, capture_pane=lambda: None,
                bind_pane=lambda _pane: None, sync_pane_controls=lambda: None,
                update_pane_emphasis=lambda: None, start_thumbnails=lambda: None,
                run_in_pane=lambda _pane, callback: None,
                start_duration_lookup=lambda pane, paths: requested.append((pane, paths)),
            )
            BackgroundTransfers.update_transfer_panes(
                owner, SimpleNamespace(moved={source: target}), copy_only=False)
            self.assertEqual(requested, [(destination_pane, [target])])
            self.assertEqual([row.path for row in destination_model.rows], [target])
            self.assertEqual(destination_model.rows[0].sort_values[2], -1)

    def test_directory_notification_keeps_transferred_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.png'
            path.write_bytes(b'image')
            row = basic_entry(path)
            model = Model({path: 'preview'})
            model.rows.append(row)
            pane = SimpleNamespace(folder=Path(directory), model=model, scanning=False)
            owner = SimpleNamespace(
                panes=[pane], bound_pane=pane, model=model, closing=False,
                _visible_workers=[], refreshed=[],
                run_in_pane=lambda _pane, callback: callback(),
                bind_pane=lambda _pane: None, sync_pane_controls=lambda: None,
                start_duration_lookup=lambda *_args: None,
                add=lambda updated: model.add(updated),
                start_thumbnails=lambda: owner.refreshed.append(path),
            )
            Window.apply_visible_entry(owner, basic_entry(path))
            self.assertEqual(model.thumbnails[path], 'preview')
            self.assertTrue(model.icon_at_insert[-1])
            self.assertFalse(getattr(pane, 'preview_dirty', False))

            # A changed file invalidates its preview, then the watcher job
            # schedules regeneration without needing a manual F5.
            path.write_bytes(b'new image data')
            Window.apply_visible_entry(owner, basic_entry(path))
            self.assertNotIn(path, model.thumbnails)
            self.assertTrue(pane.preview_dirty)
            Window.refresh_changed_previews(owner)
            self.assertEqual(owner.refreshed, [path])
            self.assertFalse(pane.preview_dirty)


if __name__ == '__main__':
    unittest.main()
