"""One Dolphin item engine per pane; compatibility controls do not paint files.

The hidden QHeaderView only serializes existing column preferences. The visible
header, selection, layout, scrolling, rename editor and item drawing are KDE's.
"""
import ctypes
import json
import os
import uuid
import weakref
from pathlib import Path

import shiboken6
from PySide6.QtCore import (Qt, Signal, QObject, QEvent, QPoint, QPointF, QRect,
                            QSize, QModelIndex, QItemSelectionModel, QTimer, QMimeData)
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHeaderView, QListView, QAbstractScrollArea, QToolTip
from PySide6.QtCore import QUrl
from .platform_services import services

_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p)
_library = None
_backends = weakref.WeakValueDictionary()


def _load():
    global _library
    if _library is None:
        path = os.environ.get('MIRIVUE_TEST_DOLPHIN_LIBRARY') or services.tool_path('libmirivue-dolphin-view.so')
        if not path:
            raise RuntimeError('Le moteur de vues KDE natif est absent. Recompilez les composants de Mirivue.')
        library = ctypes.CDLL(path)
        for name, args, result in (
            ('create', [ctypes.c_void_p]*3 + [_CALLBACK], ctypes.c_void_p),
            ('widget', [ctypes.c_void_p], ctypes.c_void_p),
            ('canvas', [ctypes.c_void_p], ctypes.c_void_p),
            ('configure', [ctypes.c_void_p, ctypes.c_char_p], None),
            ('query', [ctypes.c_void_p, ctypes.c_char_p], ctypes.c_char_p),
            ('scroll', [ctypes.c_void_p, ctypes.c_int], None),
            ('edit', [ctypes.c_void_p, ctypes.c_int], None),
            ('set_active', [ctypes.c_void_p, ctypes.c_int], None),
        ):
            function = getattr(library, 'mirivue_dolphin_' + name)
            function.argtypes, function.restype = args, result
        _library = library
    return _library


def _pointer(obj):
    return shiboken6.getCppPointer(obj)[0]


class _Drop:
    def __init__(self, message):
        self.message = message
        self.mime = QMimeData()
        self.mime.setUrls([QUrl(value) for value in message['urls']])
        if message['internal']:
            self.mime.setData('application/x-mirivue-files', b'1')
        self.accepted = False
    def source(self):
        backend = _backends.get(self.message.get('sourcePane'))
        return backend.active if backend is not None else None
    def mimeData(self): return self.mime
    def position(self): return QPointF(self.message['x'], self.message['y'])
    def type(self): return QEvent.Type.Drop
    def possibleActions(self): return Qt.DropAction(self.message['actions'])
    def proposedAction(self): return Qt.DropAction(self.message['proposed'])
    def keyboardModifiers(self): return Qt.KeyboardModifier(self.message['modifiers'])
    modifiers = keyboardModifiers
    def setDropAction(self, action): self.action = action
    def accept(self): self.accepted = True
    def ignore(self): self.accepted = False


class _Header(QHeaderView):
    def __init__(self, backend):
        super().__init__(Qt.Orientation.Horizontal)
        self.backend = backend
        self.hide()
    def restoreState(self, state):
        restored = super().restoreState(state)
        for column in getattr(self.backend.model, 'retired_columns', ()):
            self.setSectionHidden(column, True)
        if self.sortIndicatorSection() in getattr(self.backend.model, 'retired_columns', ()):
            self.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        return restored
    def mapToGlobal(self, point):
        return self.backend.canvas.mapToGlobal(point) if self.backend.active else super().mapToGlobal(point)


