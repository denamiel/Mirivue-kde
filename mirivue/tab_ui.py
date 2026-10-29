# SPDX-FileCopyrightText: 2014 Emmanuel Pescosta <emmanuelpescosta099@gmail.com>
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: GPL-2.0-or-later
# Python adaptation of Dolphin v26.08.2 src/dolphintabbar.cpp gestures/menus.
# Original: https://invent.kde.org/system/dolphin/-/blob/v26.08.2/src/dolphintabbar.cpp
# Adaptations: Python/Qt signal routing, Mirivue pane/transfer API, tab lifetimes.
"""Tab gestures and menus matching Dolphin 26.08.2, using Qt's theme."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QTabBar, QMenu, QInputDialog
from .i18n import tr


class DolphinTabBar(QTabBar):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.setSelectionBehaviorOnRemove(QTabBar.SelectionBehavior.SelectPreviousTab)
        self._middle_pressed = -1
        self.setAcceptDrops(True)
        self._hover_index = -1
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(800)
        self._hover_timer.timeout.connect(self._activate_hovered_tab)

    def _activate_hovered_tab(self):
        if 0 <= self._hover_index < self.count():
            self.setCurrentIndex(self._hover_index)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_pressed = self.tabAt(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0 and index == self._middle_pressed:
                self.tabCloseRequested.emit(index)
            self._middle_pressed = -1
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def duplicate_tab(self, index):
        if not 0 <= index < len(self.window._tabs):
            index = self.currentIndex()
        tab = self.window._tabs[index]
        location = (self.window.folder if tab.bound is self.window.bound_pane else tab.bound.folder) or tab.location
        self.window.open_new_tab(location)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.duplicate_tab(self.tabAt(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def create_context_menu(self, index):
        menu = QMenu(self)
        def add(label, icon, callback, enabled=True):
            action = menu.addAction(QIcon.fromTheme(icon), tr(label), callback)
            action.setEnabled(enabled)
            return action
        add('Nouvel onglet', 'tab-new', lambda: self.duplicate_tab(index))
        add('Détacher l’onglet', 'tab-detach', lambda: self.window.detach_tab(index), self.count() > 1)
        menu.addSeparator()
        add('Renommer l’onglet…', 'edit-rename', lambda: self.window.rename_tab(index))
        menu.addSeparator()
        for label, icon, indices in (
            ('Fermer les autres onglets', 'tab-close-other', [i for i in range(self.count()) if i != index]),
            ('Fermer les onglets à gauche', 'go-previous', list(range(index))),
            ('Fermer les onglets à droite', 'go-next', list(range(index + 1, self.count()))),
        ):
            add(label, icon, lambda positions=indices: self.window.close_tab_group(positions), bool(indices))
        add('Fermer l’onglet', 'tab-close', lambda: self.window.close_tab(index))
        return menu

    def contextMenuEvent(self, event):
        index = self.tabAt(event.pos())
        if index >= 0:
            menu = self.create_context_menu(index)
            menu.exec(event.globalPos())
            menu.deleteLater()
        else:
            super().contextMenuEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        index = self.tabAt(event.position().toPoint())
        if index != self._hover_index:
            self._hover_timer.stop()
            self._hover_index = index
            if index >= 0:
                self._hover_timer.start()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._hover_timer.stop()
        self._hover_index = -1
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._hover_timer.stop()
        index = self.tabAt(event.position().toPoint())
        if index >= 0 and event.mimeData().hasUrls():
            tab = self.window._tabs[index]
            destination = (self.window.folder if tab.bound is self.window.bound_pane else tab.bound.folder) or tab.location
            # The normal KIO drop path retains modifier keys and the Plasma
            # copy/move/link menu; a tab does not invent a separate transfer.
            self.window.pane_drop_to_location(event, destination)
        else:
            event.ignore()
