# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
# Original Mirivue implementation; behavior compared with Dolphin v26.08.2.
# No Dolphin source code is copied into this module.
"""Display-style scope, independently of media column profiles."""
from pathlib import Path
from .metadata import HEADERS
from PySide6.QtCore import QStandardPaths, QUrl, Qt


def per_folder_views(settings):
    return settings.value('view/remember-per-folder',
                          settings.value('sorting/remember-per-folder', False, type=bool), type=bool)


def special_view(settings, folder):
    url = QUrl(str(folder or ''))
    scheme = url.scheme()
    if scheme in ('trash', 'recentlyused', 'timeline'):
        return scheme
    # Dolphin's Downloads default applies in per-folder mode, not to every
    # ordinary directory when a common style is selected.
    downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    if per_folder_views(settings) and downloads and str(folder) == downloads:
        return 'downloads'
    return ''


def stored_style(settings, folder):
    special = special_view(settings, folder)
    scoped = per_folder_views(settings) or bool(special)
    if scoped:
        styles = settings.value('view/folder-styles-v1', {})
        style = styles.get(str(folder), {}) if isinstance(styles, dict) else {}
    else:
        style = settings.value('view/common-style', {})
    defaults = {}
    if special == 'trash':
        defaults = {'mode': 0, 'columns': [0, 37, 39]}
    elif special in ('recentlyused', 'timeline'):
        defaults = {'mode': 0, 'columns': [0, 37, 38], 'sort': [38, 1], 'folders_first': False, 'grouped': True}
    elif special == 'downloads':
        defaults = {'sort': [14, 1], 'folders_first': False, 'grouped': True}
    defaults.update(style if isinstance(style, dict) else {})
    return defaults


