"""Context-only command visibility and the native KDE services settings page."""
import ctypes
import json
import os
from pathlib import Path
import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListView, QListWidget, QListWidgetItem, QLabel, QPushButton, QMessageBox
from .i18n import tr
from .platform_services import services
from .iconography import themed_icon


# Stable identifiers, independent of translated labels or menu positions.
ENTRIES = (
    ('add_to_places', 'Ajouter aux emplacements', 'bookmark-new', True),
    ('sort', 'Trier par', 'view-sort-ascending', True),
    ('view_mode', 'Modifier le mode d’affichage', 'view-list-icons', True),
    ('hidden', 'Afficher les éléments cachés', 'view-hidden', True),
    ('open_in_new_tab', 'Ouvrir dans un nouvel onglet', 'tab-new', True),
    ('open_in_new_window', 'Ouvrir dans une nouvelle fenêtre', 'window-new', True),
    ('open_in_split_view', 'Ouvrir en vue scindée', 'view-split-left-right', True),
    ('copy_location', 'Copier le chemin', 'edit-copy-path', True),
    ('duplicate', 'Dupliquer', 'edit-copy', True),
    ('open_terminal_here', 'Ouvrir un terminal ici', 'utilities-terminal', True),
    ('run_in_konsole', 'Lancer dans Konsole', 'utilities-terminal', True),
    ('create_archive', 'Créer une archive…', 'package-x-generic', True),
    ('move_to_new_folder', 'Déplacer vers un nouveau dossier…', 'folder-new', True),
    ('copy_to_inactive', 'Copier vers l’autre panneau', 'edit-copy', True),
    ('move_to_inactive', 'Déplacer vers l’autre panneau', 'edit-move', True),
    ('_delete', 'Supprimer définitivement', 'edit-delete', False),
    ('organize', 'Organiser', 'document-edit', True),
    ('media', 'Outils multimédias', 'applications-multimedia', True),
    ('companions', 'Fichiers associés', 'document-multiple', True),
)
DEFAULTS = {identifier: default for identifier, _label, _icon, default in ENTRIES}


def setting_key(identifier):
    return 'delete/show-permanent' if identifier == '_delete' else 'context-menu/' + identifier


def service_catalog():
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if path:
        try:
            library = ctypes.CDLL(path)
            library.mirivue_context_service_catalog.argtypes = []
            library.mirivue_context_service_catalog.restype = ctypes.c_char_p
            return json.loads(library.mirivue_context_service_catalog())
        except (OSError, AttributeError, ValueError):
            pass
    return []


def entry_enabled(settings, identifier):
    provider = {'run_in_konsole': 'runInKonsole', 'create_archive': 'compressfileitemaction'}.get(identifier)
    if provider and any(row['id'] == provider for row in service_catalog()):
        return service_enabled(provider)
    standard = DEFAULTS.get(identifier, True)
    if identifier == 'move_to_new_folder' and not settings.contains(setting_key(identifier)):
        standard = service_enabled('movetonewfolderitemaction')
    return settings.value(setting_key(identifier), standard, type=bool)


def mark_entry(action, identifier):
    action.setProperty('_mirivue_context_id', identifier)
    return action


def service_enabled(identifier, default=True):
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if path:
        try:
            library = ctypes.CDLL(path)
            library.mirivue_context_service_enabled.argtypes = [ctypes.c_char_p, ctypes.c_int]
            library.mirivue_context_service_enabled.restype = ctypes.c_int
            return bool(library.mirivue_context_service_enabled(identifier.encode('utf-8'), int(default)))
        except (OSError, AttributeError):
            pass
    return default


def filter_menu(window, menu):
    """Remove only this popup's references, never hide shared QAction objects."""
    for action in list(menu.actions()):
        identifier = action.property('_mirivue_context_id')
        if identifier and not entry_enabled(window.settings, identifier):
            menu.removeAction(action)
            continue
        child = action.menu()
        # Main-menu submenus (e.g. Sort) are shared. Leave their contents alone.
        if child is not None and child.parent() is menu:
            filter_menu(window, child)
            if not any(not candidate.isSeparator() for candidate in child.actions()):
                menu.removeAction(action)
    previous_separator = True
    for action in list(menu.actions()):
        if action.isSeparator() and previous_separator:
            menu.removeAction(action)
        else:
            previous_separator = action.isSeparator()
    if menu.actions() and menu.actions()[-1].isSeparator():
        menu.removeAction(menu.actions()[-1])
    return menu


