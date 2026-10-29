from .i18n import tr, trf
tr('Desktop-facing preferences, toolbar layout, and trash through system tools.')
from pathlib import Path
from xml.etree.ElementTree import ParseError
import os, shutil
from PySide6.QtCore import Qt, QSettings, QFileSystemWatcher, QTimer, QProcess
from PySide6.QtGui import QIcon, QDesktopServices, QFont
from .platform_services import services
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QAbstractItemView, QPushButton, QToolButton, QStyle, QDialogButtonBox, QMessageBox, QMenu, QHeaderView, QSizePolicy
TOOLBAR = [(tr('menu_button'), tr('Menu')), (tr('home'), tr('Dossier personnel')), (tr('up'), tr('Dossier parent')), (tr('back'), tr('Précédent')), (tr('forward'), tr('Suivant')), (tr('refresh_button'), tr('Actualiser')), (tr('details_button'), tr('Vue détaillée')), (tr('icons_button'), tr('Vue en icônes')), (tr('compact_button'), tr('Vue compacte')), (tr('view_mode_button'), tr('Mode d’affichage')), (tr('split_button'), tr('Vue scindée')), (tr('hidden'), tr('Éléments cachés')), (tr('preview_button'), tr('Miniatures')), (tr('preview_panel_button'), tr('Panneau d’aperçu')), (tr('search_button'), tr('Recherche'))]
LEFT_TOOLBAR = {tr('menu_button'), tr('home'), tr('up'), tr('back'), tr('forward'), tr('refresh_button')}
PATH_BARS_MARKER = '__mirivue_path_bars__'

DEFAULT_TOOLBAR_ORDER = (
    'back', 'forward', 'up', 'home', 'refresh_button', 'details_button',
    'icons_button', 'compact_button', 'view_mode_button', 'split_button',
    'hidden', 'preview_button', 'preview_panel_button', 'search_button', 'menu_button',
)
DEFAULT_TOOLBAR_HIDDEN = ('home', 'details_button', 'icons_button', 'compact_button', 'hidden', 'preview_button')
DEFAULT_TOOLBAR_BEFORE_PATHS = ('back', 'forward', 'up', 'home', 'refresh_button')