class ViewPolicyMixin:
    def set_sorting_options(self, mode, hidden_last):
        mode = mode if mode in (0, 1, 2) else 0
        self.settings.setValue('sorting/mode', mode)
        self.settings.setValue('sorting/hidden-last', bool(hidden_last))
        for tab in self._tabs:
            for pane in tab.panes:
                pane.proxy.sort_mode = mode
                pane.proxy.hidden_last = bool(hidden_last)
                pane.proxy.invalidate()

    def folder_display_style(self, folder):
        return stored_style(self.settings, folder)

    def remember_folder_display(self, folder, key, value):
        if not folder or getattr(self, '_restoring_folder_display', False):
            return
        if not per_folder_views(self.settings) and not special_view(self.settings, folder):
            common = self.settings.value('view/common-style', {})
            common = dict(common) if isinstance(common, dict) else {}
            common[key] = value
            self.settings.setValue('view/common-style', common)
            global_keys = {'hidden': 'view/hidden', 'previews': 'view/previews', 'mode': 'view/mode'}
            if key in global_keys:
                self.settings.setValue(global_keys[key], value)
            return
        styles = self.settings.value('view/folder-styles-v1', {})
        styles = dict(styles) if isinstance(styles, dict) else {}
        style = dict(styles.get(str(folder), {}))
        style[key] = value
        styles[str(folder)] = style
        self.settings.setValue('view/folder-styles-v1', styles)

    def remember_folder_sort(self, pane, column, order):
        folder = self.folder if pane is getattr(self, 'bound_pane', None) else pane.folder
        if getattr(self, '_restoring_folder_display', False) or not folder:
            return
        if per_folder_views(self.settings) or special_view(self.settings, folder):
            pane.folder_sorts[folder] = (column, order)
            self.remember_folder_display(folder, 'sort', [column, int(order.value)])
        else:
            self.settings.setValue('sorting/common-sort', [column, int(order.value)])

    def restore_folder_view(self, destination):
        pane = getattr(self, 'bound_pane', None)
        if pane is None:
            return
        if self.folder:
            pane.folder_views[self.folder] = pane.view_mode
        modes = getattr(self, 'folder_view_modes', None)
        if modes is None:
            modes = self.settings.value('view/folder-modes-v1', {})
            modes = dict(modes) if isinstance(modes, dict) else {}
            self.folder_view_modes = modes
        style = self.folder_display_style(destination)
        default_mode = self.settings.value('view/mode', 1, type=int)
        if per_folder_views(self.settings):
            default_mode = pane.folder_views.get(destination, modes.get(destination, default_mode))
        mode = style.get('mode', default_mode)
        try:
            mode = int(mode)
        except (TypeError, ValueError):
            mode = 1
        if mode in (0, 1, 2) and mode != self.content_stack.currentIndex():
            self.change_view(mode, remember=False)
        pane.view_mode = mode
        style = self.folder_display_style(destination)
        self._restoring_folder_display = True
        try:
            special_columns = style.get('columns')
            if special_columns is not None:
                if not getattr(pane, '_normal_columns', None):
                    pane._normal_columns = [c for c in range(len(HEADERS)) if not pane.table.isColumnHidden(c)]
                    pane._normal_column_state = pane.table.horizontalHeader().saveState()
                visible_columns = special_columns
            else:
                visible_columns = getattr(pane, '_normal_columns', None)
                pane._normal_columns = None
                saved_header = getattr(pane, '_normal_column_state', None)
                if saved_header is not None:
                    pane.table.horizontalHeader().restoreState(saved_header)
                    pane._normal_column_state = None
                    visible_columns = None
            if visible_columns is not None:
                for c in range(len(HEADERS)):
                    pane.table.setColumnHidden(c, c not in visible_columns)
            for view in (pane.table, pane.icons, pane.compact):
                view.grouped_sorting = bool(style.get('grouped', False))
                view._backend.schedule()
            stored_sort = (style.get('sort', [0, 0])
                           if per_folder_views(self.settings) or special_view(self.settings, destination)
                           else self.settings.value('sorting/common-sort', [0, 0]))
            if isinstance(stored_sort, (list, tuple)) and len(stored_sort) == 2:
                column, direction = int(stored_sort[0]), int(stored_sort[1])
                if 0 <= column < len(HEADERS) and direction in (0, 1):
                    self.table.sortByColumn(column, Qt.SortOrder(direction))
                    pane.folder_sorts[destination] = (column, Qt.SortOrder(direction))
            common_folders_first = self.settings.value('sorting/folders-first', True, type=bool)
            folders_first = bool(style.get('folders_first', common_folders_first)
                                 if per_folder_views(self.settings) or special_view(self.settings, destination)
                                 else common_folders_first)
            if self.proxy.folders_first != folders_first:
                self.proxy.folders_first = folders_first
                self.proxy.invalidate()
            raw_columns = style.get('extra_columns', ())
            allowed = {1, 2, 3, 4, 14, 19, 20}
            pane.extra_columns = tuple(column for column in raw_columns if type(column) is int and column in allowed) if isinstance(raw_columns, (list, tuple)) else ()
            self.update_pane_extra_information(pane)
            hidden = bool(style.get('hidden', self.settings.value('view/hidden', False, type=bool)))
            previews = bool(style.get('previews', self.settings.value('view/previews', False, type=bool)))
            pane.hidden_state = hidden
            self.hidden.blockSignals(True)
            self.hidden.setChecked(hidden)
            self.hidden.blockSignals(False)
            self.hidden_action.blockSignals(True)
            self.hidden_action.setChecked(hidden)
            self.hidden_action.blockSignals(False)
            self.apply_hidden_filter()
            self.sync_native_navigator_state(pane)
            self.model.show_thumbnails = previews
            self.preview_action.blockSignals(True)
            self.preview_action.setChecked(previews)
            self.preview_action.blockSignals(False)
            self.preview_button.blockSignals(True)
            self.preview_button.setChecked(previews)
            self.preview_button.blockSignals(False)
            self.apply_icon_zoom()
        finally:
            self._restoring_folder_display = False