class ContextMenuMixin:
    def context_entry_enabled(self, identifier):
        return entry_enabled(self.settings, identifier)

    def filter_context_menu(self, menu):
        return filter_menu(self, menu)

    def merge_kde_context_menu(self, menu, kde_menu):
        if kde_menu is None:
            return
        # Properties is an independent anchor when Organiser is hidden.
        before = next((a for a in menu.actions() if a.property('_mirivue_extra_actions')), None)
        if before is None:
            before = next((a for a in menu.actions() if a.property('_mirivue_context_properties')), None)
        native_ids = set()
        def collect(current):
            for action in current.actions():
                identifier = action.property('_mirivue_kde_id')
                if identifier:
                    native_ids.add(identifier)
                if action.menu() is not None:
                    collect(action.menu())
        collect(kde_menu)
        replacements = {'runInKonsole': 'run_in_konsole', 'compressfileitemaction': 'create_archive'}
        def remove_duplicates(current):
            for action in list(current.actions()):
                own_id = action.property('_mirivue_context_id')
                if any(provider in native_ids and own_id == own for provider, own in replacements.items()):
                    current.removeAction(action)
                elif action.property('_mirivue_archive_extract') and 'extractfileitemaction' in native_ids:
                    current.removeAction(action)
                elif action.menu() is not None and action.menu().parent() is current:
                    remove_duplicates(action.menu())
        remove_duplicates(menu)
        service_actions = list(kde_menu.actions())
        while service_actions and service_actions[0].isSeparator():
            service_actions.pop(0)
        while service_actions and service_actions[-1].isSeparator():
            service_actions.pop()
        for action in service_actions:
            menu.insertAction(before, action)
        if service_actions and before is not None:
            menu.insertSeparator(before)
        self.filter_context_menu(menu)

    def add_context_folder_actions(self, menu, rows):
        if not rows or not all(row.is_dir for row in rows):
            return
        paths = [str(row.path) for row in rows]
        label = tr('Ouvrir dans un nouvel onglet') if len(paths) == 1 else tr('Ouvrir dans de nouveaux onglets')
        def tabs():
            for location in paths:
                self.open_new_tab(location)
        action = menu.addAction(label, tabs)
        action.setIcon(themed_icon('tab-new'))
        mark_entry(action, 'open_in_new_tab')
        if len(paths) == 1:
            for identifier, label, icon, callback in (
                ('open_in_new_window', 'Ouvrir dans une nouvelle fenêtre', 'window-new', self.open_place_in_new_window),
                ('open_in_split_view', 'Ouvrir en vue scindée', 'view-split-left-right', self.open_place_in_split_view),
            ):
                action = menu.addAction(tr(label), lambda checked=False, target=paths[0], call=callback: call(target))
                action.setIcon(themed_icon(icon))
                mark_entry(action, identifier)


class ContextMenuPage(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.native = False
        self.setObjectName('contextMenuPage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        entries = [dict(id=identifier, text=tr(label), icon=icon, default=default,
                        checked=entry_enabled(window.settings, identifier))
                   for identifier, label, icon, default in ENTRIES]
        path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
        if path:
            try:
                self.library = ctypes.CDLL(path)
                self.callback_type = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
                self.library.mirivue_context_settings_create.argtypes = [ctypes.c_void_p, ctypes.c_char_p, self.callback_type]
                self.library.mirivue_context_settings_create.restype = ctypes.c_void_p
                self.library.mirivue_context_settings_result.argtypes = [ctypes.c_void_p, ctypes.c_int]
                self.library.mirivue_context_settings_result.restype = ctypes.c_char_p
                self.callback = self.callback_type(lambda event: QTimer.singleShot(0, window.show_shortcut_configuration)
                                                    if event == b'shortcuts' else None)
                payload = dict(entries=entries, knsrc=str(Path(__file__).with_name('servicemenu.knsrc')), labels={
                    'search': tr('Rechercher…'), 'download': tr('Télécharger des services…'),
                    'shortcuts': tr('Raccourcis…'), 'defaults': tr('Réglages par défaut'),
                    'builtin': tr('Commande intégrée à Mirivue'),
                    'notice': tr('Ces choix modifient le menu du clic droit. Les services KDE sont partagés avec Dolphin ; les commandes intégrées sont propres à Mirivue.'),
                    'installerMissing': tr('Le téléchargement nécessite le composant servicemenuinstaller fourni avec Dolphin.'),
                })
                pointer = self.library.mirivue_context_settings_create(shiboken6.getCppPointer(self)[0],
                            json.dumps(payload, ensure_ascii=False).encode('utf-8'), self.callback)
                if pointer:
                    self.pointer = pointer
                    self.widget = shiboken6.wrapInstance(pointer, QWidget)
                    layout.addWidget(self.widget)
                    self.native = True
                    return
            except (OSError, AttributeError):
                pass
        # Source-only fallback: builtins work without pretending to configure KDE.
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Rechercher…'))
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        self.entries = QListWidget()
        layout.addWidget(self.entries)
        for entry in sorted(entries, key=lambda item: item['text'].casefold()):
            item = QListWidgetItem(themed_icon(entry['icon']), entry['text'])
            item.setData(Qt.ItemDataRole.UserRole, entry['id'])
            item.setCheckState(Qt.CheckState.Checked if entry['checked'] else Qt.CheckState.Unchecked)
            self.entries.addItem(item)
        self.search.textChanged.connect(self.filter_fallback)
        notice = QLabel(tr('Les services KDE seront disponibles avec les composants natifs de Mirivue compilés.'))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        defaults = QPushButton(tr('Réglages par défaut'))
        defaults.clicked.connect(self.restore_fallback_defaults)
        layout.addWidget(defaults)

    def filter_fallback(self, text):
        for row in range(self.entries.count()):
            item = self.entries.item(row)
            item.setHidden(text.casefold() not in item.text().casefold())

    def restore_fallback_defaults(self):
        for row in range(self.entries.count()):
            item = self.entries.item(row)
            checked = DEFAULTS[item.data(Qt.ItemDataRole.UserRole)]
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def apply(self):
        if self.native:
            result = json.loads(self.library.mirivue_context_settings_result(self.pointer, 1))
            if not result['ok']:
                QMessageBox.warning(self, tr('Réglages non enregistrés'), tr('Impossible d’enregistrer les services KDE. Vérifiez les droits du dossier de configuration.'))
                return False
            values = result['builtins']
        else:
            values = {self.entries.item(row).data(Qt.ItemDataRole.UserRole):
                      self.entries.item(row).checkState() == Qt.CheckState.Checked for row in range(self.entries.count())}
        for identifier, checked in values.items():
            if identifier in DEFAULTS:
                self.window.settings.setValue(setting_key(identifier), checked)
        self.window.settings.sync()
        return True

    def searchable_labels(self):
        if self.native:
            return json.loads(self.library.mirivue_context_settings_result(self.pointer, 0))['labels']
        return [self.entries.item(row).text() for row in range(self.entries.count())]
