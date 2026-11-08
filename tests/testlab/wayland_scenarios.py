# SPDX-License-Identifier: MIT
"""End-to-end scenarios for native Wayland (KWin virtual backend).

They use only Wayland-compatible mechanisms: KWin fake input, KWin scripting
for windows and activation, wl-paste for the clipboard and ScreenShot2 for
captures. Unlike Xvfb, KWin manages focus: the scenarios *assert* that focus
returns to the right window by itself instead of forcing it.
"""
import time

from .scenarios import FIRST_USE, MAIN_WINDOW, NEW_FOLDER_DIALOG, NEW_FOLDER_NAME

# Icon view, window at 0,0 1280x800 with KWin server-side decorations: the
# first two items of the disposable folder. Measured on the Fedora 45 image;
# a layout change makes the scenario fail with a screenshot, not pass silently.
FOLDER_ITEM = (313, 117)
FILE_ITEM = (423, 117)


def _start(lab, files=None, folders=('Existant',)):
    folder = lab.fixture_folder('Essai TestLab', files=files or {'note.txt': 'Fichier jetable du TestLab.\n'},
                                folders=list(folders))
    with lab.step('Démarrer l’application installée en Wayland natif, sans Xwayland'):
        application = lab.launch(folder)
        main = lab.wait_window(MAIN_WINDOW, timeout=60)
        plugins = lab.assert_native_wayland(application)
        lab.steps[-1]['details'] = {'greffons_qt': plugins}
    with lab.step('« Premiers pas » reçoit le focus de KWin, puis Entrée la ferme'):
        dialog = lab.wait_window(FIRST_USE, timeout=20)
        lab.wait_focus(dialog)
        lab.screenshot('premiers-pas')
        lab.key('Return')
        lab.wait_no_window(FIRST_USE)
    with lab.step('KWin rend le focus à la fenêtre principale sans intervention'):
        lab.wait_focus(main, timeout=10)
    return application, main, folder


def _focus_files(lab):
    """The documented Ctrl+L / Escape sequence that returns focus to the file view."""
    lab.key('ctrl+l')
    lab.key('Escape')


def essential(lab):
    """Focus, activation, shortcuts, dialog and clipboard on native Wayland."""
    application, main, folder = _start(lab)
    with lab.step('Ctrl+A puis Ctrl+C : le presse-papiers Wayland contient les deux éléments'):
        _focus_files(lab)
        lab.key('ctrl+a')
        lab.key('ctrl+c')
        expected = {(folder / name).as_uri() for name in ('Existant', 'note.txt')}
        lab.wait_until(lambda: set(lab.clipboard().split()) == expected, 10, 'URL des deux éléments (wl-paste)')
        lab.screenshot('fenetre-principale')
    with lab.step('Ctrl+Maj+N ouvre « Nouveau dossier », activé par KWin'):
        lab.key('ctrl+shift+n')
        dialog = lab.wait_window(NEW_FOLDER_DIALOG, timeout=15)
        lab.wait_focus(dialog)
        lab.screenshot('dialogue-nouveau-dossier')
    with lab.step('Saisir le nom, valider : dossier créé et focus rendu à la fenêtre principale'):
        lab.type_text(NEW_FOLDER_NAME)
        lab.key('Return')
        lab.wait_no_window(NEW_FOLDER_DIALOG)
        lab.wait_until(lambda: (folder / NEW_FOLDER_NAME).is_dir(), 20, 'dossier créé sur le disque par KIO')
        lab.wait_focus(main, timeout=10)
    with lab.step('Recherche clavier puis Ctrl+C : seule l’URL du nouveau dossier'):
        _focus_files(lab)
        lab.type_text(NEW_FOLDER_NAME[:9])
        lab.key('ctrl+c')
        expected = (folder / NEW_FOLDER_NAME).as_uri()
        lab.wait_until(lambda: lab.clipboard().split() == [expected], 10, 'URL du nouveau dossier')
        lab.screenshot('apres-creation')
    with lab.step('Ctrl+N : la nouvelle fenêtre demande et obtient l’activation (xdg-activation)'):
        before = {identifier for identifier, _ in lab.visible_windows()}
        lab.key('ctrl+n')
        second = lab.wait_until(
            lambda: next((identifier for identifier, caption in lab.visible_windows()
                          if identifier not in before and caption.endswith('Mirivue')), None),
            20, 'nouvelle fenêtre Mirivue')
        lab.wait_focus(second, timeout=10)
        lab.screenshot('deuxieme-fenetre')
    with lab.step('Le clavier suit l’activation : chaque fenêtre copie sa propre sélection'):
        _focus_files(lab)
        lab.key('ctrl+a')
        lab.key('ctrl+c')
        lab.wait_until(lambda: lab.clipboard().split() not in ([], [expected]), 10,
                       'presse-papiers rempli par la deuxième fenêtre')
        lab.focus(main)
        lab.key('ctrl+c')
        lab.wait_until(lambda: lab.clipboard().split() == [expected], 10,
                       'presse-papiers rempli par la fenêtre principale réactivée')
    with lab.step('Ctrl+Q ferme l’application'):
        lab.key('ctrl+q')
        code = lab.wait_exit(application, 30)
        lab.check(code == 0, f'Code de sortie inattendu : {code}')
    with lab.step('Contrôler les données jetables'):
        names = sorted(path.name for path in folder.iterdir())
        lab.check(names == sorted(['Existant', 'note.txt', NEW_FOLDER_NAME]), f'Contenu inattendu : {names}')
        lab.check(not lab.trash_files.exists() or not any(lab.trash_files.iterdir()),
                  'La corbeille jetable n’est pas vide.')


def drag_and_drop(lab):
    """Drag a file onto a folder with the pointer, then choose « Déplacer ici »."""
    application, main, folder = _start(lab)
    with lab.step('Glisser « note.txt » sur « Existant » avec le pointeur'):
        before = {identifier for identifier, _ in lab.visible_windows()}
        lab.screenshot('avant-glisser')
        lab.pointer_drag(FILE_ITEM, FOLDER_ITEM)
        menu = lab.wait_until(
            lambda: next((window for window in lab.windows()
                          if window['id'] not in before and window['id'] != main), None),
            10, 'menu de dépôt de Mirivue')
        lab.screenshot('menu-depot')
    with lab.step('Choisir « Déplacer ici » dans le menu de dépôt'):
        lab.click((menu['x'] + 50, menu['y'] + 12))
        lab.wait_until(lambda: (folder / 'Existant' / 'note.txt').is_file() and not (folder / 'note.txt').exists(),
                       20, 'note.txt déplacé dans Existant par KIO')
        time.sleep(0.5)
        lab.screenshot('apres-depot')
    with lab.step('Ctrl+Q ferme l’application'):
        lab.focus(main)
        lab.key('ctrl+q')
        code = lab.wait_exit(application, 30)
        lab.check(code == 0, f'Code de sortie inattendu : {code}')
    with lab.step('Contrôler le contenu déplacé'):
        lab.check((folder / 'Existant' / 'note.txt').read_text(encoding='utf-8') == 'Fichier jetable du TestLab.\n',
                  'Le fichier déplacé a été modifié.')
    lab.coverage['glisser_deposer'] = 'couvert (dans la même fenêtre)'


def failure_control(lab):
    """Negative control on Wayland: must fail with capture, window list and reports."""
    _start(lab)
    with lab.step('Attendre une fenêtre qui n’existe pas (échec attendu)'):
        lab.wait_window(r'^Fenêtre inexistante du TestLab$', timeout=3)
