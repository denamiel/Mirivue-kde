from .i18n import tr
tr("Independent directory views sharing the window's file operations and job queue.\n\nOnly GUI-thread callbacks bind a pane. Worker signals capture their originating\npane, so navigation in the other view cannot redirect results or cancellation.\n")
from pathlib import Path
import os
import json
from types import SimpleNamespace
from PySide6.QtCore import Qt, QEvent, QSize, QTimer, QModelIndex, QPoint, QUrl, QProcess
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShortcut, QCursor, QPalette
from PySide6.QtWidgets import QAbstractItemView, QListView, QStackedWidget, QPushButton, QToolButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy, QApplication, QLineEdit, QScrollArea, QFrame, QStyle, QHeaderView, QStyleOptionFrame, QStylePainter, QMenu, QMessageBox
from .selection import DetailsView, IconView
from .locations import ARCHIVE_PROTOCOLS, Location, archive_protocol
from .iconography import themed_icon, set_themed_action_icon
from .path_bar import local_place_breadcrumb
from .view_policy import per_folder_views, special_view
from .places import local_places
from .platform_services import services
from .item_presentation import (configure_details_header, suspend_details_header,
                                details_header_adjusting)
def reveal_breadcrumb_end(scroll):
    """A queued fallback reveal must not touch a deleted C++ scroll area."""
    from shiboken6 import isValid
    if isValid(scroll):
        bar = scroll.horizontalScrollBar()
        bar.setValue(bar.maximum())


FIELDS = (tr('model'), tr('proxy'), tr('table'), tr('icons'), tr('compact'), tr('content_stack'), tr('folder'), tr('history'), tr('history_position'), tr('pending_navigation'), tr('parent_selection'), tr('worker'), tr('thumbnail_worker'), tr('folder_size_worker'), tr('scanning'), tr('scan_queued'), tr('notices'), tr('search_active'), tr('search_root'), tr('search_criteria'))

