"""Shared KDE defaults and one window action per command.

Editors keep Qt's ShortcutOverride handling. Registering the actions on the
window makes the file commands independent of hidden menus and toolbars.
"""
import ctypes
import json
import weakref

import shiboken6
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox

_CALLBACK = ctypes.CFUNCTYPE(None)
_DOLPHIN_DEFAULTS = {
    'location': ['Ctrl+L', 'Alt+D'], 'properties': ['Alt+Return', 'Alt+Enter'],
    'filter': ['Ctrl+I', '/'], 'zoom-reset': ['Ctrl+0'],
    'copy-to-inactive': ['Shift+F5'], 'move-to-inactive': ['Shift+F6'],
    'copy-paths': ['Ctrl+Alt+C'], 'focus-other-pane': ['Ctrl+F3'],
    'terminal-selection': ['Shift+Alt+F4'], 'focus-terminal': ['Ctrl+Shift+F4'],
    'new-tab': ['Ctrl+T'], 'reopen-tab': ['Ctrl+Shift+T'],
    'previews': ['F12'], 'duplicate': ['Ctrl+D'],
}


def _native_defaults():
    from .dolphin_view import _load
    library = _load()
    getter = library.mirivue_desktop_shortcuts
    getter.argtypes, getter.restype = [], ctypes.c_char_p
    return json.loads(getter().decode()), library


def _normalize(sequence):
    return QKeySequence(sequence).toString(QKeySequence.SequenceFormat.PortableText)


def _effective(binding, value):
    if isinstance(value, (list, tuple)):
        keys = (_normalize(str(key)) for key in value if key)
        return list(dict.fromkeys(key for key in keys if key))
    value = _normalize(str(value or ''))
    return list(binding['defaults']) if value == binding['default'] else ([value] if value else [])


def apply_bindings(window, values=None):
    native, library = _native_defaults()
    # In file views Shift+Delete means permanent deletion. Qt text widgets
    # still implement Shift+Delete as Cut through their ShortcutOverride.
    native['cut'] = [key for key in native['cut'] if key not in native['delete-permanent']]
    defaults = dict(_DOLPHIN_DEFAULTS, **native)
    defaults['back'] = list(dict.fromkeys(['Backspace'] + native['back']))
    defaults['tab-next'] = list(dict.fromkeys(native['tab-next'] + ['Ctrl+Tab']))
    defaults['tab-previous'] = list(dict.fromkeys(native['tab-previous'] + ['Ctrl+Shift+Tab']))
    for binding in window.shortcut_bindings:
        keys = [_normalize(key) for key in defaults.get(binding['id'], [binding['default']]) if key]
        binding['defaults'] = keys
        binding['default'] = keys[0] if keys else ''
        identifier = binding['id']
        value = (values[identifier] if values is not None and identifier in values
                 else window.settings.value('shortcuts/' + identifier, binding['default']))
        binding['sequences'] = _effective(binding, value)
        binding['sequence'] = binding['sequences'][0] if binding['sequences'] else ''
        sequences = [QKeySequence(key) for key in binding['sequences']]
        for target in binding['targets']:
            if isinstance(target, QAction):
                target.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
                target.setShortcuts(sequences)
                window.addAction(target)
            else:
                target.setKeys(sequences)
        if values is not None and identifier in values:
            if binding['sequences'] == binding['defaults']:
                window.settings.remove('shortcuts/' + identifier)
            else:
                window.settings.setValue('shortcuts/' + identifier,
                                         binding['sequences'] if isinstance(value, (list, tuple)) else binding['sequence'])
    if values is not None:
        window.settings.sync()
    if not hasattr(window, '_desktop_shortcut_callback'):
        owner = weakref.ref(window)
        def changed():
            current = owner()
            if current is not None and shiboken6.isValid(current) and not current.closing:
                QTimer.singleShot(0, current.apply_shortcut_bindings)
        window._desktop_shortcut_callback = _CALLBACK(changed)
        watch = library.mirivue_watch_desktop_shortcuts
        watch.argtypes, watch.restype = [ctypes.c_void_p, _CALLBACK], None
        watch(shiboken6.getCppPointer(window)[0], window._desktop_shortcut_callback)


def conflicts(window, values):
    seen = {}
    for binding in window.shortcut_bindings:
        for key in _effective(binding, values[binding['id']]):
            seen.setdefault(key, set()).add(binding['id'])
    return [key for key, identifiers in seen.items() if len(identifiers) > 1]


