"""Keep file data in Python and repeated painting in native Qt.

The identity mapping preserves source row numbers. View selections must map
through both proxies when converting a file-model index to a view index.
"""
import ctypes
import os

import shiboken6
from PySide6.QtCore import QAbstractProxyModel, Qt
from PySide6.QtWidgets import QHeaderView

from .platform_services import services


def _load_library():
    path = (os.environ.get('MIRIVUE_TEST_PRESENTATION_LIBRARY')
            or services.tool_path('libmirivue-item-presentation.so'))
    if not path:
        return None
    library = ctypes.CDLL(path)
    library.mirivue_item_presentation_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    library.mirivue_item_presentation_create.restype = ctypes.c_void_p
    library.mirivue_details_header_create.argtypes = [ctypes.c_void_p]
    library.mirivue_details_header_create.restype = ctypes.c_void_p
    library.mirivue_details_header_configure.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                       ctypes.c_int, ctypes.c_int]
    library.mirivue_details_header_configure.restype = None
    library.mirivue_details_header_is_adjusting.argtypes = [ctypes.c_void_p]
    library.mirivue_details_header_is_adjusting.restype = ctypes.c_int
    return library


def presentation_model(source, parent):
    library = _load_library()
    if library is None:
        return source  # Source-only environments can run without compiled KDE tools.
    pointer = library.mirivue_item_presentation_create(
        shiboken6.getCppPointer(source)[0], shiboken6.getCppPointer(parent)[0])
    if not pointer:
        raise RuntimeError('Impossible de créer le modèle natif de présentation.')
    model = shiboken6.wrapInstance(pointer, QAbstractProxyModel)
    model._mirivue_library = library
    model._mirivue_source = source
    return model


def install_details_header(table):
    library = _load_library()
    if library is None:
        return
    pointer = library.mirivue_details_header_create(shiboken6.getCppPointer(table)[0])
    if not pointer:
        raise RuntimeError('Impossible de créer l’en-tête natif de la vue Détails.')
    header = shiboken6.wrapInstance(pointer, QHeaderView)
    table.setHorizontalHeader(header)
    table._mirivue_header = (library, pointer)


def suspend_details_header(table):
    if hasattr(table, 'configure_details'):
        return
    native = getattr(table, '_mirivue_header', None)
    if native:
        native[0].mirivue_details_header_configure(native[1], -1, 0, 0)


def configure_details_header(table, automatic, fill, capture=False):
    if hasattr(table, 'configure_details'):
        table.configure_details(automatic, fill, capture)
        return
    native = getattr(table, '_mirivue_header', None)
    # Stretching the final metadata field differs from Dolphin's Name sizing.
    table.horizontalHeader().setStretchLastSection(False)
    if native:
        native[0].mirivue_details_header_configure(native[1], automatic, fill, capture)


def details_header_adjusting(table):
    if hasattr(table, '_backend') and table._backend is not None:
        return table._backend.adjusting
    native = getattr(table, '_mirivue_header', None)
    return bool(native and native[0].mirivue_details_header_is_adjusting(native[1]))


class PresentationStateMixin:
    """Notify Qt when display options change without changing file data."""

    @property
    def show_thumbnails(self):
        return self._show_thumbnails

    @show_thumbnails.setter
    def show_thumbnails(self, value):
        changed = bool(value) != getattr(self, '_show_thumbnails', False)
        self._show_thumbnails = bool(value)
        if changed and self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows)-1, 0),
                                  [Qt.ItemDataRole.DecorationRole])

    @property
    def semantic_color_group(self):
        return self._semantic_color_group

    @semantic_color_group.setter
    def semantic_color_group(self, value):
        changed = value != getattr(self, '_semantic_color_group', value)
        self._semantic_color_group = value
        if changed and self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows)-1, 10),
                                  [Qt.ItemDataRole.ForegroundRole])

    def invalidate_style(self):
        self.row_icons.clear()
        self.mime_icons.clear()
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows)-1, self.columnCount()-1),
                                  [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.ForegroundRole,
                                   Qt.ItemDataRole.FontRole])



def map_file_index(proxy, index):
    """Convert a domain index through the optional native presentation model."""
    presentation = getattr(proxy, 'presentation', None)
    if presentation is not None and presentation is not proxy.file_model:
        index = presentation.mapFromSource(index)
    return proxy.mapFromSource(index)