class _Backend(QObject):
    def __init__(self, model, owner):
        super().__init__()
        self.model, self.active, self.facades = model, None, []
        self.drag_token = uuid.uuid4().hex
        _backends[self.drag_token] = self
        self.selection = QItemSelectionModel(model, self)
        self.library = _load()
        self.callback = _CALLBACK(self.dispatch)
        self.handle = self.library.mirivue_dolphin_create(_pointer(model), _pointer(self.selection),
                                                       _pointer(owner), self.callback)
        self.widget = shiboken6.wrapInstance(self.library.mirivue_dolphin_widget(self.handle), QAbstractScrollArea)
        self.setParent(self.widget)
        self.widget._mirivue_bridge = self
        # The native bridge returns QGraphicsView::viewport(), a QWidget.
        # Wrapping it as QAbstractScrollArea is an invalid C++ downcast and
        # can leave Shiboken's wrapper cache with an incorrect object type.
        self.canvas = shiboken6.wrapInstance(self.library.mirivue_dolphin_canvas(self.handle), QWidget)
        # wrapInstance() does not invalidate this C++-owned viewport wrapper
        # when its native parent is deleted. Never retain its old address in
        # Shiboken's cache: Qt may reuse that address for a new widget.
        self.canvas.destroyed.connect(lambda *_: shiboken6.invalidate(self.canvas))
        self.canvas.installEventFilter(self)
        self.header = _Header(self)
        self.header.setParent(self.widget)
        self.header.hide()
        self.header.setModel(model)
        self.header.setSectionsMovable(True)
        self.header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.header.sectionResized.connect(self.schedule)
        self.header.sectionMoved.connect(self.schedule)
        self.header.geometriesChanged.connect(self.schedule)
        self.header.sortIndicatorChanged.connect(self.sort)
        self.vertical = QHeaderView(Qt.Orientation.Vertical, self.widget)
        self.vertical.hide()
        self.vertical.setDefaultSectionSize(28)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.configure)
        self.automatic, self.fill, self.adjusting = True, True, False
        self.last_configuration = None
        self.widget.hide()
    def query(self, **values):
        return json.loads(self.library.mirivue_dolphin_query(self.handle, json.dumps(values).encode()))
    def attach(self, facade):
        if self.active is facade:
            return
        self.active = facade
        self.widget.setParent(facade)
        facade.layout().addWidget(self.widget)
        self.widget.setPalette(facade.palette())
        self.widget.setFont(facade.font())
        facade.setFocusProxy(self.widget)
        self.widget.show()
        self.configure()
    def schedule(self, *_):
        if not self.adjusting:
            self.timer.start(0)
    def configure(self):
        view = self.active
        if view is None:
            return
        header = self.header
        retired = getattr(self.model, 'retired_columns', ())
        for column in retired:
            if not header.isSectionHidden(column):
                header.setSectionHidden(column, True)
        window = view.window()
        pane = next((p for p in getattr(window, 'panes', ()) if p.table._backend is self), None)
        if pane and pane.folder:
            from .locations import Location
            view.directory = (str(pane.folder) if Location.from_value(pane.folder).is_uri
                              else QUrl.fromLocalFile(str(pane.folder)).toString())
        if view.mode == 0:
            columns = [header.logicalIndex(n) for n in range(header.count())
                       if not header.isSectionHidden(header.logicalIndex(n))]
        else:
            columns = [0] + [column for column in view.extra_columns if column not in retired]
        config = dict(mode=view.mode, columns=columns, dragToken=self.drag_token, iconSize=view._icon_size.width(),
                      widths=[header.sectionSize(c) for c in range(header.count())],
                      automatic=self.automatic, fill=self.fill, empty=view.empty_message,
                      sortColumn=header.sortIndicatorSection(), sortOrder=header.sortIndicatorOrder().value,
                      alternate=view._alternate, directory=view.directory,
                      grouped=getattr(view, 'grouped_sorting', False))
        # A style change must also reach the native widgets. No filesystem or
        # data queries are performed here during a pane's resize.
        self.widget.setPalette(view.palette())
        self.widget.setFont(view.font())
        self.adjusting = True
        try:
            self.library.mirivue_dolphin_configure(self.handle, json.dumps(config).encode())
            self.last_configuration = config
        finally:
            self.adjusting = False
    def sort(self, column, order):
        self.model.sort(column, order)
        self.schedule()
    def dispatch(self, raw):
        try:
            message = json.loads(raw)
            view = self.active
            if view is None:
                return 0
            event, row = message['event'], message.get('row', -1)
            index = self.model.index(row, 0)
            if event == 'press':
                if index.isValid(): view.pressed.emit(index)
                elif view.activation_handler: view.activation_handler()
            elif event == 'activate': view.activated.emit(index)
            elif event == 'activate-selection':
                window = view.window()
                if hasattr(window, 'open_selected'): window.open_selected()
            elif event == 'middle' and index.isValid() and index.data(Qt.ItemDataRole.UserRole + 42):
                url = index.data(Qt.ItemDataRole.UserRole + 43)
                window = view.window()
                if hasattr(window, 'open_new_tab'):
                    window.open_new_tab(url.toLocalFile() if url.isLocalFile() else url.toString(),
                                        active=bool(message.get('modifiers', 0) & Qt.KeyboardModifier.ShiftModifier.value))
            elif event == 'context':
                view.customContextMenuRequested.emit(QPoint(message['x'], message['y']))
            elif event == 'header-context':
                self.header.customContextMenuRequested.emit(QPoint(message['x'], message['y']))
            elif event == 'drop':
                drop = _Drop(message)
                if view.drop_handler: view.drop_handler(drop)
                return (getattr(drop, 'action', drop.proposedAction()).value if drop.accepted else 0)
            elif event == 'can-drag':
                window = view.window()
                if getattr(window, 'scanning', False): return 0
                paths = []
                for selected_row in message['rows']:
                    url = self.model.index(selected_row, 0).data(Qt.ItemDataRole.UserRole + 43)
                    paths.append(Path(url.toLocalFile()) if url.isLocalFile() else url.toString())
                return int(not hasattr(window, 'movement_locked') or not window.movement_locked(paths))
            elif event == 'column-width' and not self.adjusting:
                self.adjusting = True
                try:
                    window = view.window()
                    pane = next((p for p in getattr(window, 'panes', ()) if p.table._backend is self), None)
                    window._column_resize_pane = pane
                    widths = self.query(op='widths')['widths']
                    self.automatic = False
                    for column, width in enumerate(widths):
                        if width > 0: self.header.resizeSection(column, round(width))
                    if pane:
                        pane.column_width_mode = 'custom'
                        window.save_pane_column_state(pane)
                    window._column_resize_pane = None
                finally: self.adjusting = False
            elif event == 'columns-moved' and not self.adjusting:
                self.adjusting = True
                try:
                    for visual, column in enumerate(message['columns']):
                        self.header.moveSection(self.header.visualIndex(column), visual)
                finally: self.adjusting = False
            elif event == 'sort' and not self.adjusting:
                self.header.setSortIndicator(message['column'], Qt.SortOrder(message['order']))
            return 1
        except Exception:
            import traceback
            traceback.print_exc()
            return 0
    def eventFilter(self, watched, event):
        view = getattr(self, 'active', None)
        if view and watched is self.canvas and event.type() == QEvent.Type.ToolTip:
            index = view.indexAt(event.pos())
            text = index.data(Qt.ItemDataRole.ToolTipRole) if index.isValid() else ''
            if text:
                QToolTip.showText(event.globalPos(), str(text), self.canvas)
            else:
                QToolTip.hideText()
            return True
        return super().eventFilter(watched, event)