def extend_bindings(window, add):
    for identifier, title in (('cut', 'Couper'), ('copy', 'Copier'), ('paste', 'Coller'), ('duplicate', 'Dupliquer')):
        action = window.transfer_actions[title]
        add(identifier, title, action.shortcut().toString(), action)
    for identifier, title, default, action in (
        ('new-tab', 'Nouvel onglet', 'Ctrl+T', window.new_tab_action),
        ('close-tab', 'Fermer l’onglet', 'Ctrl+W', window.close_tab_action),
        ('reopen-tab', 'Rouvrir le dernier onglet fermé', 'Ctrl+Shift+T', window.reopen_tab_action),
        ('tab-next', 'Onglet suivant', 'Ctrl+Tab', window.next_tab_action),
        ('tab-previous', 'Onglet précédent', 'Ctrl+Shift+Tab', window.previous_tab_action),
        ('help', 'Aide', 'F1', window.guide_action),
        ('preferences', 'Configurer Mirivue', 'Ctrl+Shift+,', window.configure_action),
        ('previews', 'Afficher les miniatures', 'F12', window.preview_action),
    ):
        add(identifier, title, default, action)
    for identifier, title, default, callback in (
        ('copy-paths', 'Copier l’emplacement des fichiers', 'Ctrl+Alt+C', window.copy_selected_paths),
        ('focus-other-pane', 'Activer l’autre panneau', 'Ctrl+F3', lambda: focus_other_pane(window)),
        ('terminal-selection', 'Ouvrir un terminal ici', 'Shift+Alt+F4', lambda: terminal_selection(window)),
        ('focus-terminal', 'Passer au terminal ou à la vue', 'Ctrl+Shift+F4', lambda: focus_terminal(window)),
    ):
        action = QAction(title, window)
        action.triggered.connect(callback)
        if identifier == 'terminal-selection':
            action.setToolTip('Ouvre un terminal dans chaque dossier sélectionné, ou dans le dossier contenant les fichiers sélectionnés. Sans sélection, utilise le dossier affiché.')
            from .iconography import set_themed_action_icon
            set_themed_action_icon(action, 'utilities-terminal')
        setattr(window, identifier.replace('-', '_') + '_action', action)
        add(identifier, title, default, action)
    for number in range(10):
        action = QAction('Dernier onglet' if number == 0 else f'Onglet {number}', window)
        action.triggered.connect(lambda checked=False, index=number: activate_tab(window, index))
        add(f'tab-{number}', action.text(), f'Alt+{number}', action)


def activate_tab(window, number):
    index = window.tab_bar.count() - 1 if number == 0 else number - 1
    if 0 <= index < window.tab_bar.count():
        window.tab_bar.setCurrentIndex(index)


def focus_other_pane(window):
    if window.split_enabled:
        window.activate_pane(next(pane for pane in window.panes if pane is not window.bound_pane))


def focus_terminal(window):
    if window.terminal_dock.isVisible() and window.terminal_dock.isAncestorOf(QApplication.focusWidget()):
        window.active_view().setFocus()
    else:
        window.terminal_dock.show()
        if window.native_terminal is not None:
            window.native_terminal.focus()


def terminal_selection(window):
    from .locations import parent_location
    from .platform_services import services
    locations = list(dict.fromkeys(str(row.path) if row.is_dir else parent_location(str(row.path))
                                   for row in (window.row(index) for index in window.selected_indexes()))) or [window.folder]
    if len(locations) > 5 and QMessageBox.question(
            window, 'Ouvrir des terminaux', f'Ouvrir {len(locations)} fenêtres de terminal ?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
        return
    for location in locations:
        if location and not services.start_terminal(location):
            window.show_activity_message('Impossible d’ouvrir le terminal dans ' + str(location), 5000)


def show_shortcuts(window):
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
    from html import escape
    dialog = QDialog(window)
    dialog.setWindowTitle('Raccourcis clavier')
    dialog.resize(720, 600)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    rows = ''.join('<tr><td>' + escape(binding['title']) + '</td><td>' +
                   escape(' ; '.join(binding['sequences']) or 'Désactivé') + '</td></tr>'
                   for binding in window.shortcut_bindings)
    browser.setHtml('<p>Raccourcis actuels, avec vos personnalisations. '
                    'Les champs de saisie conservent leurs commandes d’édition.</p><table>' + rows + '</table>'
                    '<p>Entrée : ouvrir. Échap : annuler la sélection ou l’édition. '
                    'Retour arrière : précédent dans la vue de fichiers. '
                    'Flèches, Début, Fin : navigation ; Maj : étendre la sélection ; '
                    'Ctrl+Espace : basculer la sélection courante. '
                    'Ctrl+molette : taille de l’affichage.</p>')
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
