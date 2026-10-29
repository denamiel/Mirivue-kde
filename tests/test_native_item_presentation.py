"""Exercise the compiled presentation path, not source-code string matches."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QPersistentModelIndex
    from PySide6.QtGui import QStandardItemModel, QStandardItem
    from PySide6.QtWidgets import QApplication, QSplitter, QTableView, QHeaderView
    from PySide6.QtTest import QAbstractItemModelTester
    from mirivue.item_presentation import (presentation_model, install_details_header,
                                         configure_details_header, _load_library)
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 indisponible')
class TestNativeItemPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        if _load_library() is None:
            raise unittest.SkipTest('Compiler le module de présentation Qt pour ces tests')

    def pair(self, rows=8, columns=6):
        class CountedModel(QAbstractTableModel):
            calls = 0
            checks = 0
            editable = True

            def __init__(self):
                super().__init__()
                self.values = [[f'{r}:{c}' for c in range(columns)] for r in range(rows)]

            def rowCount(self, parent=QModelIndex()):
                self.checks += 1
                return 0 if parent.isValid() else len(self.values)

            def columnCount(self, parent=QModelIndex()):
                self.checks += 1
                return 0 if parent.isValid() else columns

            def data(self, index, role=Qt.ItemDataRole.DisplayRole):
                self.calls += 1
                return self.values[index.row()][index.column()] if role == Qt.ItemDataRole.DisplayRole else None

            def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
                if not self.editable:
                    return False
                self.values[index.row()][index.column()] = value
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
                return True

            def flags(self, index):
                value = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                return value | Qt.ItemFlag.ItemIsEditable if self.editable else value

        source = CountedModel()
        owner = QTableView()
        cache = presentation_model(source, owner)
        return source, cache, owner

    def test_warm_paint_values_and_empty_roles_need_no_source_calls(self):
        source, cache, owner = self.pair()
        roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.FontRole,
                 Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.BackgroundRole]
        for role in roles:
            cache.index(3, 2).data(role)
        source.calls = source.checks = 0
        for _ in range(100):
            for role in roles:
                cache.index(3, 2).data(role)
            cache.rowCount()
            cache.columnCount()
        self.assertEqual((source.calls, source.checks), (0, 0))

    def test_changed_data_editing_and_operation_locks_stay_live(self):
        source, cache, owner = self.pair()
        index = cache.index(1, 0)
        self.assertEqual(index.data(), '1:0')
        self.assertTrue(cache.setData(index, 'renommé'))
        self.assertEqual(index.data(), 'renommé')
        source.editable = False
        self.assertFalse(index.flags() & Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(cache.setData(index, 'refusé'))
        self.assertEqual(index.data(), 'renommé')

    def test_incremental_removal_insert_and_reset_keep_cache_and_selection_coherent(self):
        source, cache, owner = self.pair()
        tester = QAbstractItemModelTester(cache, QAbstractItemModelTester.FailureReportingMode.Fatal)
        self.assertEqual(cache.index(4, 1).data(), '4:1')
        persistent = QPersistentModelIndex(cache.index(4, 1))
        source.beginRemoveRows(QModelIndex(), 0, 0)
        source.values.pop(0)
        source.endRemoveRows()
        source.calls = 0
        self.assertEqual(persistent.row(), 3)
        self.assertEqual(cache.index(3, 1).data(), '4:1')
        self.assertEqual(source.calls, 0)
        source.beginInsertRows(QModelIndex(), 0, 0)
        source.values.insert(0, ['new'] * 6)
        source.endInsertRows()
        self.assertEqual(persistent.row(), 4)
        self.assertEqual(cache.index(4, 1).data(), '4:1')
        source.beginResetModel()
        source.values = [['reset'] * 6]
        source.endResetModel()
        self.assertFalse(persistent.isValid())
        self.assertEqual(cache.rowCount(), 1)
        self.assertEqual(cache.index(0, 1).data(), 'reset')

    def test_layout_reordering_preserves_persistent_file_identity(self):
        source = QStandardItemModel()
        source.appendRow(QStandardItem('b'))
        source.appendRow(QStandardItem('a'))
        owner = QTableView()
        cache = presentation_model(source, owner)
        tester = QAbstractItemModelTester(cache, QAbstractItemModelTester.FailureReportingMode.Fatal)
        saved = QPersistentModelIndex(cache.index(0, 0))
        self.assertEqual(saved.data(), 'b')
        source.sort(0)
        self.assertEqual(saved.row(), 1)
        self.assertEqual(saved.data(), 'b')

    def test_cache_is_bounded_and_evicted_values_are_reloaded(self):
        source, cache, owner = self.pair(5000, 1)
        cache.index(0, 0).data()
        for row in range(1, 5000):
            cache.index(row, 0).data()
        source.calls = 0
        self.assertEqual(cache.index(0, 0).data(), '0:0')
        self.assertEqual(source.calls, 1)

    def test_details_header_only_resizes_name_without_remeasuring_cells(self):
        source, cache, table = self.pair(40, 6)
        install_details_header(table)
        table.setModel(cache)
        table.resize(1100, 500)
        for column in range(6):
            table.setColumnWidth(column, 300 if column == 0 else 90)
        table.show()
        self.application.processEvents()
        configure_details_header(table, True, True, capture=True)
        other_widths = [table.columnWidth(c) for c in range(1, 6)]
        wide_name = table.columnWidth(0)
        source.calls = 0
        for width in (900, 800, 1000, 850, 1100):
            table.resize(width, 500)
            self.application.processEvents()
        self.assertEqual([table.columnWidth(c) for c in range(1, 6)], other_widths)
        self.assertFalse(table.horizontalHeader().stretchLastSection())
        self.assertEqual(table.columnWidth(0), wide_name)
        self.assertEqual(source.calls, 0)
        configure_details_header(table, False, False, capture=True)
        custom = [table.columnWidth(c) for c in range(6)]
        for width in (800, 1000, 850, 1100):
            table.resize(width, 500)
            self.application.processEvents()
        self.assertEqual([table.columnWidth(c) for c in range(6)], custom)
        table.close()


if __name__ == '__main__':
    unittest.main()
