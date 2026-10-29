"""Exercise the real compiled Dolphin engine, including native input and paint."""
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QUrl, QSize, QItemSelectionModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QColor, QContextMenuEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QTextEdit, QTableView, QListView, QWidget, QStackedWidget
from mirivue.dolphin_view import DetailsView, IconView


class CountedModel(QStandardItemModel):
    reads = 0
    icon_reads = 0
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        self.reads += 1
        if role == Qt.ItemDataRole.DecorationRole: self.icon_reads += 1
        return super().data(index, role)


class TestDolphinViewEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_view(self, count=20, columns=8):
        model = CountedModel()
        model.setHorizontalHeaderLabels(['Nom'] + [f'Champ {c}' for c in range(1, columns)])
        for r in range(count):
            row = [QStandardItem(f'film {r:03}.mkv')] + [QStandardItem(f'{r}-{c}') for c in range(1, columns)]
            row[0].setData(QUrl.fromLocalFile(f'/tmp/film {r:03}.mkv'), Qt.ItemDataRole.UserRole + 43)
            model.appendRow(row)
        view = DetailsView()
        view.setModel(model)
        view.resize(900, 650)
        view.show()
        self.app.processEvents()
        self.app.processEvents()
        self.addCleanup(view.deleteLater)
        return view, model

    def test_native_objects_and_all_layouts_share_one_engine_and_selection(self):
        view, model = self.make_view()
        stack = QStackedWidget()
        stack.addWidget(view)
        icons, compact = IconView(), IconView()
        icons.setModel(model)
        icons.setViewMode(QListView.ViewMode.IconMode)
        compact.setModel(model)
        compact.setViewMode(QListView.ViewMode.ListMode)
        stack.addWidget(icons)
        stack.addWidget(compact)
        stack.resize(900, 650)
        stack.show()
        self.addCleanup(stack.deleteLater)
        backend = view._backend
        view.selectionModel().select(model.index(2, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        for facade, layout in ((view, 2), (icons, 0), (compact, 1), (view, 2)):
            stack.setCurrentWidget(facade)
            self.app.processEvents()
            self.app.processEvents()
            self.assertIs(facade._backend, backend)
            self.assertEqual(backend.query()['layout'], layout)
            self.assertEqual(backend.query()['headerVisible'], facade is view)
            self.assertEqual([i.row() for i in facade.selectionModel().selectedRows()], [2])
            self.assertFalse(isinstance(facade, (QTableView, QListView)))
        # After leaving Icons, all Details header columns must be restored.
        from PySide6.QtCore import QPoint
        x = round(backend.query(op='widths')['widths'][0]) + 8
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(x, 8))
        self.app.processEvents()
        self.assertEqual(view.horizontalHeader().sortIndicatorSection(), 1)
        stack.setCurrentWidget(icons)
        self.app.processEvents()
        self.assertLess(backend.query()['itemWidth'], icons.viewport().width() / 2)
        self.assertEqual(icons.visualRect(model.index(0, 0)).y(), icons.visualRect(model.index(1, 0)).y())

    def test_warm_resize_and_repaint_do_not_request_python_model_data(self):
        view, model = self.make_view(80, 38)
        view.configure_details(True, True)
        for _ in range(3): self.app.processEvents()
        self.assertLess(model.icon_reads, model.rowCount())
        model.reads = 0
        for n in range(40):
            view.resize(650 + (n % 8)*25, 600)
            self.app.processEvents()
        self.assertEqual(model.reads, 0)
        self.assertGreater(view._backend.query()['visibleObjects'], 0)

    def test_insert_remove_sort_and_data_update_preserve_file_selection(self):
        view, model = self.make_view(12)
        view.selectionModel().select(model.index(5, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        chosen = model.item(5).text()
        model.removeRow(0)
        model.insertRow(0, [QStandardItem('aaa new.mkv')])
        model.sort(0, Qt.SortOrder.DescendingOrder)
        self.app.processEvents()
        self.assertEqual([i.data() for i in view.selectionModel().selectedRows()], [chosen])
        self.assertEqual(view._backend.query()['count'], model.rowCount())
        self.assertEqual(view._backend.query(op='selected')['rows'],
                         [view.selectionModel().selectedRows()[0].row()])
        index = view.selectionModel().selectedRows()[0]
        model.setData(model.index(index.row(), 2), '01:23:45')
        self.app.processEvents()
        self.assertEqual(view._backend.query()['count'], 12)
        self.assertEqual(view.indexAt(view.visualRect(index).center()).row(), index.row())

    def test_native_mouse_keyboard_activation_and_context_position(self):
        view, model = self.make_view(6)
        activated, contexts = [], []
        view.activated.connect(lambda i: activated.append(i.row()))
        view.customContextMenuRequested.connect(contexts.append)
        point = view.visualRect(model.index(1, 0)).center()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.app.processEvents()
        self.assertEqual([i.row() for i in view.selectionModel().selectedRows()], [1])
        QTest.keyClick(view.viewport(), Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertEqual(activated[-1], 1)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.RightButton, pos=point)
        self.app.sendEvent(view.viewport(), QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, view.viewport().mapToGlobal(point)))
        self.app.processEvents()
        self.assertTrue(contexts)
        self.assertLess((contexts[-1]-point).manhattanLength(), 4)

    def test_rename_preserves_extension_and_live_editability(self):
        view, model = self.make_view(2)
        index = model.index(0, 0)
        view.edit(index)
        self.app.processEvents()
        editor = view.findChild(QTextEdit)
        self.assertIsNotNone(editor)
        self.assertEqual(editor.textCursor().selectedText(), 'film 000')
        editor.insertPlainText('nouveau')
        QTest.keyClick(editor, Qt.Key.Key_Return)
        self.app.processEvents()
        self.app.processEvents()
        self.assertEqual(model.index(0, 0).data(), 'nouveau.mkv')
        model.item(0).setEditable(False)
        view.edit(model.index(0, 0))
        self.app.processEvents()
        self.assertFalse(any(e.isVisible() for e in view.findChildren(QTextEdit)))

    def test_visible_widget_receives_new_columns_duration_icons_colors_and_url(self):
        view, model = self.make_view(2)
        view.setColumnHidden(2, True)
        self.app.processEvents()
        model.setData(model.index(0, 2), '00:21:30')
        view.setColumnHidden(2, False)
        self.app.processEvents()
        self.assertIn('00:21:30', view._backend.query(op='item', row=0)['cells'])
        before = view._backend.query(op='item', row=0)['iconKey']
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.red)
        model.item(0).setIcon(QIcon(pixmap))
        model.item(0).setForeground(QColor('red'))
        new_url = QUrl.fromLocalFile('/tmp/nouveau.mkv')
        model.item(0).setData(new_url, Qt.ItemDataRole.UserRole + 43)
        self.app.processEvents()
        snapshot = view._backend.query(op='item', row=0)
        self.assertNotEqual(snapshot['iconKey'], before)
        self.assertEqual(snapshot['color'], QColor('red').name())
        self.assertEqual(snapshot['url'], new_url.toString())
        view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.app.processEvents()
        self.assertEqual(view._backend.query(op='item', row=0)['sortColumn'], 2)
        self.assertEqual(view._backend.query(op='item', row=0)['sortOrder'], 1)

    def test_drop_preserves_requested_action_and_internal_mime(self):
        from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
        from PySide6.QtCore import QPoint, QPointF, QMimeData
        view, model = self.make_view(2)
        events = []
        def dropped(event):
            events.append((event.mimeData().urls(), event.keyboardModifiers()))
            event.setDropAction(Qt.DropAction.LinkAction)
            event.accept()
        view.drop_handler = dropped
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile('/tmp/disposable.txt')])
        point = QPoint(20, view.viewport().height() - 30)
        actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction
        modifiers = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        for event in (QDragEnterEvent(point, actions, mime, Qt.MouseButton.LeftButton, modifiers),
                      QDragMoveEvent(point, actions, mime, Qt.MouseButton.LeftButton, modifiers),
                      QDropEvent(QPointF(point), actions, mime, Qt.MouseButton.LeftButton, modifiers)):
            self.app.sendEvent(view.viewport(), event)
            # Injecting Drop directly can reach the handler even when DragMove
            # was rejected. A real desktop would never deliver that drop.
            self.assertTrue(event.isAccepted())
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], mime.urls())
        self.assertEqual(event.dropAction(), Qt.DropAction.LinkAction)

    def test_empty_and_populated_backgrounds_accept_drag_hover_in_all_views(self):
        from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent
        from PySide6.QtCore import QPoint, QMimeData
        for count in (0, 2):
            details, model = self.make_view(count)
            stack = QStackedWidget()
            icons, compact = IconView(), IconView()
            for facade in (details, icons, compact):
                facade.setModel(model)
                stack.addWidget(facade)
            icons.setViewMode(QListView.ViewMode.IconMode)
            compact.setViewMode(QListView.ViewMode.ListMode)
            stack.resize(650, 450)
            stack.show()
            self.addCleanup(stack.deleteLater)
            for facade in (details, icons, compact):
                with self.subTest(rows=count, mode=facade.mode):
                    stack.setCurrentWidget(facade)
                    self.app.processEvents()
                    self.app.processEvents()
                    mime = QMimeData()
                    mime.setUrls([QUrl.fromLocalFile('/tmp/disposable-source.txt')])
                    point = QPoint(250, 350)
                    actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
                    for event in (QDragEnterEvent(point, actions, mime, Qt.LeftButton, Qt.ControlModifier),
                                  QDragMoveEvent(point, actions, mime, Qt.LeftButton, Qt.ControlModifier)):
                        self.app.sendEvent(facade.viewport(), event)
                        self.assertTrue(event.isAccepted())


    def test_tab_in_native_editor_commits_and_opens_next_file(self):
        view, model = self.make_view(3)
        view.edit(model.index(0, 0))
        self.app.processEvents()
        editor = view.findChild(QTextEdit)
        editor.insertPlainText('premier')
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        self.app.processEvents()
        self.app.processEvents()
        self.assertEqual(model.index(0, 0).data(), 'premier.mkv')
        editors = [e for e in view.findChildren(QTextEdit) if e.isVisible()]
        self.assertEqual(len(editors), 1)
        self.assertEqual(editors[0].toPlainText(), 'film 001.mkv')
        self.assertEqual(view.selectionModel().currentIndex().row(), 1)


    def test_native_event_gate_only_forwards_requested_interactions(self):
        from PySide6.QtCore import QObject, QEvent
        from mirivue.native_events import install_event_gate
        class Listener(QObject):
            def __init__(self):
                super().__init__()
                self.calls = []
            def eventFilter(self, watched, event):
                self.calls.append(event.type())
                return False
        target, listener = QWidget(), Listener()
        gate = install_event_gate(target, listener, [QEvent.Type.KeyPress])
        self.app.sendEvent(target, QEvent(QEvent.Type.User))
        QTest.keyClick(target, Qt.Key.Key_A)
        self.assertEqual(listener.calls, [QEvent.Type.KeyPress])
        target.removeEventFilter(gate)

    def test_custom_column_fill_tracks_width_without_changing_saved_base_widths(self):
        view, model = self.make_view(6, 3)
        for c in range(3): view.setColumnWidth(c, 100)
        view.configure_details(False, False)
        self.app.processEvents()
        self.assertEqual(round(view._backend.query(op='widths')['widths'][0]), 100)
        view.configure_details(False, True)
        self.app.processEvents()
        before = view._backend.query(op='widths')['widths'][0]
        self.assertGreater(before, 100)
        view.resize(view.width() + 120, view.height())
        self.app.processEvents()
        after = view._backend.query(op='widths')['widths'][0]
        self.assertAlmostEqual(after - before, 120, delta=2)
        self.assertEqual(view.horizontalHeader().sectionSize(0), 100)
        view.configure_details(False, False)
        self.app.processEvents()
        self.assertEqual(round(view._backend.query(op='widths')['widths'][0]), 100)
