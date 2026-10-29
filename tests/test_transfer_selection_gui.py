"""An arrival remains selected in every destination view after a KIO rescan."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import QSortFilterProxyModel, QUrl
    from PySide6.QtGui import QStandardItemModel, QStandardItem
    from PySide6.QtWidgets import QApplication
    from mirivue.selection import DetailsView, IconView
    from mirivue.app import Window
    from mirivue.movement import MovementMixin
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 indisponible')
class TestTransferSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_copy_and_move_select_arrivals_after_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'destination'
            destination.mkdir()
            model = QStandardItemModel()
            proxy = QSortFilterProxyModel()
            proxy.setSourceModel(model)
            views = [DetailsView(), IconView(), IconView()]
            for view in views:
                view.setModel(proxy)
            pane = SimpleNamespace(folder=str(destination), model=model, proxy=proxy,
                                   table=views[0], icons=views[1], compact=views[2])
            owner = SimpleNamespace(panes=[pane], bound_pane=pane, folder=str(destination),
                                    model=model, proxy=proxy, table=views[0], icons=views[1],
                                    compact=views[2], active_view=lambda: views[0])
            sources = [QUrl.fromLocalFile(str(Path(directory) / name)).toString()
                       for name in ('un.mkv', 'deux.mkv')]
            target = QUrl.fromLocalFile(str(destination)).toString()
            MovementMixin.remember_transfer_selection(owner, sources, target, 'copy')
            for name in ('ancien.mkv', 'un.mkv', 'deux.mkv'):
                model.appendRow(QStandardItem(name))
            model.rows = [SimpleNamespace(path=destination / name)
                          for name in ('ancien.mkv', 'un.mkv', 'deux.mkv')]
            Window.restore_transfer_selection(owner)
            for view in views:
                self.assertEqual({index.data() for index in view.selectionModel().selectedRows()},
                                 {'un.mkv', 'deux.mkv'})
            self.assertIsNone(pane.pending_transfer_selection)

            model.clear()  # The next KIO listing resets all three views.
            model.appendRow(QStandardItem('renommé.mkv'))
            model.rows = [SimpleNamespace(path=destination / 'renommé.mkv')]
            renamed = QUrl.fromLocalFile(str(destination / 'renommé.mkv')).toString()
            MovementMixin.remember_transfer_selection(owner, sources[:1], renamed, 'moveas')
            Window.restore_transfer_selection(owner)
            for view in views:
                self.assertEqual([index.data() for index in view.selectionModel().selectedRows()],
                                 ['renommé.mkv'])

    def test_local_kio_result_updates_rows_without_rescanning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_dir = root / 'destination'
            target_dir.mkdir()
            target = target_dir / 'film.mkv'
            target.write_bytes(b'copied')
            source = root / 'film.mkv'
            calls = []
            owner = SimpleNamespace(
                panes=[SimpleNamespace(scanning=False)],
                recursive=SimpleNamespace(isChecked=lambda: False),
                update_transfer_panes=lambda worker, copy: calls.append((worker.moved, copy)),
                watch_visible_directories=lambda: calls.append('watch'),
            )
            handled = MovementMixin.update_local_kio_transfer(
                owner, [QUrl.fromLocalFile(str(source)).toString()],
                QUrl.fromLocalFile(str(target_dir)).toString(), 'copy')
            self.assertTrue(handled)
            self.assertEqual(calls, [({source: target}, True), 'watch'])

    def test_navigation_does_not_select_a_matching_name_in_another_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'destination'
            destination.mkdir()
            pane = SimpleNamespace(folder=str(destination))
            owner = SimpleNamespace(panes=[pane])
            source = QUrl.fromLocalFile(str(Path(directory) / 'film.mkv')).toString()
            MovementMixin.remember_transfer_selection(
                owner, [source], QUrl.fromLocalFile(str(destination)).toString(), 'move')
            self.assertEqual(pane.pending_transfer_selection[1], {'film.mkv'})
            pane.folder = str(Path(directory) / 'ailleurs')
            self.assertNotEqual(pane.pending_transfer_selection[0], pane.folder)


if __name__ == '__main__':
    unittest.main()