class DolphinView(QWidget):
    activated = Signal(QModelIndex)
    pressed = Signal(QModelIndex)
    drag_handler = drop_handler = activation_handler = open_handler = None
    context_menu_handler = None
    mode = 0

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QWidget(self)
        self._placeholder.hide()
        self._backend = None
        self._icon_size = QSize(22, 22)
        self._grid_size = QSize()
        self._alternate = True
        self._empty_message = ''
        self.extra_columns = ()
        self.directory = ''
        self._horizontal_policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded
        self.setMinimumWidth(0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    def setModel(self, model):
        backend = getattr(model, '_dolphin_backend', None)
        if backend is None:
            backend = model._dolphin_backend = _Backend(model, self)
        self._backend = backend
        backend.facades.append(self)
        if self.mode == 0 and backend.active is None:
            backend.attach(self)
    def model(self): return self._backend.model if self._backend else None
    def selectionModel(self): return self._backend.selection
    def horizontalHeader(self): return self._backend.header
    def verticalHeader(self): return self._backend.vertical
    def viewport(self):
        return self._backend.canvas if self._backend and self._backend.active is self else self._placeholder
    def currentIndex(self): return self.selectionModel().currentIndex()
    def setCurrentIndex(self, index):
        self.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
    def clearSelection(self): self.selectionModel().clearSelection()
    def selectAll(self):
        model = self.model()
        if model.rowCount():
            from PySide6.QtCore import QItemSelection
            selection = QItemSelection(model.index(0, 0), model.index(model.rowCount()-1, model.columnCount()-1))
            self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    def setColumnWidth(self, column, width): self.horizontalHeader().resizeSection(column, width)
    def columnWidth(self, column): return self.horizontalHeader().sectionSize(column)
    def setColumnHidden(self, column, hide):
        self.horizontalHeader().setSectionHidden(column, hide or column in getattr(self.model(), 'retired_columns', ()))
        self._backend.schedule()
    def isColumnHidden(self, column): return self.horizontalHeader().isSectionHidden(column)
    def sortByColumn(self, column, order):
        if column in getattr(self.model(), 'retired_columns', ()):
            column = 0
        self.horizontalHeader().setSortIndicator(column, order)
        self.model().sort(column, order)
    def setIconSize(self, size):
        self._icon_size = QSize(size)
        if self._backend: self._backend.schedule()
    def iconSize(self): return QSize(self._icon_size)
    def setGridSize(self, size): self._grid_size = QSize(size)
    def gridSize(self): return QSize(self._grid_size)
    def setAlternatingRowColors(self, value):
        self._alternate = bool(value)
        if self._backend: self._backend.schedule()
    def alternatingRowColors(self): return self._alternate
    def setPalette(self, palette):
        super().setPalette(palette)
        if self._backend and self._backend.active is self: self._backend.schedule()
    def setViewMode(self, mode):
        self.mode = 1 if mode == QListView.ViewMode.IconMode else 2
    def doItemsLayout(self):
        if self._backend: self._backend.schedule()
    def showEvent(self, event):
        super().showEvent(event)
        if self._backend: self._backend.attach(self)
    def edit(self, index, *_):
        self._backend.attach(self)
        self._backend.library.mirivue_dolphin_edit(self._backend.handle, index.row())
    def setPaneActive(self, active):
        self._backend.library.mirivue_dolphin_set_active(self._backend.handle, bool(active))
    def scrollTo(self, index, *_):
        self._backend.library.mirivue_dolphin_scroll(self._backend.handle, index.row())
    def indexAt(self, point):
        if self._backend.active is not self: return QModelIndex()
        row = self._backend.query(op='index', x=point.x(), y=point.y()).get('row', -1)
        return self.model().index(row, 0)
    def is_view_background(self, point):
        if self._backend.active is not self: return False
        return self._backend.query(op='background', x=point.x(), y=point.y()).get('background', False)
    def visualRect(self, index):
        if not index.isValid(): return QRect()
        values = self._backend.query(op='rect', row=index.row())
        return QRect(values['x'], values['y'], values['width'], values['height'])
    @property
    def empty_message(self): return self._empty_message
    @empty_message.setter
    def empty_message(self, message):
        self._empty_message = message
        if self._backend: self._backend.schedule()
    def configure_details(self, automatic, fill, capture=False):
        self._backend.automatic, self._backend.fill = bool(automatic), bool(fill)
        self._backend.schedule()
    def setHorizontalScrollBarPolicy(self, value): self._horizontal_policy = value
    def horizontalScrollBarPolicy(self): return self._horizontal_policy
    def verticalScrollBar(self): return self._backend.widget.verticalScrollBar()
    def set_drop_highlight(self, index): pass  # Dolphin owns item drop highlighting.
    def resizeColumnsToContents(self): self.configure_details(True, True)
    # Former QAbstractItemView settings whose actual behavior is owned by the
    # Dolphin controller. Kept for existing setup/tool callers, never for paint.
    def setShowGrid(self, *_): pass
    def setSortingEnabled(self, *_): pass
    def setSelectionBehavior(self, *_): pass
    def setSelectionMode(self, *_): pass
    def setEditTriggers(self, *_): pass
    def setDragDropMode(self, *_): pass
    def setDefaultDropAction(self, *_): pass
    def setDragEnabled(self, *_): pass
    def setWordWrap(self, *_): pass
    def setResizeMode(self, *_): pass
    def setMovement(self, *_): pass
    def setFlow(self, *_): pass
    def setWrapping(self, *_): pass
    def setUniformItemSizes(self, *_): pass


class DetailsView(DolphinView):
    mode = 0


class IconView(DolphinView):
    mode = 1
