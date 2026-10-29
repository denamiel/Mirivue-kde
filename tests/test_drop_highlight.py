"""A drag over the view background must not colour the entire file pane."""
import os
import unittest

try:
    from PySide6.QtCore import QModelIndex
    from PySide6.QtGui import QStandardItem, QStandardItemModel
    from PySide6.QtWidgets import QApplication
    from mirivue.selection import DetailsView
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is unavailable on this machine')
class TestDropHighlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.app = QApplication.instance() or QApplication([])

    def test_background_drop_stays_valid_without_a_viewport_overlay(self):
        view = DetailsView()
        model = QStandardItemModel()
        model.appendRow(QStandardItem('folder'))
        view.setModel(model)
        view.resize(400, 200)
        view.show()
        self.app.processEvents()

        view.set_drop_highlight(model.index(0, 0))
        self.assertFalse(hasattr(view, 'drop_band'))
        self.assertLess(view.visualRect(model.index(0, 0)).height(), view.viewport().height())
        view.set_drop_highlight(QModelIndex())
        view.set_drop_highlight(None)
        self.assertFalse(hasattr(view, 'drop_band'))
        self.assertEqual(view._backend.query()['engine'], 'KStandardItemListView')
        view.close()