class PaneElidingLabel(QLabel):
    """Keep changing footer text on one line without changing pane geometry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ''
        self._elide_mode = Qt.TextElideMode.ElideMiddle
        self.setWordWrap(False)

    def set_full_text(self, text, mode=None):
        self._full_text = text
        if mode is not None:
            self._elide_mode = mode
        self.refresh_elision()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_elision()

    def refresh_elision(self):
        visible = self.fontMetrics().elidedText(
            self._full_text,
            self._elide_mode,
            max(0, self.contentsRect().width()),
        )
        if visible != self.text():
            self.setText(visible)


class HoverPathBar(QLineEdit):
    """Native Plasma location-bar frame with hover reporting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hover_changed = None
        self._active = False
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_active(self, active):
        active = bool(active)
        if active != self._active:
            self._active = active
            self.update()

    def paintEvent(self, event):
        # The active pane changes the breadcrumb text, not the outer frame.
        # Leave the fallback's frame to the current Qt/Plasma style.
        option = QStyleOptionFrame()
        self.initStyleOption(option)
        option.state &= ~QStyle.StateFlag.State_HasFocus
        option.state |= QStyle.StateFlag.State_Sunken
        painter = QStylePainter(self)
        painter.drawPrimitive(QStyle.PrimitiveElement.PE_PanelLineEdit, option)

    def enterEvent(self, event):
        if self.hover_changed is not None:
            self.hover_changed(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Entering a child can briefly produce a leave event with some Qt
        # styles.  Check the complete bar after Qt has dispatched that event.
        QTimer.singleShot(0, self.refresh_hover)
        super().leaveEvent(event)

    def refresh_hover(self):
        if self.hover_changed is not None:
            local = self.mapFromGlobal(QCursor.pos())
            self.hover_changed(self.rect().contains(local))


class BreadcrumbArea(QWidget):
    """Turn a click in the unused breadcrumb area into location editing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.blank_clicked = None

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.childAt(event.position().toPoint()) is None
                and self.blank_clicked is not None):
            self.blank_clicked()
            event.accept()
            return
        super().mousePressEvent(event)

class PaneMixin:

    def trash_view_has_items(self):
        if not hasattr(self, '_tabs'):
            return (QUrl(str(self.folder or '')).scheme().casefold() == 'trash'
                    and bool(self.model.rows))
        self.capture_pane()
        return any(QUrl(str(pane.folder or '')).scheme().casefold() == 'trash'
                   and bool(pane.model.rows)
                   for tab in self._tabs for pane in tab.panes)

    def refresh_trash_panes(self):
        """Discard stale Trash rows in every pane before reloading KIO."""
        if not hasattr(self, '_tabs'):
            if QUrl(str(self.folder or '')).scheme().casefold() == 'trash':
                self._clear_and_reload_trash_pane(self.folder)
            return
        self.capture_pane()
        for tab in self._tabs:
            for pane in tab.panes:
                folder = str(pane.folder or '')
                if QUrl(folder).scheme().casefold() == 'trash':
                    self.run_in_pane(pane, self._clear_and_reload_trash_pane, folder)

    def _clear_and_reload_trash_pane(self, folder):
        self.model.clear()
        self.update_empty_state()
        self.update_summary()
        if self.scanning:
            self.pending_navigation = (folder, None)
            if self.worker is not None:
                self.worker.cancel()
        else:
            self.scan()

    def accept_kio_listing(self, pane, worker, rows):
        if not worker.cancelled:
            self.run_in_pane_silent(pane, self.set_initial_listing, rows)

    def copy_current_folder_name(self):
        if not self.folder:
            return
        value = str(self.folder)
        url = QUrl(value)
        name = url.path().rstrip('/').rsplit('/', 1)[-1] if url.scheme() else Path(value).name
        QApplication.clipboard().setText(name or '/')

    def open_place_in_split_view(self, location):
        if not self.split_enabled:
            self.set_split_view(True, navigate_new=False)
        destination = next((pane for pane in self.panes if pane is not self.bound_pane), None)
        if destination is not None:
            self.activate_pane(destination)
            self.navigate(location)

    def open_place_in_new_window(self, location, files=(), properties=False):
        from .launch_targets import LaunchRequest
        return self.open_requests_in_new_window([LaunchRequest(str(location), tuple(map(str, files)))],
                                                properties=properties)

    def report_native_place_error(self, message):
        QMessageBox.warning(self, tr('Emplacement indisponible'), str(message))

    def init_panes(self, navigation, view_menu):
        self.panes = []
        self.bound_pane = None
        self.split_enabled = False
        # Keep the existing fill preference, but allocate spare width to Name
        # as Dolphin does, rather than stretching the final metadata field.
        self._dolphin_fill_width_migration = not self.settings.value(
            'columns/fill-view-width-dolphin-v1', False, type=bool
        )
        if self._dolphin_fill_width_migration:
            self.settings.setValue('columns/fill-view-width-dolphin-v1', True)
        self._pane_context_depth = 0
        self._delete_button_update_pending = False
        # Set only while the pointer is actually on a column resize handle.
        # QHeaderView may deliver that press to its viewport rather than to
        # the header object itself, so the event filter checks both widgets.
        self._column_resize_pane = None
        # Dolphin's navigator action hosts its children in a QSplitter, which
        # is a QFrame. Union uses this native Frame ancestor when resolving the
        # navigator's frame. Keep our geometry synchronizer, with the same
        # frame context and no extra border drawn by this container.
        self.pane_path_container = QFrame(self.navigation_bar)
        self.pane_path_container.setFrameShape(QFrame.Shape.NoFrame)
        self.pane_path_container.setObjectName(tr('mirivuePanePaths'))
        # Dolphin's navigator host is transparent in a toolbar and uses the
        # Window palette role; KUrlNavigator paints its own KDE frame.
        self.pane_path_container.setAutoFillBackground(False)
        self.pane_path_container.setBackgroundRole(QPalette.ColorRole.Window)
        # Let breadcrumbs scroll in narrow windows instead of forcing the
        # surrounding window or preview dock to grow.
        self.pane_path_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pane_path_container.setMinimumWidth(0)
        self.pane_path_layout = QHBoxLayout(self.pane_path_container)
        self.pane_path_layout.setContentsMargins(0, 0, 0, 0)
        self.pane_path_layout.setSpacing(0)
        self.pane_path_separator = None
        self._pane_path_divider_gap = 6
        # A drag can produce dozens of splitterMoved signals per second.
        # Keep the views live while coalescing toolbar layouts and writes.
        self._path_alignment_drag_timer = QTimer(self)
        self._path_alignment_drag_timer.setSingleShot(True)
        self._path_alignment_drag_timer.setInterval(16)
        self._path_alignment_drag_timer.timeout.connect(self.sync_path_toolbar_alignment)
        self._breadcrumb_reveal_timer = QTimer(self)
        self._breadcrumb_reveal_timer.setSingleShot(True)
        self._breadcrumb_reveal_timer.timeout.connect(self.reveal_current_breadcrumbs)
        self._pane_splitter_save_timer = QTimer(self)
        self._pane_splitter_save_timer.setSingleShot(True)
        self._pane_splitter_save_timer.setInterval(200)
        self._pane_splitter_save_timer.timeout.connect(self.save_pane_splitter_sizes)
        self.register_pane()
        self.pane_splitter.splitterMoved.connect(self.schedule_pane_splitter_save)
        QTimer.singleShot(0, self.sync_path_toolbar_alignment)
        self.split_action = QAction(tr('Vue scindée'), self)
        set_themed_action_icon(self.split_action, tr('view-split-left-right'))
        self.split_action.setCheckable(True)
        self.split_action.setShortcut(QKeySequence(tr('F3')))
        self.addAction(self.split_action)
        view_menu.addAction(self.split_action)
        self.split_action.toggled.connect(self.set_split_view)
        self.split_button = QToolButton()
        self.split_button.setAutoRaise(True)
        self.split_button.setCheckable(True)
        self.split_button.setIcon(themed_icon(tr('view-split-left-right'), self, QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.split_button.setToolTip(tr('Afficher ou masquer la vue scindée (F3)'))
        self.split_button.setAccessibleName(tr('Vue scindée (F3)'))
        self.split_button.toggled.connect(self.split_action.setChecked)
        self.split_action.toggled.connect(self.split_button.setChecked)
        navigation.insertWidget(navigation.indexOf(self.details_button) + 1, self.split_button)
        self.refresh_symbolic_icons()

    def init_tabs(self, file_menu):
        """Keep a separate pane model, history and search for each tab."""
        self._recently_closed_tabs = []
        self._tab_mru = []
        self._tabs = [SimpleNamespace(panes=self.panes, bound=self.bound_pane,
                                      split=False, separator=self.pane_path_separator,
                                      location=None, splitter_sizes=None)]
        self._active_tab = 0
        self.tab_bar.addTab(tr('Dossier personnel'))
        self.tab_bar.currentChanged.connect(self.switch_tab)
        self.tab_bar.tabCloseRequested.connect(self.close_tab)
        self.tab_bar.tabMoved.connect(self.move_tab)
        self.new_tab_action = file_menu.addAction(tr('Nouvel onglet'), self.open_new_tab)
        self.new_tab_action.setShortcut(QKeySequence(tr('Ctrl+T')))
        set_themed_action_icon(self.new_tab_action, tr('tab-new'))
        self.close_tab_action = file_menu.addAction(tr('Fermer l’onglet'), lambda: self.close_tab(self.tab_bar.currentIndex()))
        self.close_tab_action.setShortcut(QKeySequence(tr('Ctrl+W')))
        self.addAction(self.close_tab_action)
        self.reopen_tab_action = file_menu.addAction(tr('Rouvrir le dernier onglet fermé'), self.reopen_closed_tab)
        self.reopen_tab_action.setShortcut(QKeySequence(tr('Ctrl+Shift+T')))
        self.reopen_tab_action.setEnabled(False)
        self.recently_closed_tabs_menu = file_menu.addMenu(tr('Onglets récemment fermés'))
        self.recently_closed_tabs_menu.setEnabled(False)
        self.recently_closed_tabs_menu.aboutToShow.connect(self.populate_recently_closed_tabs)
        for attribute, shortcut, step in (('next_tab_action', 'Ctrl+Tab', 1), ('previous_tab_action', 'Ctrl+Shift+Tab', -1)):
            key = QAction(self)
            setattr(self, attribute, key)
            key.setShortcut(QKeySequence(shortcut))
            key.triggered.connect(lambda checked=False, offset=step: self.tab_bar.setCurrentIndex(
                (self.tab_bar.currentIndex() + offset) % self.tab_bar.count()))
            self.addAction(key)

    def location_identity(self, location):
        from .places import location_identity
        native = getattr(self, 'native_places', None)
        if native is not None:
            identity = native.location_identity(location)
            if identity:
                return identity
        return location_identity(location)

    def tab_title(self, location):
        return self.location_identity(location)[0]

    def open_new_tab(self, location=None, active=True, external_files=None, external_properties=False, append=None, insert_index=None):
        if isinstance(location, bool):  # QAction.triggered(bool)
            location = None
        if append is None:
            append = not location or isinstance(location, bool) or self.settings.value('tabs/open-after-last', False, type=bool)
        location = location or self.folder or str(Path.home())
        self.capture_pane()
        self.save_pane_splitter_sizes()
        old_separator = self.pane_path_separator
        pane = self.create_second_pane()
        pane.external_request_pending = external_files is not None
        pane.pending_external_files = [Path(path) for path in (external_files or ())]
        pane.pending_external_properties = bool(external_properties)
        self.panes.remove(pane)
        # create_second_pane creates a divider for the current tab. A new tab
        # starts with one view and acquires its own divider only when split.
        new_separator = self.pane_path_separator
        if new_separator is not old_separator and new_separator is not None:
            self.pane_path_layout.removeWidget(new_separator)
            new_separator.deleteLater()
        self.pane_path_separator = old_separator
        pane.container.hide()
        pane.path_bar.hide()
        tab = SimpleNamespace(panes=[pane], bound=pane, split=False,
                              separator=None, location=str(location), splitter_sizes=None)
        index = len(self._tabs) if append else self._active_tab + 1
        if insert_index is not None:
            index = max(self._active_tab + 1, min(len(self._tabs), insert_index))
        self._tabs.insert(index, tab)
        self.tab_bar.blockSignals(True)
        self.tab_bar.insertTab(index, self.tab_title(location).replace('&', '&&'))
        self.tab_bar.blockSignals(False)
        self.refresh_tab_title(index)
        self.tab_bar.setTabToolTip(index, str(location))
        self.apply_tab_bar_settings()
        if active:
            self.tab_bar.setCurrentIndex(index)
        return pane

    def switch_tab(self, index):
        if index < 0 or index >= len(self._tabs) or index == self._active_tab:
            return
        self._pane_splitter_save_timer.stop()
        self.save_pane_splitter_sizes()
        self.capture_pane()
        previous = self._tabs[self._active_tab]
        self._tab_mru = [t for t in self._tab_mru if t is not previous]
        self._tab_mru.append(previous)
        previous.bound = self.bound_pane
        previous.split = self.split_enabled
        previous.separator = self.pane_path_separator
        for pane in previous.panes:
            pane.container.hide()
            pane.path_bar.hide()
        if previous.separator is not None:
            previous.separator.hide()
        tab = self._tabs[index]
        self._active_tab = index
        self.panes = tab.panes
        self.split_enabled = tab.split
        self.pane_path_separator = tab.separator
        for pane in self.panes:
            pane.container.setVisible(self.split_enabled or pane is tab.bound)
        self.restore_tab_splitter_sizes(tab)
        self.bind_pane(tab.bound)
        self.split_action.blockSignals(True)
        self.split_action.setChecked(self.split_enabled)
        self.split_action.blockSignals(False)
        self.sync_pane_path_bars()
        self.sync_pane_controls()
        self.update_navigation()
        if getattr(self, '_restoring_session', False):
            pass
        elif any(getattr(pane, '_session_listing_pending', False)
                 for pane in (tab.panes if tab.split else [tab.bound])):
            self.start_pending_tab_listings(tab)
        elif self.folder is None and tab.location:
            self.navigate(tab.location)
        else:
            self.active_view().setFocus()
        QTimer.singleShot(0, self.sync_path_toolbar_alignment)

    def restore_tab_splitter_sizes(self, tab):
        """Apply saved proportions even before the top-level window is shown."""
        widths = tab.splitter_sizes if tab.split and tab.splitter_sizes else [1] * len(tab.panes)
        sizes = [0] * self.pane_splitter.count()
        for pane, width in zip(tab.panes, widths):
            if tab.split or pane is tab.bound:
                sizes[self.pane_splitter.indexOf(pane.container)] = width
        self.pane_splitter.setSizes(sizes)

    def start_pending_tab_listings(self, tab):
        """A lazy split tab owns two listings, not only its active pane's."""
        for pane in (tab.panes if tab.split else [tab.bound]):
            if getattr(pane, '_session_listing_pending', False):
                pane._session_listing_pending = False
                if pane.folder and not pane.scanning:
                    self.run_in_pane(pane, self.scan)
        self.active_view().setFocus()

    def move_tab(self, from_index, to_index):
        tab = self._tabs.pop(from_index)
        self._tabs.insert(to_index, tab)
        self._active_tab = self.tab_bar.currentIndex()

    def close_tab(self, index):
        if index < 0 or index >= len(self._tabs):
            return
        if self.tab_bar.count() == 1:
            self.close()
            return
        tab = self._tabs[index]
        if index == self._active_tab:
            self._pane_splitter_save_timer.stop()
            self.save_pane_splitter_sizes()
            self.capture_pane()
            tab.bound = self.bound_pane
            tab.split = self.split_enabled
        saved_panes = tab.panes if tab.split else [tab.bound]
        locations = [str(p.folder or (p.pending_navigation[0] if p.pending_navigation else None)
                         or tab.location or Path.home()) for p in saved_panes]
        self._recently_closed_tabs.append((locations, saved_panes.index(tab.bound), tab.split,
                                          tab.splitter_sizes, getattr(tab, 'custom_title', '')))
        self._recently_closed_tabs = self._recently_closed_tabs[-20:]
        self.reopen_tab_action.setEnabled(True)
        self.recently_closed_tabs_menu.setEnabled(True)
        self.tab_bar.blockSignals(True)
        try:
            if index == self._active_tab:
                previous = next((t for t in reversed(self._tab_mru)
                                 if t is not tab and any(t is live for live in self._tabs)), None)
                next_index = next((i for i, t in enumerate(self._tabs) if t is previous),
                                  index - 1 if index else 1)
                self.switch_tab(next_index)
            self._tabs.pop(index)
            self._tab_mru = [t for t in self._tab_mru if t is not tab]
            self.tab_bar.removeTab(index)
            if self._active_tab > index:
                self._active_tab -= 1
            self.tab_bar.setCurrentIndex(self._active_tab)
        finally:
            self.tab_bar.blockSignals(False)
        for pane in tab.panes:
            self.retire_pane(pane)
            pane.container.hide()
            pane.container.setParent(None)
            pane.container.deleteLater()
            self.pane_path_layout.removeWidget(pane.path_bar)
            pane.path_bar.deleteLater()
            if hasattr(pane, 'fallback_path_bar'):
                pane.fallback_path_bar.deleteLater()
        if tab.separator is not None:
            self.pane_path_layout.removeWidget(tab.separator)
            tab.separator.deleteLater()
        self.apply_tab_bar_settings()
        self.sync_path_toolbar_alignment()

    def retire_pane(self, pane):
        """Cancel pane lookups without waiting; reject every queued UI delivery."""
        pane._closed = True
        timer = getattr(pane, 'column_save_timer', None)
        if timer is not None:
            timer.stop()
        pane.scanning = False
        self.cancel_duration_lookups(pane)
        for name in ('worker', 'thumbnail_worker', 'folder_size_worker'):
            worker = getattr(pane, name, None)
            if worker is None:
                continue
            from shiboken6 import isValid
            if isValid(worker):
                if worker.isRunning():
                    cancel = getattr(worker, 'cancel', None)
                    if callable(cancel):
                        cancel()
                    worker.requestInterruption()
                    # RuntimeTaskRegistry owns the live thread until completion.
                    worker.finished.connect(worker.deleteLater)
                else:
                    worker.deleteLater()
            setattr(pane, name, None)
        pane.model.pending_preliminary = []
        pane.model.pending_resolved = []

    def apply_tab_bar_settings(self):
        self.tab_bar.setTabsClosable(self.settings.value('tabs/show-close-buttons', True, type=bool))
        self.tab_bar.setVisible(self.tab_bar.count() > 1 or self.settings.value('tabs/always-show-bar', False, type=bool))

    def populate_recently_closed_tabs(self):
        self.recently_closed_tabs_menu.clear()
        for index in range(len(self._recently_closed_tabs) - 1, -1, -1):
            locations, _active, _split, _sizes, *names = self._recently_closed_tabs[index]
            title = names[0] if names and names[0] else self.tab_title(locations[0])
            action = self.recently_closed_tabs_menu.addAction(title.replace('&', '&&'))
            action.setToolTip(locations[0])
            action.triggered.connect(lambda checked=False, position=index: self.reopen_closed_tab(position))

    def reopen_closed_tab(self, index=None):
        if not self._recently_closed_tabs:
            return
        if type(index) is not int:  # QAction.triggered passes a bool.
            index = len(self._recently_closed_tabs) - 1
        if index < 0 or index >= len(self._recently_closed_tabs):
            return
        locations, active, split, sizes, *names = self._recently_closed_tabs.pop(index)
        self.reopen_tab_action.setEnabled(bool(self._recently_closed_tabs))
        self.recently_closed_tabs_menu.setEnabled(bool(self._recently_closed_tabs))
        self.open_new_tab(locations[0])
        if split and len(locations) > 1:
            self._tabs[self._active_tab].splitter_sizes = sizes
            self.set_split_view(True, navigate_new=False)
            self.run_in_pane(self.panes[1], self.navigate, locations[1])
            if active == 1:
                self.activate_pane(self.panes[1])
        if names and names[0]:
            self.rename_tab(self._active_tab, names[0])

    def refresh_tab_title(self, index):
        tab = self._tabs[index]
        def location(pane):
            return self.folder if pane is self.bound_pane else pane.folder or tab.location
        panes = self.panes if index == self._active_tab else tab.panes
        split = self.split_enabled if index == self._active_tab else tab.split
        bound = self.bound_pane if index == self._active_tab else tab.bound
        if getattr(tab, 'custom_title', ''):
            title = tab.custom_title
        elif split and len(panes) > 1:
            left, right = (self.tab_title(location(p)) for p in panes[:2])
            title = f'{left} | ({right})' if bound is panes[0] else f'({left}) | {right}'
        else:
            title = self.tab_title(location(bound))
        if getattr(tab, 'custom_title', ''):
            self.tab_bar.setTabText(index, title.replace('&', '&&'))
        else:
            from .places import set_automatic_tab_text
            set_automatic_tab_text(self.tab_bar, index, title)
        self.tab_bar.setTabIcon(index, themed_icon(self.location_identity(location(bound))[1], self.tab_bar, QStyle.StandardPixmap.SP_DirIcon))
        self.tab_bar.setTabToolTip(index, '\n'.join(str(location(p) or '') for p in panes))

    def rename_tab(self, index, name=None):
        if name is None:
            from PySide6.QtWidgets import QInputDialog
            name, accepted = QInputDialog.getText(self, tr('Renommer l’onglet'), tr('Nouveau nom :'),
                                                 text=getattr(self._tabs[index], 'custom_title', '') or self.tab_bar.tabText(index).replace('&&', '&'))
            if not accepted:
                return
        self._tabs[index].custom_title = str(name)
        self.refresh_tab_title(index)

    def close_tab_group(self, indices):
        for index in sorted(indices, reverse=True):
            if len(self._tabs) > 1:
                self.close_tab(index)

    def detach_tab(self, index):
        tab = self._tabs[index]
        # Preserve both panes and the custom title across the new process.
        snapshot = self.session_snapshot()['tabs'][index]
        if self.open_requests_in_new_window([], detached_tab=snapshot):
            self.close_tab(index)

    def pane_drop_to_location(self, event, destination):
        paths = [Path(url.toLocalFile()) if url.isLocalFile() else url.toString()
                 for url in event.mimeData().urls()]
        if not paths or not destination or not self.allow_drop_destination(paths, destination):
            event.ignore()
            return
        action = self.pane_drop_action(paths, destination, event)
        if not event.possibleActions() & action:
            event.ignore()
            return
        event.setDropAction(action)
        event.accept()
        modifiers = event.keyboardModifiers()
        if not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            QTimer.singleShot(0, lambda: self.drop_choices(paths, destination))
        else:
            operation = 'link' if action == Qt.DropAction.LinkAction else 'copy' if action == Qt.DropAction.CopyAction else 'move'
            QTimer.singleShot(0, lambda: self.drop_operation(paths, destination, operation))

    def capture_pane(self):
        p = self.bound_pane
        if p is None:
            return
        for name in FIELDS:
            setattr(p, name, getattr(self, name))
        p.search_text = self.search.text()
        p.search_content = self.search_content.isChecked()
        p.filter_text = self.quick_filter.text()
        p.filter_open = not self.filter_panel.isHidden()
        p.search_open = not self.search_panel.isHidden()
        p.search_scope = self.search_scope.currentData()
        p.search_kind = self.search_kind.currentData()
        p.state_filter = self.state_filter.currentText()

    def bind_pane(self, pane, style_path=True):
        self.bound_pane = pane
        for name in FIELDS:
            setattr(self, name, getattr(pane, name))
        if self.hidden.isChecked() != pane.hidden_state:
            self.hidden.blockSignals(True)
            self.hidden.setChecked(pane.hidden_state)
            self.hidden.blockSignals(False)
            self.hidden_action.blockSignals(True)
            self.hidden_action.setChecked(pane.hidden_state)
            self.hidden_action.blockSignals(False)
            self.apply_hidden_filter()
        self.sync_native_navigator_state(pane)
        mode = pane.content_stack.currentIndex()
        button = self.view_buttons.button(mode)
        if button is not None:
            button.setChecked(True)
        for index, action in enumerate((self.details_view_action, self.icons_view_action,
                                        self.compact_view_action)):
            action.setChecked(index == mode)
        self.search.blockSignals(True)
        self.search.setText(pane.search_text)
        self.search.blockSignals(False)
        self.search_panel.setVisible(pane.search_open)
        self.search_content.blockSignals(True)
        self.search_content.setChecked(pane.search_content)
        self.search_content.blockSignals(False)
        self.quick_filter.blockSignals(True)
        self.quick_filter.setText(pane.filter_text)
        self.quick_filter.blockSignals(False)
        self.filter_panel.setVisible(pane.filter_open)
        self.proxy.set_name_filter(pane.filter_text)
        if hasattr(self, 'activity_message_label'):
            self.sync_feedback_in_pane_footers()
        scope_index = self.search_scope.findData(pane.search_scope)
        self.search_scope.blockSignals(True)
        self.search_scope.setCurrentIndex(max(0, scope_index))
        self.search_scope.blockSignals(False)
        kind_index = self.search_kind.findData(pane.search_kind)
        self.search_kind.blockSignals(True)
        self.search_kind.setCurrentIndex(max(0, kind_index))
        self.search_kind.blockSignals(False)
        self.state_filter.blockSignals(True)
        self.state_filter.setCurrentText(tr('Informations techniques manquantes') if pane.state_filter == tr('Médias incomplets') else pane.state_filter)
        self.state_filter.blockSignals(False)
        self.search_duplicates_manage.setVisible(
            self.search_active
            and self.search_criteria.get('state') == tr('Doublons exacts')
            and bool(self.duplicate_groups)
        )
        self.table.setColumnHidden(12, not self.search_active)
        if hasattr(self, 'update_search_more_label'):
            self.update_search_more_label()
        if style_path:
            self.style_pane_path_bars()

    def register_pane(self):
        pane = SimpleNamespace(**{name: getattr(self, name) for name in FIELDS})
        # Native editor commits are queued. The active pane can change before
        # they reach this model, but the edit still belongs to its own pane.
        pane.model.rename_handler = lambda path, name, p=pane: self.run_in_pane(p, self.rename_inline, path, name)
        pane.model.edit_allowed = lambda p=pane: not (self.scanning if p is self.bound_pane else p.scanning)
        pane.column_slot = 'left' if not self.panes else 'right'
        pane.column_width_mode = str(self.settings.value(f'columns-pane-{pane.column_slot}-width-mode-v1', 'custom'))
        if pane.column_width_mode not in ('auto', 'custom'):
            pane.column_width_mode = 'custom'
        pane.fill_view_width = (
            True if self._dolphin_fill_width_migration
            else self.settings.value(f'columns-pane-{pane.column_slot}-fill-width-v1', True, type=bool)
        )
        saved_widths = self.settings.value(f'columns-pane-{pane.column_slot}-custom-widths-v1', [])
        try:
            pane.custom_column_widths = [max(20, int(width)) for width in saved_widths]
        except (TypeError, ValueError):
            pane.custom_column_widths = []
        pane.search_text = ''
        pane.pending_live_search = False
        pane.search_content = False
        pane.filter_text = ''
        pane.filter_open = False
        pane.search_open = False
        pane.search_scope = 'recursive'
        pane.search_kind = 'all'
        pane.state_filter = tr('Tous les états')
        pane.folder_sorts = {}
        pane.folder_views = {}
        pane.hidden_state = self.hidden.isChecked()
        pane.extra_columns = ()
        pane.view_mode = pane.content_stack.currentIndex()
        pane.container = QWidget()
        pane.table.horizontalHeader().sortIndicatorChanged.connect(
            lambda column, order, p=pane: self.remember_folder_sort(p, column, order))
        self.configure_pane_extra_information(pane)
        pane.container.setObjectName(tr('mirivuePane'))
        box = QVBoxLayout(pane.container)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(5)
        self.create_pane_path_bar(pane)
        pane.label = QLabel()
        pane.label.setTextFormat(Qt.TextFormat.PlainText)
        pane.label.setMargin(4)
        pane.label.hide()
        box.addWidget(pane.label)
        pane.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        pane.container.setMinimumWidth(120)
        pane.column_save_timer = QTimer(pane.container)
        pane.column_save_timer.setSingleShot(True)
        pane.column_save_timer.setInterval(250)
        pane.column_save_timer.timeout.connect(lambda p=pane: self.save_pane_column_state(p))
        header = pane.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.sectionMoved.connect(lambda *_args, p=pane: self.schedule_pane_column_save(p))
        header.sectionResized.connect(lambda *_args, p=pane: self.schedule_pane_column_save(p))
        box.addWidget(pane.content_stack)
        pane.footer = QWidget(pane.container)
        pane.footer.setObjectName(tr('mirivuePaneFooter'))
        pane.footer.setAutoFillBackground(True)
        footer_layout = QHBoxLayout(pane.footer)
        footer_layout.setContentsMargins(8, 2, 8, 2)
        footer_layout.setSpacing(6)
        pane.summary_label = PaneElidingLabel(pane.footer)
        pane.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        pane.summary_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pane.summary_label.setMinimumWidth(0)
        # Item counts change after each transfer.  A text-dependent minimum
        # width would make QSplitter redistribute the two file panes.
        pane.summary_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer_layout.addWidget(pane.summary_label, 4)
        pane.selection_label = PaneElidingLabel(pane.footer)
        pane.selection_label.setTextFormat(Qt.TextFormat.PlainText)
        pane.selection_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pane.selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pane.selection_label.setMinimumWidth(0)
        pane.selection_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer_layout.addWidget(pane.selection_label, 2)
        pane.disk_label = PaneElidingLabel(pane.footer)
        pane.disk_label.setTextFormat(Qt.TextFormat.PlainText)
        pane.disk_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        pane.disk_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pane.disk_label.setMinimumWidth(0)
        # Free-space labels change during a copy and must not resize a pane.
        pane.disk_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        footer_layout.addWidget(pane.disk_label, 4)
        box.addWidget(pane.footer)
        self.pane_splitter.addWidget(pane.container)
        self.panes.append(pane)
        pane.content_stack.currentChanged.connect(lambda *_args: self.sync_pane_scrollbar_policies())
        self.bound_pane = pane
        self.style_pane_path_bars()
        pane.label.installEventFilter(self)
        pane.table.horizontalHeader().installEventFilter(self)
        pane.table.horizontalHeader().viewport().installEventFilter(self)
        for view in (pane.table, pane.icons, pane.compact):
            view.installEventFilter(self)
            view.viewport().installEventFilter(self)
            view.selectionModel().selectionChanged.connect(lambda *_, p=pane: self.pane_selection_changed(p))
            view.setAcceptDrops(True)
            view.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            view.setDefaultDropAction(Qt.DropAction.MoveAction)
            # QAbstractItemView emits `pressed` from its own mouse handling.
            # Activate here rather than in QApplication's pre-dispatch event
            # filter, so file selection is not held up by palette work.
            view.pressed.connect(lambda _index, p=pane: self.activate_pane(p))
            view.activation_handler = lambda p=pane: self.activate_pane_from_empty_area(p)
            view.open_handler = lambda index, p=pane: self.pane_command(p, self.open_video, index)
            view.context_menu_handler = lambda point, shift=False, p=pane: self.pane_command(p, self.context_menu, point, shift)
            view.drag_handler = lambda v, p=pane: self.pane_drag(p, v)
            view.drop_handler = lambda event, v=view, p=pane: self.pane_drop(p, v, event)
        pane.table.horizontalHeader().sectionPressed.connect(lambda *_args, p=pane: self.activate_pane(p))
        pane.table.horizontalHeader().sectionResized.connect(
            lambda logical, old, new, p=pane: self.pane_section_resized(p, logical, old, new)
        )
        self.apply_pane_column_width_mode(pane, restore_custom=False)
        return pane

    def configure_pane_extra_information(self, pane):
        for view in (pane.icons, pane.compact):
            view.extra_columns = pane.extra_columns

    def update_pane_extra_information(self, pane):
        for view in (pane.icons, pane.compact):
            view.extra_columns = pane.extra_columns
        pane.compact.setUniformItemSizes(not bool(pane.extra_columns))
        self.run_in_pane_silent(pane, self.apply_icon_zoom)
        pane.icons.doItemsLayout()
        pane.compact.doItemsLayout()
        pane.icons.viewport().update()
        pane.compact.viewport().update()

    def set_folders_first(self, enabled, all_panes=False):
        """Keep folders above files for every column and sort direction."""
        enabled = bool(enabled)
        per_folder = per_folder_views(self.settings)
        if all_panes or not per_folder:
            self.settings.setValue('sorting/folders-first', enabled)
        panes = ((p for tab in self._tabs for p in tab.panes) if hasattr(self, '_tabs') else iter(self.panes)) if all_panes else (self.bound_pane,)
        for pane in panes:
            pane.proxy.folders_first = enabled
            if pane.folder and per_folder:
                self.remember_folder_display(pane.folder, 'folders_first', enabled)
            header = pane.table.horizontalHeader()
            pane.proxy.invalidate()
            pane.proxy.sort(header.sortIndicatorSection(), header.sortIndicatorOrder())
        self.settings.sync()

    def apply_pane_column_width_mode(self, pane, restore_custom=False):
        header = pane.table.horizontalHeader()
        # Dolphin fits the columns automatically, then leaves the header
        # interactive so the user can refine any width immediately.
        mode = QHeaderView.ResizeMode.Interactive
        suspend_details_header(pane.table)
        header.setResizeContentsPrecision(1000)
        header.setStretchLastSection(False)
        for column in range(header.count()):
            if header.isSectionHidden(column):
                # Qt collapses hidden sections when their resize mode is
                # changed.  Leave them untouched so their saved width is
                # restored when the user makes the column visible again.
                continue
            header.setSectionResizeMode(column, mode)
        if pane.column_width_mode == 'auto':
            header.resizeSections(QHeaderView.ResizeMode.ResizeToContents)
            # The pane is created before its first scan. Keep the primary
            # Name column immediately usable instead of allowing an empty
            # model to collapse it to the header label and resizing it later.
            header.resizeSection(0, max(240, header.sectionSize(0)))
        elif restore_custom and len(pane.custom_column_widths) == header.count():
            for column, width in enumerate(pane.custom_column_widths):
                header.resizeSection(column, width)
        configure_details_header(pane.table, pane.column_width_mode == 'auto',
                                 pane.fill_view_width, capture=True)

    def pane_section_resized(self, pane, logical, old, new):
        """Persist the first manual adjustment after an automatic fit.

        Qt emits ``sectionResized`` for both layout work and pointer drags.
        The event filter marks only a real press on a resize handle, so
        ordinary layout work and window resizes keep the automatic profile.
        """
        if (pane is None or pane.column_width_mode != 'auto' or old == new
                or details_header_adjusting(pane.table)):
            return
        if getattr(self, '_column_resize_pane', None) is not pane:
            return
        header = pane.table.horizontalHeader()
        pane.column_width_mode = 'custom'
        configure_details_header(pane.table, False, pane.fill_view_width, capture=True)
        pane.custom_column_widths = [header.sectionSize(column) for column in range(header.count())]
        self.settings.setValue(f'columns-pane-{pane.column_slot}-width-mode-v1', 'custom')
        self.settings.setValue(f'columns-pane-{pane.column_slot}-custom-widths-v1', pane.custom_column_widths)
        self.schedule_pane_column_save(pane)

    def set_pane_column_width_mode(self, pane, mode):
        if pane is None or mode not in ('auto', 'custom'):
            return
        header = pane.table.horizontalHeader()
        if pane.column_width_mode == 'custom' and mode == 'auto':
            pane.custom_column_widths = [header.sectionSize(column) for column in range(header.count())]
            self.settings.setValue(f'columns-pane-{pane.column_slot}-custom-widths-v1', pane.custom_column_widths)
        restore_custom = pane.column_width_mode == 'auto' and mode == 'custom'
        pane.column_width_mode = mode
        self.settings.setValue(f'columns-pane-{pane.column_slot}-width-mode-v1', mode)
        self.apply_pane_column_width_mode(pane, restore_custom=restore_custom)
        self.schedule_pane_column_save(pane)

    def set_pane_fill_view_width(self, pane, enabled):
        if pane is None:
            return
        pane.fill_view_width = bool(enabled)
        configure_details_header(pane.table, pane.column_width_mode == 'auto',
                                 pane.fill_view_width)
        self.settings.setValue(f'columns-pane-{pane.column_slot}-fill-width-v1', pane.fill_view_width)
        self.schedule_pane_column_save(pane)

    def schedule_pane_column_save(self, pane):
        if (not getattr(self, '_restoring_folder_display', False)
                and pane is not None and hasattr(pane, 'column_save_timer')
                and not details_header_adjusting(pane.table)):
            pane.column_save_timer.start()

    def save_pane_column_state(self, pane):
        if pane is None or not hasattr(pane, 'table'):
            return
        key = f'columns-pane-{pane.column_slot}-v1'
        normal_header = getattr(pane, '_normal_column_state', None)
        if normal_header is not None:
            visible = [c for c in range(pane.model.columnCount()) if not pane.table.isColumnHidden(c)]
            folder = self.folder if pane is self.bound_pane else pane.folder
            if folder:
                self.remember_folder_display(folder, 'columns', visible)
        self.settings.setValue(key, normal_header if normal_header is not None else pane.table.horizontalHeader().saveState())
        self.settings.setValue(f'columns-pane-{pane.column_slot}-role-count', pane.model.columnCount())
        self.settings.setValue(f'columns-pane-{pane.column_slot}-width-mode-v1', pane.column_width_mode)
        self.settings.setValue(f'columns-pane-{pane.column_slot}-fill-width-v1', pane.fill_view_width)
        if pane.column_width_mode == 'custom':
            pane.custom_column_widths = [pane.table.horizontalHeader().sectionSize(column)
                                         for column in range(pane.table.horizontalHeader().count())]
            self.settings.setValue(f'columns-pane-{pane.column_slot}-custom-widths-v1', pane.custom_column_widths)

    def save_pane_column_states(self):
        all_panes = (p for tab in self._tabs for p in tab.panes) if hasattr(self, '_tabs') else iter(self.panes)
        for pane in all_panes:
            if hasattr(pane, 'column_save_timer'):
                pane.column_save_timer.stop()
            self.save_pane_column_state(pane)
        if self.bound_pane is not None:
            # Keep the old key as a migration source for earlier releases.
            self.settings.setValue('columns-v7', self.bound_pane.table.horizontalHeader().saveState())
        self.settings.sync()

    def create_pane_path_bar(self, pane):
        """Create an independent Dolphin-style location bar for one pane."""
        if self.panes:
            # Mirror the splitter handle below.  QFrame draws a restrained
            # single separator inside the handle-width slot.
            self.pane_path_separator = QWidget(self.pane_path_container)
            self.pane_path_separator.setObjectName(tr('mirivuePanePathDivider'))
            divider_layout = QHBoxLayout(self.pane_path_separator)
            divider_layout.setContentsMargins(0, 0, 0, 0)
            divider_layout.setSpacing(0)
            self.pane_path_divider_line = QFrame(self.pane_path_separator)
            self.pane_path_divider_line.setFrameShape(QFrame.Shape.VLine)
            self.pane_path_divider_line.setFrameShadow(QFrame.Shadow.Plain)
            # A small gap on each side makes the divider visible without
            # moving its one-pixel line away from the splitter below.
            divider_layout.addSpacing(self._pane_path_divider_gap)
            divider_layout.addWidget(self.pane_path_divider_line)
            divider_layout.addStretch(1)
            self.pane_path_separator.setFixedWidth(self.pane_splitter.handleWidth() + self._pane_path_divider_gap * 2)
            self.pane_path_layout.addWidget(self.pane_path_separator)
        bar = HoverPathBar(pane.container)
        bar.setObjectName(tr('mirivuePanePathBar'))
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.setMinimumWidth(0)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 4, 4, 2)
        layout.setSpacing(2)

        pane.crumbs = BreadcrumbArea(bar)
        pane.crumb_layout = QHBoxLayout(pane.crumbs)
        pane.crumb_layout.setContentsMargins(0, 0, 0, 0)
        pane.crumb_layout.setSpacing(0)
        pane.crumb_scroll = QScrollArea(bar)
        pane.crumb_scroll.setWidgetResizable(True)
        pane.crumb_scroll.setWidget(pane.crumbs)
        pane.crumb_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        pane.crumb_scroll.setAutoFillBackground(False)
        pane.crumb_scroll.viewport().setAutoFillBackground(False)
        pane.crumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pane.crumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pane.crumb_scroll.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, maximum, scroll=pane.crumb_scroll:
            scroll.horizontalScrollBar().setValue(maximum))
        # QPushButton's native size hint can be taller than this path bar's
        # viewport. Keep the unavoidable vertical overflow equally clipped
        # on both sides instead of leaving the labels against the lower edge.
        vertical = pane.crumb_scroll.verticalScrollBar()
        vertical.rangeChanged.connect(lambda _minimum, maximum, scroll=vertical:
                                      scroll.setValue(maximum // 2))
        pane.crumb_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        pane.crumb_scroll.setMinimumWidth(0)
        pane.crumb_scroll.setObjectName(tr('mirivuePanePath'))
        pane.path_input = QLineEdit(bar)
        pane.path_input.setFrame(False)
        pane.path_input.setPlaceholderText(tr('Saisir le chemin — Entrée pour ouvrir'))
        pane.path_input.setMinimumWidth(0)
        pane.path_input.returnPressed.connect(lambda: self.run_in_pane(pane, self.navigate, pane.path_input.text()))
        pane.path_stack = QStackedWidget(bar)
        pane.path_stack.addWidget(pane.crumb_scroll)
        pane.path_stack.addWidget(pane.path_input)
        pane.path_stack.setCurrentIndex(0)
        pane.path_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        pane.path_stack.setMinimumWidth(0)
        layout.addWidget(pane.path_stack, 1)
        pane.path_toggle = QPushButton('', bar)
        pane.path_toggle.setFlat(True)
        pane.path_toggle.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        pane.path_toggle.setIcon(themed_icon(tr('document-edit'), self, QStyle.StandardPixmap.SP_FileDialogInfoView))
        pane.path_toggle.setToolTip(tr('Saisir le chemin'))
        pane.path_toggle.setAccessibleName(tr('Saisir le chemin'))
        pane.path_toggle.clicked.connect(lambda: self.toggle_pane_path_mode(pane))
        layout.addWidget(pane.path_toggle)
        pane.path_bar = bar
        pane.rendered_path = None
        pane.rendered_full_path = None
        pane.path_hovered = False
        pane.path_toggle.hide()
        bar.hover_changed = lambda hovered, p=pane: self.set_pane_path_hover(p, hovered)
        pane.crumbs.blank_clicked = lambda p=pane: self.edit_pane_path(p)
        for surface in (bar, pane.crumbs, pane.crumb_scroll, pane.path_input):
            surface.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            surface.customContextMenuRequested.connect(
                lambda point, p=pane, widget=surface: self.pane_path_menu(p, widget, point)
            )
        self.pane_path_layout.addWidget(bar, 1)
        pane.native_navigator = None
        if getattr(self, 'native_places', None) is not None:
            try:
                from .native_places_view import NativePathNavigator
                pane.native_navigator = NativePathNavigator(
                    self.pane_path_container, self.native_places, pane.folder,
                    lambda location, p=pane: self.run_in_pane(p, self.navigate, location),
                    self.open_new_tab, self.open_place_in_new_window,
                    self.native_drop_completed, self.report_native_place_error)
                self.pane_path_layout.removeWidget(bar)
                bar.hide()
                pane.fallback_path_bar = bar
                pane.path_bar = pane.native_navigator.widget
                pane.native_navigator.set_full_path(
                    self.settings.value('view/full-path', False, type=bool))
                self.sync_native_navigator_state(pane)
                pane.path_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self.pane_path_layout.addWidget(pane.path_bar, 1)
            except (AttributeError, ImportError, OSError, RuntimeError, ValueError):
                pane.native_navigator = None
        pane.path_escape = QShortcut(QKeySequence('Escape'), pane.path_bar)
        pane.path_escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        pane.path_escape.activated.connect(lambda p=pane: self.toggle_pane_path_mode(p, False))
        self.style_pane_path_bars()

    def sync_native_navigator_state(self, pane):
        """Keep each KUrlNavigator in sync with its own view and the Places panel."""
        if pane.native_navigator is None:
            return
        pane.native_navigator.set_places_selector_visible(self.places_panel.isHidden())
        pane.native_navigator.set_hidden_folders(pane.hidden_state)

    def style_pane_path_bars(self, panes=None):
        """Let the Plasma style distinguish active and inactive path bars."""
        if not hasattr(self, tr('panes')):
            return
        targets = self.panes if panes is None else panes
        for pane in targets:
            active = pane is self.bound_pane and pane.container.isVisible()
            if pane.native_navigator is not None:
                pane.native_navigator.set_split_mode(self.split_enabled)
                pane.native_navigator.set_active(active)
            else:
                pane.path_bar.set_active(active)

    def toggle_pane_path_mode(self, pane, editing=None):
        if pane.native_navigator is not None:
            editing = not pane.native_navigator.is_editable() if editing is None else editing
            pane.native_navigator.set_editable(editing)
            if not editing:
                pane.content_stack.currentWidget().setFocus()
            return
        editing = (pane.path_stack.currentIndex() == 0) if editing is None else editing
        pane.path_stack.setCurrentIndex(1 if editing else 0)
        icon = tr('dialog-ok-apply') if editing else tr('document-edit')
        fallback = QStyle.StandardPixmap.SP_DialogApplyButton if editing else QStyle.StandardPixmap.SP_FileDialogInfoView
        pane.path_toggle.setIcon(themed_icon(icon, self, fallback))
        pane.path_toggle.setToolTip(tr('Afficher les boutons du chemin') if editing else tr('Saisir le chemin (Ctrl+L)'))
        pane.path_toggle.setAccessibleName(pane.path_toggle.toolTip())
        pane.path_toggle.setVisible(editing or pane.path_hovered)
        if editing:
            pane.path_input.setText(pane.folder or '')
            pane.path_input.setFocus()
            pane.path_input.selectAll()
        else:
            pane.content_stack.currentWidget().setFocus()

    def set_pane_path_hover(self, pane, hovered):
        pane.path_hovered = hovered
        pane.path_toggle.setVisible(hovered or pane.path_stack.currentIndex() == 1)

    def edit_pane_path(self, pane):
        self.activate_pane(pane)
        self.toggle_pane_path_mode(pane, True)

    def show_active_pane_path_input(self):
        if self.bound_pane is not None:
            self.toggle_pane_path_mode(self.bound_pane, True)

    def toggle_active_pane_path_mode(self):
        if self.bound_pane is not None:
            self.toggle_pane_path_mode(self.bound_pane)

    def pane_path_menu(self, pane, widget, point, segment=None):
        """Offer Dolphin's location actions, plus the requested folder name."""
        self.activate_pane(pane)
        current = self.folder or ''
        menu = QMenu(self)
        copy_path = menu.addAction(tr('Copier'), lambda: QApplication.clipboard().setText(current))
        copy_path.setEnabled(bool(current))

        def paste_path():
            value = QApplication.clipboard().text().strip()
            if value:
                self.toggle_pane_path_mode(pane, True)
                pane.path_input.setText(value)
                pane.path_input.setFocus()

        paste = menu.addAction(tr('Coller'), paste_path)
        paste.setEnabled(bool(QApplication.clipboard().text().strip()))
        menu.addSeparator()
        modes = QActionGroup(menu)
        modes.setExclusive(True)
        for label, editing in ((tr('Modifier'), True), (tr('Naviguer'), False)):
            action = menu.addAction(label, lambda checked=False, value=editing: self.toggle_pane_path_mode(pane, value))
            action.setCheckable(True)
            action.setChecked((pane.path_stack.currentIndex() == 1) == editing)
            modes.addAction(action)
        menu.addSeparator()
        full = menu.addAction(tr('Afficher le chemin complet'))
        full.setCheckable(True)
        full.setChecked(self.settings.value('view/full-path', False, type=bool))
        full.toggled.connect(self.set_full_breadcrumb_path)
        menu.addSeparator()
        name_path = segment if segment is not None else current
        name = Path(name_path).name if not Location.from_value(str(name_path)).is_uri else QUrl(str(name_path)).path().rstrip('/').split('/')[-1]
        name_action = menu.addAction(tr('Copier le nom du dossier'), lambda: QApplication.clipboard().setText(name or tr('/')))
        name_action.setEnabled(bool(name_path))
        menu.exec(widget.mapToGlobal(point))

    def set_full_breadcrumb_path(self, show_full):
        self.settings.setValue('view/full-path', bool(show_full))
        all_panes = (p for tab in self._tabs for p in tab.panes) if hasattr(self, '_tabs') else iter(self.panes)
        for pane in all_panes:
            if pane.native_navigator is not None:
                pane.native_navigator.set_full_path(show_full)
            self.update_pane_path_bar(pane, force=True)

    def breadcrumb_places(self):
        """Use the KDE Places names already loaded in the sidebar."""
        places = []
        for entry in getattr(self, '_current_places', ()):
            url = QUrl(str(entry.get('url') or ''))
            if url.isLocalFile():
                places.append((entry.get('group', 0), entry.get('name', ''),
                               url.toLocalFile(), entry.get('icon', 'folder')))
        return places or local_places()

    def add_breadcrumb_chevron(self, pane, parent_location):
        """A chevron opens the preceding folder's children, as in KUrlNavigator."""
        chevron = QToolButton(pane.crumbs)
        chevron.setText('›')
        chevron.setAutoRaise(True)
        chevron.setToolTip(tr('Afficher les sous-dossiers'))
        chevron.setAccessibleName(tr('Afficher les sous-dossiers'))
        chevron.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        chevron.clicked.connect(
            lambda checked=False, source=str(parent_location), anchor=chevron:
            self.show_breadcrumb_children(pane, source, anchor))
        pane.crumb_layout.addWidget(chevron)

    def show_breadcrumb_children(self, pane, source, anchor):
        menu = QMenu(anchor)

        def populate(entries):
            menu.clear()
            show_hidden = self.hidden.isChecked()
            folders = sorted((entry for entry in entries if entry.get('directory')
                              and (show_hidden or not str(entry.get('name', '')).startswith('.'))),
                             key=lambda entry: str(entry.get('name', '')).casefold())
            for entry in folders:
                target = str(entry.get('url') or '')
                if not target:
                    continue
                action = menu.addAction(str(entry.get('name') or target))
                action.triggered.connect(
                    lambda checked=False, destination=target:
                    self.run_in_pane(pane, self.navigate, destination))
            if not menu.actions():
                menu.addAction(tr('Aucun sous-dossier')).setEnabled(False)

        tool = services.tool_path('mirivue-kio-list')
        local = QUrl(source)
        if not tool and (not local.scheme() or local.isLocalFile()):
            folder = local.toLocalFile() if local.isLocalFile() else source
            try:
                with os.scandir(folder) as listing:
                    entries = [{'name': item.name, 'url': item.path, 'directory': item.is_dir()}
                               for item in listing]
            except OSError:
                entries = []
            populate(entries)
            menu.aboutToHide.connect(menu.deleteLater)
            menu.popup(anchor.mapToGlobal(anchor.rect().bottomLeft()))
            return

        if not tool:
            menu.deleteLater()
            return
        waiting = menu.addAction(tr('Chargement…'))
        waiting.setEnabled(False)
        process = QProcess(menu)
        timeout = QTimer(menu)
        timeout.setSingleShot(True)
        timeout.timeout.connect(process.kill)

        def finished(*_args):
            timeout.stop()
            if not menu.isVisible():
                menu.deleteLater()
                return
            try:
                payload = json.loads(bytes(process.readAllStandardOutput()).splitlines()[-1])
                populate(payload.get('entries', []) if payload.get('ok') else [])
            except (ValueError, IndexError):
                populate([])

        process.finished.connect(finished)
        def close_menu():
            if process.state() == QProcess.ProcessState.NotRunning:
                menu.deleteLater()
            else:
                process.kill()

        menu.aboutToHide.connect(close_menu)
        process.errorOccurred.connect(lambda _error: finished() if process.state() == QProcess.ProcessState.NotRunning else None)
        process.start(tool, [source])
        timeout.start(30000)
        menu.popup(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def update_pane_path_bar(self, pane, force=False):
        if not hasattr(pane, tr('path_stack')):
            return
        # While navigate() is running, the active folder is held on the window
        # until capture_pane() stores it back on the pane.  Use that fresh value
        # so a double-click updates the breadcrumb immediately.
        folder = self.folder if pane is self.bound_pane else pane.folder
        if pane.native_navigator is not None:
            self.sync_native_navigator_state(pane)
            pane.native_navigator.set_url(folder)
            if hasattr(self, '_tabs') and pane is self.bound_pane:
                self.refresh_tab_title(self._active_tab)
            return
        pane.path_input.setText(folder or '')
        # Dolphin keeps one KUrlNavigator alive per view and changes it only
        # when that view's URL changes. Keep our existing breadcrumb widgets
        # too: worker progress, focus and selection updates must not rebuild
        # the location bar.
        show_full = self.settings.value('view/full-path', False, type=bool)
        if not force and pane.rendered_path == (folder or '') and pane.rendered_full_path == show_full:
            return
        pane.rendered_path = folder or ''
        pane.rendered_full_path = show_full
        while pane.crumb_layout.count():
            item = pane.crumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not folder:
            pane.crumb_layout.addStretch()
            return
        location = Location.from_value(folder)
        if location.is_uri:
            url = QUrl(location.value)
            parts = [part for part in url.path().split('/') if part]
            if url.scheme().casefold() == 'trash':
                self.add_breadcrumb_chevron(pane, 'trash:/')
                trash_button = QPushButton(tr('Corbeille'), pane.crumbs)
                trash_button.setIcon(themed_icon('user-trash', self))
                if not parts:
                    font = trash_button.font()
                    font.setBold(True)
                    trash_button.setFont(font)
                self.style_crumb(trash_button)
                trash_button.setToolTip('trash:/')
                trash_button.clicked.connect(
                    lambda checked=False: self.run_in_pane(pane, self.navigate, 'trash:/'))
                pane.crumb_layout.addWidget(trash_button)
            archive_index = next((i for i, part in enumerate(parts) if archive_protocol(part)), None) if url.scheme().casefold() in ARCHIVE_PROTOCOLS else None
            previous = 'trash:/' if url.scheme().casefold() == 'trash' else QUrl(url)
            if isinstance(previous, QUrl):
                previous.setPath('/')
                previous = previous.toString()
            for position, part in enumerate(parts):
                self.add_breadcrumb_chevron(pane, previous)
                if archive_index is not None and position < archive_index:
                    target_value = '/' + '/'.join(parts[:position + 1])
                else:
                    target = QUrl(url)
                    target.setPath('/' + '/'.join(parts[:position + 1]))
                    target_value = target.toString()
                previous = target_value
                button = QPushButton(part, pane.crumbs)
                if position == len(parts) - 1:
                    font = button.font()
                    font.setBold(True)
                    button.setFont(font)
                self.style_crumb(button)
                button.setToolTip(target_value)
                button.clicked.connect(lambda checked=False, target_url=target_value: self.run_in_pane(pane, self.navigate, target_url))
                pane.crumb_layout.addWidget(button)
            pane.crumb_layout.addStretch()
            QTimer.singleShot(0, lambda scroll=pane.crumb_scroll: reveal_breadcrumb_end(scroll))
            return
        path = Path(folder)
        parts = local_place_breadcrumb(path, self.breadcrumb_places(), Path.home(), tr('Dossier personnel'), show_full=show_full)
        for position, (part, title) in enumerate(parts):
            self.add_breadcrumb_chevron(pane, part.parent if position == 0 else parts[position - 1][0])
            button = QPushButton(title, pane.crumbs)
            if part == path:
                font = button.font()
                font.setBold(True)
                button.setFont(font)
            self.style_crumb(button)
            button.setToolTip(str(part))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, b=button, target=part: self.path_menu(b, target, pos))
            button.clicked.connect(lambda checked=False, target=str(part): self.run_in_pane(pane, self.navigate, target))
            pane.crumb_layout.addWidget(button)
        pane.crumb_layout.addStretch()
        QTimer.singleShot(0, lambda scroll=pane.crumb_scroll: reveal_breadcrumb_end(scroll))

    def sync_pane_path_bars(self):
        for pane in self.panes:
            pane.path_bar.setVisible(self.split_enabled or pane is self.bound_pane)
            self.update_pane_path_bar(pane)
        if self.pane_path_separator is not None:
            self.pane_path_separator.setVisible(self.split_enabled)
        self.style_pane_path_bars()
        self.sync_path_toolbar_alignment()

    def sync_path_toolbar_alignment(self, *_args):
        if not hasattr(self, tr('left_toolbar_group')):
            return
        # Align the paths with the file views while Places is visible. When
        # Places is hidden, the commands keep their natural width.
        # Use mapped widget coordinates instead of splitter sizes: the main
        # layout has its own margins and the toolbar has a spacing value. This
        # makes the left edge exact after either splitter or window resizing.
        pane_left = self.navigation_bar.mapFromGlobal(
            self.pane_splitter.mapToGlobal(QPoint(0, 0))
        ).x()
        left_x = self.navigation_bar.mapFromGlobal(
            self.left_toolbar_group.mapToGlobal(QPoint(0, 0))
        ).x()
        toolbar_gap = self.navigation_bar.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarItemSpacing)
        # The toolbar may stretch a QWidgetAction well beyond its sizeHint.
        # Cap the command group at the Places/view boundary so the navigator
        # follows the view, as in Dolphin.  A maximum (unlike a fixed width)
        # does not make this boundary a minimum size for the main window.
        toolbar_changed = False
        if self.places_panel.isVisible():
            command_width = max(0, pane_left - left_x - toolbar_gap)
            if self.left_toolbar_group.maximumWidth() != command_width:
                self.left_toolbar_group.setMaximumWidth(command_width)
                toolbar_changed = True
            if self.left_toolbar_group.preferred_width != command_width:
                self.left_toolbar_group.setPreferredWidth(command_width)
                toolbar_changed = True
        else:
            if self.left_toolbar_group.preferred_width is not None:
                self.left_toolbar_group.setPreferredWidth(None)
                toolbar_changed = True
            natural_width = self.left_toolbar_group.sizeHint().width()
            if self.left_toolbar_group.maximumWidth() != natural_width:
                self.left_toolbar_group.setMaximumWidth(natural_width)
                toolbar_changed = True
        # Applying the new left width changes the central toolbar geometry.
        # Force that small layout pass before mapping the splitter handle.
        if toolbar_changed:
            self.navigation_bar.layout().invalidate()
            self.navigation_bar.layout().activate()
        if not self.split_enabled:
            # With one view the path container already starts immediately
            # after the Places-width toolbar group.  Let its sole bar expand
            # normally; retaining a fixed width from the split calculation
            # centers a stale, narrower bar and creates a second left offset.
            pane = self.bound_pane or (self.panes[0] if self.panes else None)
            if pane is not None and pane.path_bar.maximumWidth() != 16777215:
                pane.path_bar.setMinimumWidth(0)
                pane.path_bar.setMaximumWidth(16777215)
                pane.path_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                self.pane_path_layout.invalidate()
                self.pane_path_layout.activate()
            if pane is not None and pane.native_navigator is None:
                self.schedule_breadcrumb_reveal()
            return
        path_width_changed = False
        fixed_path_widths = []
        for index, pane in enumerate(self.panes):
            if index < len(self.panes) - 1:
                # Map the real splitter handle into the toolbar.  This is
                # more exact than a stored width after Qt redistributes space
                # during a window resize.
                handle = self.pane_splitter.handle(self.pane_splitter.indexOf(self.panes[index + 1].container))
                divider_x = self.pane_path_container.mapFromGlobal(
                    handle.mapToGlobal(QPoint(0, 0))
                ).x()
                width = max(0, divider_x - self._pane_path_divider_gap)
                if pane.path_bar.maximumWidth() != width:
                    pane.path_bar.setMinimumWidth(0)
                    pane.path_bar.setMaximumWidth(width)
                    path_width_changed = True
                fixed_path_widths.append(width)
        if self.pane_path_separator is not None:
            separator_width = self.pane_splitter.handleWidth() + self._pane_path_divider_gap * 2
            if self.pane_path_separator.width() != separator_width:
                self.pane_path_separator.setFixedWidth(separator_width)
                path_width_changed = True
        # Give the final bar exactly the remaining toolbar width.  Relying on
        # its size hint lets it keep an old minimum width at intermediate
        # window sizes, which can make it overlap the divider or the first bar.
        if self.panes:
            separator_width = self.pane_path_separator.width() if self.pane_path_separator is not None and self.pane_path_separator.isVisible() else 0
            remaining = max(0, self.pane_path_container.width() - separator_width - sum(fixed_path_widths))
            if self.panes[-1].path_bar.maximumWidth() != remaining:
                self.panes[-1].path_bar.setMinimumWidth(0)
                self.panes[-1].path_bar.setMaximumWidth(remaining)
                path_width_changed = True
        # Width constraints changed above; lay the bars out immediately so a
        # newly enabled split view cannot retain its previous divider offset.
        if path_width_changed:
            self.pane_path_layout.invalidate()
            self.pane_path_layout.activate()
        if any(pane.native_navigator is None for pane in self.panes):
            self.schedule_breadcrumb_reveal()

    def schedule_path_toolbar_alignment(self, *_args):
        """Recalculate the independent address bar at most once per frame."""
        if not self._path_alignment_drag_timer.isActive():
            self._path_alignment_drag_timer.start()

    def align_path_during_drag(self, *_args):
        """Follow the splitter in the same resize event as Dolphin does."""
        if getattr(self, '_aligning_path_during_drag', False):
            return
        self._aligning_path_during_drag = True
        try:
            self.sync_path_toolbar_alignment()
        finally:
            self._aligning_path_during_drag = False

    def schedule_breadcrumb_reveal(self):
        if not self._breadcrumb_reveal_timer.isActive():
            self._breadcrumb_reveal_timer.start(0)

    def reveal_current_breadcrumbs(self):
        """Keep the current folder visible once Qt has calculated bar widths."""
        for pane in getattr(self, 'panes', ()):
            if pane.native_navigator is None and pane.path_stack.currentIndex() == 0:
                scroll = pane.crumb_scroll.horizontalScrollBar()
                scroll.setValue(scroll.maximum())
        if hasattr(self, 'crumb_scroll') and self.address_stack.currentIndex() == 0:
            scroll = self.crumb_scroll.horizontalScrollBar()
            scroll.setValue(scroll.maximum())

    def create_second_pane(self):
        from .app import VideoModel, FileSortProxy
        self.capture_pane()
        original = self.bound_pane
        self.model = VideoModel(self.settings.value('view/date-format', 'locale'))
        self.proxy = FileSortProxy()
        self.proxy.sort_mode = self.settings.value('sorting/mode', 0, type=int)
        self.proxy.hidden_last = self.settings.value('sorting/hidden-last', False, type=bool)
        self.proxy.folders_first = self.settings.value('sorting/folders-first', True, type=bool)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.table = DetailsView()
        self.table.setModel(self.proxy)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        right_state = self.settings.value('columns-pane-right-v1')
        header.restoreState(right_state if right_state is not None else original.table.horizontalHeader().saveState())
        if right_state is not None and self.settings.value('columns-pane-right-role-count', 37, type=int) < self.model.columnCount():
            for column in (37, 38, 39):
                self.table.setColumnHidden(column, True)
        self.table.setColumnHidden(10, True)
        self.table.setColumnHidden(12, True)
        self.table.setColumnHidden(15, True)
        self.table.setColumnHidden(16, True)
        self.table.setColumnHidden(36, True)
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(False)
        if header.visualIndex(0) != 0:
            header.moveSection(header.visualIndex(0), 0)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.icons = IconView()
        self.icons.setModel(self.proxy)
        self.icons.setViewMode(QListView.ViewMode.IconMode)
        self.icons.setResizeMode(QListView.ResizeMode.Adjust)
        self.icons.setMovement(QListView.Movement.Snap)
        self.icons.setWordWrap(True)
        self.compact = IconView()
        self.compact.setModel(self.proxy)
        self.compact.setViewMode(QListView.ViewMode.ListMode)
        self.compact.setFlow(QListView.Flow.TopToBottom)
        self.compact.setWrapping(True)
        self.compact.setResizeMode(QListView.ResizeMode.Adjust)
        self.compact.setMovement(QListView.Movement.Static)
        native_small_icon = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize, None, self.compact)
        self.compact.setIconSize(QSize(native_small_icon, native_small_icon))
        self.compact.setUniformItemSizes(True)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.table)
        self.content_stack.addWidget(self.icons)
        self.content_stack.addWidget(self.compact)
        self.content_stack.setCurrentIndex(original.content_stack.currentIndex())
        self.folder = None
        self.history = []
        self.history_position = -1
        self.pending_navigation = None
        self.parent_selection = None
        self.worker = None
        self.thumbnail_worker = None
        self.folder_size_worker = None
        self.scanning = False
        self.scan_queued = False
        self.notices = []
        self.search_active = False
        self.search_root = ''
        self.search_criteria = {}
        pane = self.register_pane()
        self.model.path_edit_allowed = lambda path: not self.paths_locked([path])
        self.model.show_thumbnails = self.preview_action.isChecked()
        self.apply_details_zoom()
        self.apply_icon_zoom()
        self.apply_compact_zoom()
        for view in (self.table, self.icons, self.compact):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            view.setDragEnabled(True)
            view.activated.connect(lambda index, p=pane: self.pane_command(p, self.open_video, index))
            view.customContextMenuRequested.connect(lambda pos, p=pane: self.pane_command(p, self.context_menu, pos))
        self.configure_pane_extra_information(pane)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header.customContextMenuRequested.connect(lambda pos, h=header: self.show_header_menu(h, pos))
        self.capture_pane()
        self.bind_pane(original)
        return pane

    def schedule_pane_splitter_save(self, *_args):
        """Persist the final divider position after pointer movement stops."""
        self._pane_splitter_save_timer.start()

    def save_pane_splitter_sizes(self, *_args):
        if getattr(self, '_restoring_session', False):
            return
        if self.split_enabled and len(self.panes) > 1:
            current = self.pane_splitter.sizes()
            sizes = [current[self.pane_splitter.indexOf(p.container)] for p in self.panes]
            if len(sizes) == 2 and all(size > 0 for size in sizes):
                if hasattr(self, '_tabs'):
                    self._tabs[self._active_tab].splitter_sizes = sizes
                self.settings.setValue('panes/splitter-sizes', sizes)

    def set_split_view(self, enabled, navigate_new=True):
        if enabled == self.split_enabled:
            return
        if not enabled:
            self._pane_splitter_save_timer.stop()
            self.save_pane_splitter_sizes()
        self.capture_pane()
        initial_folder = self.folder or str(Path.home())
        self.split_enabled = enabled
        if enabled:
            pane = self.create_second_pane() if len(self.panes) == 1 else None
            for p in self.panes:
                p.container.show()
                p.label.hide()
            saved_sizes = self.settings.value('panes/splitter-sizes', [])
            try:
                saved_sizes = [max(1, int(size)) for size in saved_sizes]
            except (TypeError, ValueError):
                saved_sizes = []
            tab_sizes = self._tabs[self._active_tab].splitter_sizes if hasattr(self, '_tabs') else None
            widths = tab_sizes if tab_sizes else saved_sizes if len(saved_sizes) == 2 else [1, 1]
            all_sizes = [0] * self.pane_splitter.count()
            for active_pane, width in zip(self.panes, widths):
                all_sizes[self.pane_splitter.indexOf(active_pane.container)] = width
            self.pane_splitter.setSizes(all_sizes)
            if pane and navigate_new:
                self.run_in_pane(pane, self.navigate, initial_folder)
        else:
            for p in self.panes:
                p.container.setVisible(p is self.bound_pane)
                p.label.hide()
        self.split_action.setChecked(enabled)
        if hasattr(self, '_tabs'):
            tab = self._tabs[self._active_tab]
            tab.split = enabled
            tab.separator = self.pane_path_separator
        self.sync_pane_path_bars()
        # Creating or hiding the second view changes splitter geometry only
        # during the next layout pass.
        QTimer.singleShot(0, self.sync_path_toolbar_alignment)
        self.sync_pane_controls()
        self.active_view().setFocus()

    def activate_pane(self, pane, *, focus_view=True):
        if getattr(pane, '_closed', False):
            return
        if pane is self.bound_pane:
            return
        previous = self.bound_pane
        self.capture_pane()
        self.bind_pane(pane, style_path=False)
        self.refresh_tab_title(self._active_tab)
        self.refresh_delete_availability()
        # Set the active view synchronously in response to the press, then
        # update shared controls without performing
        # disk-space I/O (each pane already keeps its own footer information).
        view = pane.content_stack.currentWidget()
        if focus_view and view in (pane.table, pane.icons, pane.compact):
            view.setFocus(Qt.FocusReason.MouseFocusReason)
        affected = tuple(p for p in self.panes if p is previous or p is pane)
        self.style_pane_path_bars(affected)
        self.update_pane_activation_emphasis(affected)
        # Flush the small active indicators now; shared navigation/status
        # widgets are not part of Dolphin's active-view switch and can update
        # on the next event-loop turn without delaying the click feedback.
        # Repainting every cell synchronously would block the input event.
        QTimer.singleShot(0, self.finish_pane_activation)

    def activate_pane_from_empty_area(self, pane):
        """Activate the pane and restore Dolphin's breadcrumb presentation."""
        self.activate_pane(pane)
        if (pane.native_navigator is not None and pane.native_navigator.is_editable()) or pane.path_stack.currentIndex() == 1:
            self.toggle_pane_path_mode(pane, False)

    def finish_pane_activation(self):
        self.sync_pane_controls(update_emphasis=False, refresh_disk=False)
        self.update_delete_button()

    def activate_event_pane(self, watched, event):
        if not hasattr(self, tr('panes')) or self._pane_context_depth:
            return
        if event.type() not in (QEvent.Type.FocusIn, QEvent.Type.Wheel, QEvent.Type.ContextMenu, QEvent.Type.MouseButtonPress):
            return
        if event.type() == QEvent.Type.FocusIn and event.reason() == Qt.FocusReason.MouseFocusReason:
            # Mouse activation is handled by the view's `pressed` signal after
            # Qt has processed the input. Avoid doing style work during its
            # nested focus event.
            return
        for pane in self.panes:
            # Focus belongs to KItemListContainer (or its editor), not to the
            # compatibility facade. Follow the real widget ancestry.
            is_view = isinstance(watched, QWidget) and any(
                watched is view or view.isAncestorOf(watched)
                for view in (pane.table, pane.icons, pane.compact))
            is_header = watched in (pane.table.horizontalHeader(), pane.table.horizontalHeader().viewport())
            if event.type() == QEvent.Type.MouseButtonPress and (is_view or is_header):
                # Views activate on their `pressed` signal; headers have their
                # own sectionPressed connection. Keep this filter for sidebar
                # labels only.
                continue
            if is_view or is_header or watched is pane.label:
                if pane.container.isVisible():
                    self.activate_pane(pane, focus_view=event.type() != QEvent.Type.FocusIn)
                break

    def pane_command(self, pane, callback, *args):
        if getattr(pane, '_closed', False):
            return
        self.activate_pane(pane)
        return callback(*args)

    def pane_selection_changed(self, pane):
        if getattr(pane, '_closed', False):
            return
        if pane is self.bound_pane:
            # QAction shortcuts consult enabled state immediately; waiting for
            # the deferred footer refresh can discard a quick Delete press.
            self.refresh_delete_availability()
            if not self._delete_button_update_pending:
                self._delete_button_update_pending = True
                QTimer.singleShot(0, self.flush_delete_button_update)
        else:
            self.update_selection_info(pane=pane)

    def flush_delete_button_update(self):
        self._delete_button_update_pending = False
        self.update_delete_button()

    def run_in_pane(self, pane, callback, *args):
        if getattr(pane, '_closed', False):
            return
        original = self.bound_pane
        if pane is original:
            result = callback(*args)
            self.capture_pane()
            return result
        self.capture_pane()
        self._pane_context_depth += 1
        self.bind_pane(pane)
        try:
            return callback(*args)
        finally:
            self.capture_pane()
            self.bind_pane(original)
            self._pane_context_depth -= 1
            self.sync_pane_controls()

    def run_in_pane_silent(self, pane, callback, *args):
        if getattr(pane, '_closed', False):
            return
        tr('Apply a high-frequency worker batch without repainting all panes.')
        original = self.bound_pane
        if pane is original:
            return callback(*args)
        self.capture_pane()
        self._pane_context_depth += 1
        self.bind_pane(pane)
        try:
            return callback(*args)
        finally:
            self.capture_pane()
            self.bind_pane(original)
            self._pane_context_depth -= 1

    def pane_callback(self, callback):
        pane = getattr(self, tr('bound_pane'), None)
        if pane is None:
            return callback
        return lambda *args: self.run_in_pane(pane, callback, *args)

    def sync_pane_controls(self, update_emphasis=True, refresh_disk=True):
        native_places = getattr(self, 'native_places', None)
        if native_places is not None:
            native_places.set_url(self.folder)
        if self.address.text() != (self.folder or ''):
            self.address.setText(self.folder or '')
            if self.folder:
                self.update_crumbs()
        self.update_navigation()
        if refresh_disk:
            self.update_disk_space()
        active_button = self.view_buttons.button(self.content_stack.currentIndex())
        if active_button is not None:
            active_button.setChecked(True)
        if hasattr(self, 'details_view_action'):
            mode = self.content_stack.currentIndex()
            (self.details_view_action if mode == 0 else self.icons_view_action if mode == 1 else self.compact_view_action).setChecked(True)
        self.search_button.setChecked(not self.search_panel.isHidden())
        self.preview_action.blockSignals(True)
        self.preview_action.setChecked(self.model.show_thumbnails)
        self.preview_action.blockSignals(False)
        self.preview_button.blockSignals(True)
        self.preview_button.setChecked(self.model.show_thumbnails)
        self.preview_button.blockSignals(False)
        self.choose.setEnabled(not self.scanning)
        self.refresh.setEnabled(not self.scanning)
        self.recursive.setEnabled(not self.scanning)
        self.stop.setEnabled(self.scanning)
        self.stop.setText(tr('Arrêter la recherche') if self.search_active else tr('Arrêter le chargement du dossier'))
        for control in (self.search_start, self.search_scope, self.search_kind, self.state_filter, self.search_more):
            control.setEnabled(not self.scanning)
        any_scanning = any(pane.scanning for pane in self.panes)
        if any_scanning:
            self.bar.setRange(0, 0)
        self.refresh_scan_progress_visibility()
        self.update_summary()
        self.update_empty_state()
        self.update_pane_titles()
        self.sync_pane_path_bars()
        if update_emphasis:
            self.update_pane_emphasis()

    def update_pane_emphasis(self):
        """Refresh the theme palette after a view or system theme change."""
        if not hasattr(self, tr('panes')):
            return
        self.sync_pane_scrollbar_policies()
        for pane in self.panes:
            if pane.container.styleSheet():
                pane.container.setStyleSheet('')
            pane.container.setAutoFillBackground(False)
        self.update_pane_activation_emphasis(self.panes)

    def update_pane_activation_emphasis(self, panes):
        """Let the native engine apply Dolphin's KDE View background policy."""
        for pane in panes:
            active = pane is self.bound_pane or not pane.container.isVisible()
            pane.model.semantic_color_group = (QPalette.ColorGroup.Active if active else QPalette.ColorGroup.Inactive)
            # Palette roles and opacity belong to the native graphics viewport,
            # not to the three Python compatibility facades around it.
            for view in (pane.table, pane.icons, pane.compact):
                if view.testAttribute(Qt.WidgetAttribute.WA_SetPalette):
                    view.setPalette(QPalette())
            pane.table.setPaneActive(active)

    def sync_pane_scrollbar_policies(self):
        """Keep each view's native, theme-painted horizontal scrollbar enabled."""
        for pane in getattr(self, tr('panes'), ()):
            for view in (pane.table, pane.icons, pane.compact):
                policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if view.horizontalScrollBarPolicy() != policy:
                    view.setHorizontalScrollBarPolicy(policy)

    def update_pane_titles(self):
        if hasattr(self, '_tabs'):
            self.refresh_tab_title(self._active_tab)
        if not hasattr(self, tr('panes')):
            return
        self.capture_pane()
        title = self.tab_title(self.folder)
        self.setWindowTitle(title + tr(' — Mirivue'))
        for p in self.panes:
            p.label.setText((tr('●  ') if p is self.bound_pane else '') + (p.folder or tr('Dossier')))
            p.label.setToolTip(p.folder or '')
            font = p.label.font()
            font.setBold(p is self.bound_pane)
            p.label.setFont(font)

    def pane_drag(self, pane, view):
        self.activate_pane(pane)
        self.start_file_drag(view)

    def pane_drop_action(self, paths, destination, event=None):
        """Choose the native file-manager default for an internal drop.

        A drop on the same filesystem moves files; crossing filesystems
        copies them.  Ctrl and Shift keep the familiar explicit overrides.
        """
        modifiers = event.keyboardModifiers() if event is not None else Qt.KeyboardModifier.NoModifier
        if modifiers & Qt.KeyboardModifier.ControlModifier and modifiers & Qt.KeyboardModifier.ShiftModifier:
            return Qt.DropAction.LinkAction
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return Qt.DropAction.CopyAction
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return Qt.DropAction.MoveAction
        if any(Location.from_value(value).is_uri for value in [*paths, destination]):
            return Qt.DropAction.CopyAction
        try:
            target_device = os.stat(str(destination)).st_dev
            same_device = all(os.stat(str(path)).st_dev == target_device for path in paths)
        except OSError:
            same_device = True
        return Qt.DropAction.MoveAction if same_device else Qt.DropAction.CopyAction

    def pane_drop(self, pane, view, event):
        source = next((p for p in self.panes if event.source() in (p.table, p.icons, p.compact)), None)
        internal = event.mimeData().hasFormat(tr('application/x-mirivue-files'))
        if not event.mimeData().hasUrls() or (source is not None and not internal):
            view.set_drop_highlight(None)
            event.ignore()
            return
        paths = [Path(url.toLocalFile()) if url.isLocalFile() else url.toString() for url in event.mimeData().urls()]
        destination = pane.folder if pane is not self.bound_pane else self.folder
        pane_is_trash = bool(destination and not Location.from_value(destination).is_uri and Path(destination).resolve() == self.trash_directory().resolve())
        if pane_is_trash:
            destination = tr('trash:/')
        index = view.indexAt(event.position().toPoint())
        if index.isValid() and not pane_is_trash:
            row = pane.model.rows[pane.proxy.mapToSource(index).row()]
            if row.is_dir:
                destination = row.path
            else:
                index = QModelIndex()
        if not paths or not destination or not self.allow_drop_destination(paths, destination):
            view.set_drop_highlight(None)
            event.ignore()
            return
        view.set_drop_highlight(index)
        action = Qt.DropAction.MoveAction if pane_is_trash else self.pane_drop_action(paths, destination, event)
        possible = event.possibleActions()
        if not (possible & action):
            action = Qt.DropAction.CopyAction if possible & Qt.DropAction.CopyAction else Qt.DropAction.MoveAction if possible & Qt.DropAction.MoveAction else Qt.DropAction.IgnoreAction
        if action == Qt.DropAction.IgnoreAction:
            view.set_drop_highlight(None)
            event.ignore()
            return
        event.setDropAction(action)
        event.accept()
        if event.type() == QEvent.Type.Drop:
            view.set_drop_highlight(None)
            operation = tr('trash') if pane_is_trash else tr('link') if action == Qt.DropAction.LinkAction else tr('copy') if action == Qt.DropAction.CopyAction else tr('move')
            command_pane = source or pane
            explicit = bool(event.keyboardModifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier))
            if internal and not pane_is_trash and not explicit:
                QTimer.singleShot(0, lambda: self.pane_command(command_pane, self.drop_choices, paths, destination))
            else:
                QTimer.singleShot(0, lambda: self.pane_command(command_pane, self.drop_operation, paths, destination, operation))

    def refresh_other_panes(self, changed_paths=None):
        if not hasattr(self, tr('panes')):
            return
        self.capture_pane()
        changed = [Path(p).resolve() for p in changed_paths] if changed_paths is not None else None
        for pane in self.panes:
            if pane is self.bound_pane or not pane.folder:
                continue
            folder = Path(pane.folder)
            resolved = folder.resolve()
            if changed is not None and (not any((resolved == p or resolved in p.parents or p in resolved.parents for p in changed))):
                continue
            while not folder.is_dir() and folder != folder.parent:
                folder = folder.parent
            self.run_in_pane(pane, self.navigate, str(folder))

    def repaint_panes(self):
        if getattr(self, tr('_receiving_result'), False):
            return
        models = [p.model for p in self.panes] if hasattr(self, tr('panes')) else [self.model]
        for model in models:
            if model.rows:
                model.dataChanged.emit(model.index(0, 0), model.index(len(model.rows) - 1, model.columnCount() - 1))

    def stop_all_pane_workers(self):
        if not hasattr(self, tr('panes')):
            return
        self.capture_pane()
        for worker in list(getattr(self, tr('_visible_workers'), [])):
            if worker.isRunning():
                worker.requestInterruption()
                worker.wait()
        for p in self.panes:
            if p.worker and p.worker.isRunning():
                p.worker.cancel()
                p.worker.wait()
            if p.thumbnail_worker:
                p.thumbnail_worker.requestInterruption()
                p.thumbnail_worker.wait()
