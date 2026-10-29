# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
# Original Mirivue implementation; behavior compared with Dolphin v26.08.2.
# No Dolphin source code is copied into this module.
"""Versioned tab sessions; media profiles and analysis results stay separate."""
import json
from pathlib import Path
from PySide6.QtWidgets import QMessageBox, QCheckBox
from .i18n import tr


class SessionMixin:
    def session_snapshot(self):
        self.capture_pane()
        self.save_pane_splitter_sizes()
        self._tabs[self._active_tab].bound = self.bound_pane
        self._tabs[self._active_tab].split = self.split_enabled
        tabs = []
        for tab in self._tabs:
            panes = tab.panes if tab.split else [tab.bound]
            tabs.append(dict(locations=[str(p.folder or tab.location or Path.home()) for p in panes],
                             active=panes.index(tab.bound), split=bool(tab.split),
                             widths=tab.splitter_sizes, title=getattr(tab, 'custom_title', '')))
        return dict(version=1, tabs=tabs, active=self._active_tab)

    def save_tab_session(self):
        if getattr(self, '_tabs', None):
            self.settings.setValue('session/tabs-v1', json.dumps(self.session_snapshot(), ensure_ascii=False))
            self.settings.sync()
            from PySide6.QtCore import QSettings
            success = self.settings.status() == QSettings.Status.NoError
            if not success:
                self.show_activity_message('La session n’a pas pu être enregistrée.', 8000)
            return success
        return True

    def restore_tab_session(self):
        if self.settings.value('startup/location', 'home') != 'session':
            return False
        try:
            state = json.loads(self.settings.value('session/tabs-v1', '{}'))
        except (ValueError, TypeError, RecursionError):
            return False
        if not isinstance(state, dict) or state.get('version') != 1 or not isinstance(state.get('tabs'), list):
            return False
        tabs = [tab for tab in state['tabs'] if isinstance(tab, dict)
                and isinstance(tab.get('locations'), list) and tab['locations']
                and all(isinstance(p, str) and p for p in tab['locations'])]
        if not tabs:
            return False
        self._restoring_session = True
        try:
            for number, saved in enumerate(tabs):
                if not isinstance(saved, dict):
                    continue
                locations = saved.get('locations')
                if not isinstance(locations, list) or not locations or not all(isinstance(p, str) for p in locations):
                    continue
                first = self.startup_location_or(locations[0], str(Path.home()))
                if number or len(self._tabs) > 1:
                    self.open_new_tab(first, append=True)
                self.prime_startup_pane(self.panes[0], first)
                if saved.get('split') and len(locations) > 1:
                    self.set_split_view(True, navigate_new=False)
                    self.prime_startup_pane(self.panes[1], self.startup_location_or(locations[1], first))
                tab = self._tabs[self._active_tab]
                tab.bound = self.panes[1] if tab.split and saved.get('active') == 1 else self.panes[0]
                widths = saved.get('widths')
                if isinstance(widths, list) and len(widths) == 2 and all(type(n) is int and n > 0 for n in widths):
                    tab.splitter_sizes = widths
                tab.custom_title = str(saved.get('title', ''))
                for pane in tab.panes:
                    pane._session_listing_pending = True
                self.bind_pane(tab.bound)
                self.refresh_tab_title(self._active_tab)
            index = state.get('active', 0)
            if type(index) is not int or not 0 <= index < len(self._tabs):
                index = 0
            self.tab_bar.setCurrentIndex(index)
            self.restore_tab_splitter_sizes(self._tabs[self._active_tab])
            self.sync_pane_path_bars()
            self.sync_pane_controls()
            self._startup_browsing_prepared = True
            return True

        finally:
            self._restoring_session = False

    def restore_detached_tab(self, saved):
        locations = saved.get('locations', [])
        if not locations or not all(isinstance(p, str) for p in locations):
            raise ValueError('Onglet détaché invalide')
        primary = self.startup_location_or(locations[0], str(Path.home()))
        self.prime_startup_pane(self.panes[0], primary)
        if saved.get('split') and len(locations) > 1:
            self.set_split_view(True, navigate_new=False)
            self.prime_startup_pane(self.panes[1], self.startup_location_or(locations[1], primary))
        tab = self._tabs[self._active_tab]
        tab.custom_title = str(saved.get('title', ''))
        if saved.get('active') == 1 and self.split_enabled:
            self.bind_pane(self.panes[1])
            tab.bound = self.panes[1]
        widths = saved.get('widths')
        if isinstance(widths, list) and len(widths) == 2 and all(type(n) is int and n > 0 for n in widths):
            tab.splitter_sizes = widths
        self.restore_tab_splitter_sizes(tab)
        self.sync_pane_path_bars()
        self.sync_pane_controls()

    def confirm_tab_window_close(self):
        if (len(self._tabs) < 2 or self.settings.value('startup/location', 'home') == 'session'
                or not self.settings.value('window/confirm-close-multiple-tabs', True, type=bool)):
            return True
        box = QMessageBox(self)
        box.setWindowTitle(tr('Fermer les onglets'))
        box.setText(tr('Cette fenêtre contient plusieurs onglets.'))
        box.setInformativeText(tr('Voulez-vous fermer la fenêtre ou uniquement l’onglet courant ?'))
        quit_button = box.addButton(tr('Fermer la fenêtre'), QMessageBox.ButtonRole.YesRole)
        current_button = box.addButton(tr('Fermer l’onglet courant'), QMessageBox.ButtonRole.NoRole)
        cancel_button = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel_button)
        remember = QCheckBox(tr('Ne plus demander'))
        box.setCheckBox(remember)
        box.exec()
        if box.clickedButton() is cancel_button or box.clickedButton() is None:
            return False
        if remember.isChecked():
            self.settings.setValue('window/confirm-close-multiple-tabs', False)
        if box.clickedButton() is current_button:
            self.close_tab(self._active_tab)
            return False
        return box.clickedButton() is quit_button
