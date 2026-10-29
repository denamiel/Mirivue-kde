"""File-view options and incremental arrivals invalidate native drawing data."""
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import Qt, QItemSelectionModel
    from PySide6.QtGui import QIcon, QPixmap, QColor, QPalette
    from PySide6.QtWidgets import QApplication, QTableView
    from mirivue.app import VideoModel, FileSortProxy
    from mirivue.metadata import basic_entry
    from mirivue.item_presentation import map_file_index, _load_library
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 indisponible')
class TestPresentationFileUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        if _load_library() is None:
            raise unittest.SkipTest('Module Qt de présentation non compilé')

    def make_view(self, root):
        model = VideoModel()
        for name in ('a.txt', 'b.txt', 'c.txt'):
            (root / name).write_text(name)
        model.add_preliminary([basic_entry(root / name) for name in ('a.txt', 'b.txt', 'c.txt')])
        proxy = FileSortProxy()
        proxy.setSourceModel(model)
        table = QTableView()
        table.setModel(proxy)
        return model, proxy, table

    def test_arrival_removal_and_sort_preserve_selected_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model, proxy, table = self.make_view(root)
            selection = table.selectionModel()
            selected = map_file_index(proxy, model.index(1, 0))
            selection.select(selected, QItemSelectionModel.SelectionFlag.Select)
            model.remove_paths([root / 'a.txt'])
            proxy.sort(0, Qt.SortOrder.DescendingOrder)
            self.assertEqual([index.data() for index in selection.selectedIndexes()], ['b.txt'])
            (root / 'd.txt').write_text('new')
            model.add_preliminary([basic_entry(root / 'd.txt')])
            arriving = map_file_index(proxy, model.index(2, 0))
            selection.select(arriving, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            self.assertEqual([index.data() for index in selection.selectedIndexes()], ['d.txt'])
            table.close()

    def test_thumbnail_toggle_and_palette_change_refresh_cached_roles(self):
        with tempfile.TemporaryDirectory() as temporary:
            model, proxy, table = self.make_view(Path(temporary))
            index = proxy.index(0, 0)
            original = index.data(Qt.ItemDataRole.DecorationRole)
            pixmap = QPixmap(8, 8)
            pixmap.fill(QColor('red'))
            thumbnail = QIcon(pixmap)
            model.thumbnails[model.rows[0].path] = thumbnail
            model.show_thumbnails = True
            self.assertEqual(index.data(Qt.ItemDataRole.DecorationRole).cacheKey(), thumbnail.cacheKey())
            model.show_thumbnails = False
            self.assertEqual(index.data(Qt.ItemDataRole.DecorationRole).cacheKey(), original.cacheKey())
            model.rows[0].error = 'example'
            model.semantic_color = lambda meaning: QColor('blue' if model.semantic_color_group == QPalette.ColorGroup.Active else 'gray')
            model.dataChanged.emit(model.index(0, 0), model.index(0, 0))
            self.assertIsNone(index.data(Qt.ItemDataRole.ForegroundRole))
            model.semantic_color_group = QPalette.ColorGroup.Inactive
            self.assertIsNone(index.data(Qt.ItemDataRole.ForegroundRole))
            table.close()


if __name__ == '__main__':
    unittest.main()
