# SPDX-FileCopyrightText: 2006 Peter Penz <peter.penz19@gmail.com>
# SPDX-FileCopyrightText: 2006 Stefan Monov <logixoul@gmail.com>
# SPDX-FileCopyrightText: 2006 Cvetoslav Ludmiloff <ludmiloff@gmail.com>
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: GPL-2.0-or-later
# Menu grouping adapts Dolphin v26.08.2 src/dolphinmainwindow.cpp:
# DolphinMainWindow::updateHamburgerMenu (lines 1540-1626).
# Original pre-existing Mirivue portions retain their earlier MIT grant.
import ctypes
from PySide6.QtWidgets import QWidgetAction
import shiboken6
from .i18n import tr
tr('Persistent menubar choice and temporary keyboard access.')
from PySide6.QtCore import QObject, QEvent, Qt, QTimer, QPoint
from PySide6.QtGui import QAction, QKeySequence
from .platform_services import services
from PySide6.QtWidgets import QApplication, QMenu, QToolButton, QWidget, QStyle
from shiboken6 import isValid
from .iconography import themed_icon

class MenuVisibility(QObject):

    def __init__(self, window, toolbar, layout, view_menu):
        super().__init__(window)
        self.window = window
        self.temporary = False
        self.alt_pending = False
        self.bar = window.menuBar()
        self.action = QAction(tr('Afficher la barre de menus'), window)
        self.action.setCheckable(True)
        # Dolphin starts with its menubar hidden; honor any existing Mirivue
        # preference for people who have chosen to keep it visible.
        self.action.setChecked(window.settings.value('view/menubar', False, type=bool))
        self.action.setShortcut(QKeySequence(services.shortcut(tr('Ctrl+M'))))
        window.addAction(self.action)
        view_menu.addSeparator()
        view_menu.addAction(self.action)
        self.content = QMenu(window)
        self.native = False
        try:
            from .native_desktop_dialogs import load
            self.library = load()
            self.callback_type = ctypes.CFUNCTYPE(None)
            self.callback = self.callback_type(self.prepare_native_menu)
            create = self.library.mirivue_hamburger_create
            create.argtypes = [ctypes.c_void_p]*4 + [self.callback_type]
            create.restype = ctypes.c_void_p
            pointer = create(shiboken6.getCppPointer(window)[0], shiboken6.getCppPointer(self.bar)[0],
                             shiboken6.getCppPointer(self.action)[0], shiboken6.getCppPointer(self.content)[0], self.callback)
            if not pointer:
                raise RuntimeError('KHamburgerMenu indisponible')
            self.open_action = shiboken6.wrapInstance(pointer, QWidgetAction)
            self.open_action.setText(tr('Ouvrir les menus'))
            self.open_action.setIcon(themed_icon('application-menu', window, QStyle.StandardPixmap.SP_TitleBarMenuButton))
            self.button = self.open_action.requestWidget(toolbar)
            self.native = True
        except (OSError, AttributeError, RuntimeError):
            # Source-only fallback; installed KDE validation requires the native action.
            self.button = QToolButton()
            self.button.setIcon(themed_icon('application-menu', window, QStyle.StandardPixmap.SP_TitleBarMenuButton))
            self._fallback_popup = QMenu(window)
            for action in self.bar.actions():
                self.popup.addAction(action)
            self.popup.addSeparator()
            self.popup.addAction(self.action)
            self.button.clicked.connect(self.open_popup)
            self.open_action = QAction(tr('Ouvrir les menus'), window)
            self.open_action.triggered.connect(self.open_popup)
        self.button.setAccessibleName(tr('Ouvrir les menus'))
        self.open_action.setShortcut(QKeySequence(tr('F10')))
        window.addAction(self.open_action)
        self.open_action.changed.connect(self.update_shortcut_hints)
        self.action.changed.connect(self.update_shortcut_hints)
        self.update_shortcut_hints()
        layout.addWidget(self.button)
        window.menu_button = self.button
        for surface in (toolbar, self.bar):
            surface.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            surface.customContextMenuRequested.connect(lambda point, s=surface: self.context_menu(s, point))
        self.action.toggled.connect(self.set_persistent)
        for action in self.bar.actions():
            if action.menu():
                action.menu().aboutToHide.connect(self.schedule_finish)
        self.apply()
        from .native_events import install_event_gate
        self._event_gate = install_event_gate(QApplication.instance(), self, (
            QEvent.Type.WindowDeactivate, QEvent.Type.KeyPress,
            QEvent.Type.ShortcutOverride, QEvent.Type.KeyRelease,
            QEvent.Type.MouseButtonPress,
        ))
        QApplication.instance().aboutToQuit.connect(self.detach)

    def update_shortcut_hints(self):
        def label(action):
            keys = [key.toString(QKeySequence.SequenceFormat.NativeText) for key in action.shortcuts() if not key.isEmpty()]
            return action.text() + (' (' + ', '.join(keys) + ')' if keys else '')
        self.button.setToolTip(label(self.open_action) + ' — ' + label(self.action))

    @staticmethod
    def clear_menu_references(menu):
        # Borrowed actions remain owned by their original menus/window. PySide's
        # QMenu.clear() can invalidate wrappers created by QMenu.addAction(),
        # even when their C++ actions still belong to another menu.
        for action in list(menu.actions()):
            own_separator = action.isSeparator() and action.parent() is menu
            menu.removeAction(action)
            if own_separator:
                action.deleteLater()

    def prepare_native_menu(self):
        # The callback cannot allow Python exceptions through the C boundary.
        try:
            self.populate_native_menu()
        except Exception:
            self.clear_menu_references(self.content)
            self.content.addActions(self.bar.actions())

    def watch_native(self, widget):
        if not self.native:
            return
        watch = self.library.mirivue_hamburger_watch
        watch.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        watch.restype = None
        watch(shiboken6.getCppPointer(self.open_action)[0], shiboken6.getCppPointer(widget)[0])

    def add_to_context_menu(self, menu):
        if self.native:
            add = self.library.mirivue_hamburger_add_to_menu
            add.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            add.restype = None
            add(shiboken6.getCppPointer(self.open_action)[0], shiboken6.getCppPointer(menu)[0])

    def populate_native_menu(self):
        w = self.window
        self.clear_menu_references(self.content)
        if not hasattr(w, 'main_menus') or not hasattr(w, 'rename_menu'):
            self.content.addActions(self.bar.actions())
            return
        w.update_main_menu_states(refresh_details=False)
        if not hasattr(self, 'basic_menu'):
            self.basic_menu = QMenu(tr('Actions sur les fichiers'), self.window)
            self.configure_menu = QMenu(tr('Configuration'), self.window)
            self.watch_native(self.basic_menu)
            self.watch_native(self.configure_menu)
        self.clear_menu_references(self.basic_menu)
        for action in (w.transfer_actions[tr('Couper')], w.transfer_actions[tr('Copier')],
                       w.transfer_actions[tr('Coller')], w.rename_action, w.delete_button, w.properties_action):
            self.basic_menu.addAction(action)
        for action in (w.dolphin_shortcuts['back'], w.dolphin_shortcuts['forward'], w.new_folder_action):
            self.content.addAction(action)
        self.content.addMenu(self.basic_menu)
        self.content.addActions([w.kio_undo_action, w.kio_redo_action, w.search_action, w.quick_filter_action])
        self.content.addSeparator()
        self.content.addActions([w.new_window_action, w.new_tab_action])
        if w.reopen_tab_action.isEnabled():
            self.content.addMenu(w.recently_closed_tabs_menu)
        self.content.addAction(w.open_terminal_action)
        self.content.addSeparator()
        self.content.addMenu(w.view_mode_menu)
        self.content.addActions([w.hidden_action, w.sort_menu.menuAction(), w.extra_info_menu.menuAction(),
                                 w.panels_menu.menuAction()])
        self.clear_menu_references(self.configure_menu)
        self.configure_menu.addActions([w.configure_shortcuts_action, w.toolbar_action, w.configure_action])
        self.content.addMenu(self.configure_menu)
        # Associate existing actions with visible buttons so KDE can suppress
        # redundant entries without guessing from translated captions.
        mappings = dict(back=w.dolphin_shortcuts['back'], forward=w.dolphin_shortcuts['forward'],
                        up=w.dolphin_shortcuts['parent'], home=w.dolphin_shortcuts['home'],
                        refresh_button=w.refresh, details_button=w.details_view_action,
                        icons_button=w.icons_view_action, compact_button=w.compact_view_action,
                        view_mode_button=w.view_mode_menu.menuAction(), split_button=w.split_action,
                        hidden=w.hidden_action, preview_button=w.preview_action,
                        preview_panel_button=w.preview_panel_action, search_button=w.search_action)
        for name, action in mappings.items():
            widget = getattr(w, name, None)
            if widget is not None:
                if action not in widget.actions():
                    widget.addAction(action)
                self.watch_native(widget)
        for widget in getattr(w, '_toolbar_xml_widgets', []):
            # A mirror points to the same behavior; its action metadata is
            # supplied by the rendering adapter when the widget is created.
            if widget.actions():
                self.watch_native(widget)

    @property
    def popup(self):
        # KDE creates and replaces its filtered menu lazily. Never retain a
        # wrapper for a menu which the native action may already have destroyed.
        return self.button.menu() if self.native else self._fallback_popup

    def open_popup(self):
        popup = self.popup
        if popup is not None and popup.isVisible():
            popup.close()
            return
        if self.native:
            self.open_action.trigger()
            return
        anchor = self.button if self.button.isVisible() else self.window.navigation_bar
        self.popup.popup(anchor.mapToGlobal(QPoint(0, anchor.height())))

    def detach(self):
        QApplication.instance().removeEventFilter(self._event_gate)

    def apply(self):
        self.bar.setVisible(self.action.isChecked() or self.temporary)
        self.button.setVisible(not self.action.isChecked() and (not self.temporary))

    def set_persistent(self, visible):
        self.temporary = False
        self.window.settings.setValue('view/menubar', visible)
        self.apply()

    def context_menu(self, surface, point):
        menu = QMenu(self.window)
        menu.addAction(self.action)
        if hasattr(self.window, 'toolbar_action'):
            menu.addAction(self.window.toolbar_action)
        elif hasattr(self.window, 'customize_toolbar'):
            menu.addAction(tr('Configurer la barre d’outils…'), self.window.customize_toolbar)
        menu.exec(surface.mapToGlobal(point))

    def finish(self):
        if self.temporary and QApplication.activePopupWidget() is None:
            self.temporary = False
            self.apply()

    def schedule_finish(self):
        QTimer.singleShot(0, self, self.finish)

    def belongs(self, widget):
        if not isinstance(widget, QWidget):
            return False
        modal = QApplication.activeModalWidget()
        return (modal is None or modal is self.window) and (widget is self.window or self.window.isAncestorOf(widget))

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind not in (QEvent.Type.WindowDeactivate, QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride, QEvent.Type.KeyRelease, QEvent.Type.MouseButtonPress):
            return False
        if QApplication.closingDown() or not isValid(self.window):
            return False
        if kind == QEvent.Type.WindowDeactivate and watched is self.window:
            self.alt_pending = False
            self.schedule_finish()
        if not self.belongs(watched):
            return False
        if kind in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride):
            key = event.key()
            if key != Qt.Key.Key_Alt:
                self.alt_pending = False
            if kind == QEvent.Type.KeyPress and key == Qt.Key.Key_Alt and (not event.isAutoRepeat()):
                if not self.action.isChecked():
                    self.alt_pending = event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.AltModifier)
                    return True
            if key == Qt.Key.Key_Escape and self.temporary and (kind == QEvent.Type.KeyPress):
                if QApplication.activePopupWidget() is None:
                    self.finish()
                    self.window.active_view().setFocus()
                    return True
                self.schedule_finish()
        elif kind == QEvent.Type.KeyRelease and event.key() == Qt.Key.Key_Alt and (not event.isAutoRepeat()):
            pending = self.alt_pending
            self.alt_pending = False
            if pending and (not self.action.isChecked()):
                if self.temporary:
                    self.finish()
                    self.window.active_view().setFocus()
                else:
                    self.temporary = True
                    self.apply()
                    self.bar.setFocus()
                    actions = self.bar.actions()
                    if actions:
                        self.bar.setActiveAction(actions[0])
                return True
        elif kind == QEvent.Type.MouseButtonPress:
            self.alt_pending = False
            if self.temporary and watched is not self.bar and (not self.bar.isAncestorOf(watched)):
                if not isinstance(watched, QMenu):
                    self.schedule_finish()
        return False
