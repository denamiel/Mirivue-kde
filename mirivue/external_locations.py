# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
# Original Mirivue implementation; behavior compared with Dolphin v26.08.2.
# No Dolphin source code is copied into this module.
"""Route desktop requests to existing tabs without disturbing their views."""
from pathlib import Path
import json
import os

from PySide6.QtCore import QItemSelectionModel, QTimer, QUrl, QProcess

from .item_presentation import map_file_index
from .locations import Location


def location_key(value):
    if not value:
        return ''
    location = Location.from_value(value)
    url = QUrl(location.uri) if location.is_uri else QUrl.fromLocalFile(str(Path(value).absolute()))
    flags = (QUrl.UrlFormattingOption.NormalizePathSegments |
             QUrl.UrlFormattingOption.StripTrailingSlash)
    # PySide exposes QUrl::FormattingOptions as ComponentFormattingOption.
    return url.adjusted(QUrl.ComponentFormattingOption(flags.value)).toString()


class ExternalLocationsMixin:
    def find_open_location(self, folder):
        key = location_key(folder)
        order = [self._active_tab] + [i for i in range(len(self._tabs)) if i != self._active_tab]
        for index in order:
            tab = self._tabs[index]
            panes = tab.panes if tab.split else [tab.bound]
            for pane in panes:
                if pane.search_active:
                    continue
                if location_key(pane.folder or tab.location) == key:
                    return index, pane
        return None

    def apply_external_selection(self, pane):
        """Select a desktop request immediately, or after its listing finishes."""
        files = getattr(pane, 'pending_external_files', [])
        if not getattr(pane, 'external_request_pending', False):
            return
        if pane.folder is None or getattr(pane, '_session_listing_pending', False):
            return
        if files:
            wanted = {str(path) for path in files}
            selected = []
            for row, item in enumerate(pane.model.rows):
                if str(item.path) in wanted:
                    index = map_file_index(pane.proxy, pane.model.index(row, 0))
                    if index.isValid():
                        selected.append(index)
            for view in (pane.table, pane.icons, pane.compact):
                selection = view.selectionModel()
                selection.clearSelection()
                for index in selected:
                    selection.select(index, QItemSelectionModel.SelectionFlag.Select |
                                     QItemSelectionModel.SelectionFlag.Rows)
                if selected:
                    selection.setCurrentIndex(selected[0], QItemSelectionModel.SelectionFlag.NoUpdate)
                    view.scrollTo(selected[0])
        properties = getattr(pane, 'pending_external_properties', False)
        pane.external_request_pending = False
        pane.pending_external_files = []
        pane.pending_external_properties = False
        if properties and files:
            QTimer.singleShot(0, lambda p=pane: self.run_in_pane(p, self.basic_properties))

    def open_requests_in_new_window(self, requests, *, properties=False, split=False,
                                    activation_token='', detached_tab=None):
        launcher = Path(__file__).resolve().parent.parent / 'Lancer.sh'
        arguments = ['--new-window']
        if properties:
            arguments.append('--show-properties')
        if split:
            arguments.append('--split')
        if detached_tab is not None:
            arguments += ['--session-tab', json.dumps(detached_tab, ensure_ascii=False)]
        if requests:
            from .window_instances import request_payload
            arguments += ['--locations-json', json.dumps(request_payload(requests), ensure_ascii=False)]
        process = QProcess(self)
        from PySide6.QtCore import QProcessEnvironment
        environment = QProcessEnvironment.systemEnvironment()
        if activation_token:
            environment.insert('XDG_ACTIVATION_TOKEN', activation_token)
        process.setProcessEnvironment(environment)
        process.setProgram(str(launcher))
        process.setArguments(arguments)
        result = process.startDetached()
        process.deleteLater()
        started = result[0] if isinstance(result, tuple) else result
        if not started:
            self.show_activity_message('Impossible d’ouvrir une nouvelle fenêtre Mirivue.', 5000)
        return bool(started)

    def receive_launch_payload(self, payload):
        from .window_instances import validated_requests, normalize_payload
        payload = normalize_payload(payload)
        if payload is None:
            return
        requests = validated_requests(payload)
        if requests:
            self.open_external_locations(requests, properties=bool(payload.get('properties')),
                activate_first=payload.get('activate_first', True), split=bool(payload.get('split')),
                activation_token=str(payload.get('activation_token') or ''),
                force_tabs=bool(payload.get('force_tabs')), across_windows=False, external_policy=True)

    def open_external_locations(self, requests, *, properties=False, activate_first=True,
                                split=False, activation_token='', force_tabs=False, across_windows=True, external_policy=None):
        requests = list(requests)
        external_policy = activate_first if external_policy is None else external_policy
        from PySide6.QtDBus import QDBusConnection
        if across_windows and activate_first and QDBusConnection.sessionBus().isConnected():
            from .window_instances import route_to_windows
            def completed(result):
                if self.closing:
                    return
                if result.remaining:
                    self.open_external_locations(result.remaining, properties=properties,
                        activate_first=activate_first and not bool(result.delivered or result.uncertain),
                        split=split, activation_token=activation_token, force_tabs=force_tabs,
                        across_windows=False, external_policy=external_policy)
                if result.uncertain:
                    self.show_activity_message('Une fenêtre ne confirme pas la demande. Elle n’a pas été répétée pour éviter un doublon.', 8000)
            route_to_windows(requests, window=self, completion=completed,
                             properties=properties, split=split, activation_token=activation_token)
            return
        activated = not activate_first
        missing = []
        for request in requests:
            found = self.find_open_location(request.folder)
            if found is None:
                missing.append(request)
                continue
            index, pane = found
            if not activated:
                self.restore_window(activation_token) if activation_token else self.restore_window()
                if self._active_tab != index:
                    self.tab_bar.setCurrentIndex(index)
                self.activate_pane(pane)
                activated = True
            pane.external_request_pending = True
            pane.pending_external_files = [Path(path) for path in request.files]
            pane.pending_external_properties = bool(properties)
            if not pane.scanning:
                self.apply_external_selection(pane)
        if missing and external_policy and not force_tabs and self.settings.value(
                'startup/allow_multiple_instances', False, type=bool):
            self.open_requests_in_new_window(missing, properties=properties, split=split,
                                             activation_token=activation_token)
            return
        if split and missing:
            previous = self._tabs[self._active_tab]
            first_tab = None
            for offset in range(0, len(missing), 2):
                first = missing[offset]
                self.open_new_tab(first.folder, active=True, external_files=first.files,
                                  external_properties=properties)
                tab = self._tabs[self._active_tab]
                if first_tab is None:
                    first_tab = tab
                if offset + 1 < len(missing):
                    second = missing[offset + 1]
                    self.set_split_view(True, navigate_new=False)
                    pane = self.panes[1]
                    pane.external_request_pending = True
                    pane.pending_external_files = [Path(path) for path in second.files]
                    pane.pending_external_properties = bool(properties)
                    self.run_in_pane(pane, self.navigate, second.folder)
            target = first_tab if not activated else previous
            self.tab_bar.setCurrentIndex(next(i for i,t in enumerate(self._tabs) if t is target))
            if not activated:
                self.restore_window(activation_token) if activation_token else self.restore_window()
            return
        insertion_index = None
        for request in missing:
            if not activated:
                self.restore_window(activation_token) if activation_token else self.restore_window()
            pane = self.open_new_tab(request.folder, active=not activated, external_files=request.files,
                              external_properties=properties, insert_index=insertion_index)
            insertion_index = next(i for i,t in enumerate(self._tabs) if t.bound is pane) + 1
            activated = True