class DesktopMixin:

    @staticmethod
    def trash_directory():
        data_home = Path(os.environ.get(tr('XDG_DATA_HOME'), str(Path.home() / tr('.local/share'))))
        return data_home / tr('Trash') / tr('files')

    def trash_is_empty(self):
        folder = self.trash_directory()
        try:
            return not any(folder.iterdir())
        except OSError:
            return True

    def init_desktop(self, navigation, settings_menu):
        self.navigation_layout = navigation
        config = Path(os.environ.get(tr('XDG_CONFIG_HOME'), str(Path.home() / tr('.config'))))
        self.kde_config = config / tr('kdeglobals') if services.capabilities.kde_theme else None
        self.apply_chrome_background()
        self.apply_toolbar()
        self._desktop_refresh = False
        self.desktop_timer = QTimer(self)
        self.desktop_timer.setSingleShot(True)
        self.desktop_timer.setInterval(150)
        self.desktop_timer.timeout.connect(self.follow_desktop)
        self.desktop_watcher = QFileSystemWatcher(self)
        if self.kde_config and config.is_dir():
            self.desktop_watcher.addPath(str(config))
        if self.kde_config and self.kde_config.exists():
            self.desktop_watcher.addPath(str(self.kde_config))
        self.desktop_watcher.fileChanged.connect(lambda *_: self.desktop_timer.start())
        self.desktop_watcher.directoryChanged.connect(lambda *_: self.desktop_timer.start())
        self._desktop_signature = None
        self.follow_desktop()

    def apply_chrome_background(self):
        # Native KDE applications inherit these surfaces from the current Qt
        # style. Do not install even an empty widget stylesheet on the window
        # or toolbar: KUrlNavigator must be painted by the active QStyle.
        # Let Qt/Plasma paint column surfaces and interaction states from its
        # active style instead of overriding the header palette with titlebar RGB.
        for header in self.findChildren(QHeaderView):
            if header.orientation() != Qt.Orientation.Horizontal:
                continue
            header.setObjectName('mirivueColumnHeader')
            header.setStyleSheet('')
        # Command and path containers likewise inherit the toolbar surface.

    def toolbar_state(self):
        from . import library
        ids = [name for name, _ in TOOLBAR]
        saved = library.read(self.settings, tr('toolbar'), {})
        if not isinstance(saved, dict):
            saved = {}
        customized = bool(saved)
        default_order = list(DEFAULT_TOOLBAR_ORDER)
        order = saved.get(tr('order'), default_order)
        if not isinstance(order, list):
            order = list(ids)
        order = list(dict.fromkeys((n for n in order if n in ids)))
        for position, name in enumerate(ids):
            if name in order:
                continue
            previous = next((candidate for candidate in reversed(ids[:position]) if candidate in order), None)
            order.insert(order.index(previous) + 1 if previous else 0, name)
        hidden = saved.get(tr('hidden'), [] if customized else list(DEFAULT_TOOLBAR_HIDDEN))
        if customized and 'view_mode_button' not in saved.get('order', []):
            hidden = [*hidden, 'view_mode_button']
        before_paths = saved.get(tr('before_paths'))
        if not customized:
            before_paths = list(DEFAULT_TOOLBAR_BEFORE_PATHS)
        if isinstance(before_paths, list):
            before_paths = {name for name in before_paths if name in ids}
        else:
            # Keep the familiar navigation placement for existing settings.
            before_paths = set(LEFT_TOOLBAR)
        saved_order = saved.get(tr('order'), [])
        if isinstance(saved_order, list):
            # New commands keep their historic default until explicitly moved.
            before_paths.update(name for name in ids if customized and name not in saved_order and name in LEFT_TOOLBAR)
        return (order, hidden if isinstance(hidden, list) else [], before_paths)

    def apply_toolbar(self):
        order, hidden, before_paths = self.toolbar_state()
        self._toolbar_hidden_names = set(hidden)
        layout = self.navigation_layout
        # The path is now inside each pane.  These legacy widgets may still
        # exist in older saved layouts but must never return to the toolbar.
        self.address_stack.hide()
        self.address_toggle.hide()
        while layout.count():
            layout.takeAt(0)
        while self.left_toolbar_layout.count():
            self.left_toolbar_layout.takeAt(0)
        while self.right_toolbar_layout.count():
            self.right_toolbar_layout.takeAt(0)
        from . import library
        from .toolbar_xml import decode, render, encode_legacy
        saved = library.read(self.settings, 'toolbar', {})
        document = saved.get('xml') if isinstance(saved, dict) else None
        if document:
            try:
                bars, properties = decode(document, dict(TOOLBAR))
            except (ValueError, ParseError):
                bars, properties = decode(encode_legacy(order, hidden, before_paths, dict(TOOLBAR)), dict(TOOLBAR))
            render(self, bars, properties)
        else:
            # A profile not yet edited through KDE retains its exact legacy layout.
            for item in getattr(self, '_toolbar_xml_widgets', []):
                item.hide(); item.deleteLater()
            self._toolbar_xml_widgets = []
            for name in order:
                widget = getattr(self, name)
                widget.setVisible(name not in hidden)
                (self.left_toolbar_layout if name in before_paths else self.right_toolbar_layout).addWidget(widget)
        # The Places sidebar may be wider than the navigation controls.  Let
        # the remaining width be empty so the buttons stay grouped at left.
        self.left_toolbar_layout.addStretch(1)
        if not hasattr(self, 'toolbar_path_action'):
            self.toolbar_left_action = self.navigation_bar.addWidget(self.left_toolbar_group)
            self.toolbar_path_action = self.navigation_bar.addWidget(self.pane_path_container)
            self.toolbar_right_action = self.navigation_bar.addWidget(self.right_toolbar_group)
        if hasattr(self, tr('toolbar_overflow')):
            self.right_toolbar_layout.addWidget(self.toolbar_overflow)
        self.menu_visibility.apply()
        if hasattr(self, tr('update_toolbar_responsiveness')):
            self.update_toolbar_responsiveness()
        QTimer.singleShot(0, self.sync_path_toolbar_alignment)

    def customize_toolbar(self):
        from .toolbar_xml import edit
        return edit(self)

    def propagate_desktop_palette(self):
        # An explicit palette on every child freezes the native Active and
        # Inactive groups, including the menu and the KF6 toolbar.  Allow Qt's
        # platform theme and the current style to propagate their own palette.
        if hasattr(self, tr('panes')):
            self.update_pane_emphasis()

    def follow_desktop(self, force=False):
        if self._desktop_refresh:
            return
        if not services.capabilities.kde_theme:
            return
        try:
            signature = (self.kde_config.stat().st_mtime_ns, self.kde_config.stat().st_size)
        except OSError:
            signature = None
        if not force and signature == self._desktop_signature:
            return
        self._desktop_signature = signature
        if self.kde_config.exists() and str(self.kde_config) not in self.desktop_watcher.files():
            self.desktop_watcher.addPath(str(self.kde_config))
        self._desktop_refresh = True
        try:
            # KDE's platform theme and Breeze already follow kdeglobals.
            # Parsing its RGB values ourselves discards Header and inactive
            # colour roles, which are visible around Dolphin's toolbar.
            services.invalidate_theme_colors()
            self.propagate_desktop_palette()
            self.apply_chrome_background()
            self.refresh_symbolic_icons()
            self.reload_places()
            self.repaint_panes()
            self.update_pane_titles()
        finally:
            self._desktop_refresh = False

    def empty_trash(self):
        if not services.capabilities.empty_trash:
            QMessageBox.information(self, tr('Corbeille'), tr('Le vidage de la corbeille sera proposé par le système sur cette plateforme.'))
            return
        if getattr(self, tr('trash_process'), None) and self.trash_process.state() != QProcess.ProcessState.NotRunning:
            return
        program = services.tool_path('mirivue-kio-empty-trash')
        if not program:
            QMessageBox.warning(self, tr('Corbeille'), tr('Assistant KIO indisponible.'))
            return
        arguments = []
        if QMessageBox.warning(self, tr('Vider la corbeille'), tr('Supprimer définitivement tout le contenu de la corbeille de votre compte, y compris les éléments supprimés avec d’autres applications ?\nCette opération ne peut pas être annulée.'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        process = QProcess(self)
        self.trash_process = process
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        def done(code, status):
            if code == 0:
                self.show_activity_message(tr('Corbeille vidée.'), 7000)
                self.reload_places()
                self.refresh_trash_panes()
            else:
                QMessageBox.warning(self, tr('Corbeille non vidée'), bytes(process.readAll()).decode(tr('utf-8'), tr('replace')) or tr('Le service système de corbeille est indisponible.'))
        process.finished.connect(done)
        process.errorOccurred.connect(lambda *_: QMessageBox.warning(self, tr('Corbeille'), process.errorString()))
        process.start(program, arguments)
