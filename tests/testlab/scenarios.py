# SPDX-License-Identifier: MIT
"""End-to-end scenarios driven through the X server against the real application.

A scenario only uses disposable fixtures created inside the run's root. New
scenarios for future changes follow the same pattern: create the data, act
through the keyboard (or the native interfaces), then check both the visible
windows and the resulting files.
"""
import re

NEW_FOLDER_NAME = 'Dossier TestLab 1'
MAIN_WINDOW = r'Mirivue$'
FIRST_USE = r'^Premiers pas avec Mirivue( — Mirivue)?$'
NEW_FOLDER_DIALOG = r'^Nouveau dossier( — Mirivue)?$'


def focus_file_view(lab, main):
    """Xvfb has no window manager: give X focus back to the main window, then
    use the documented Ctrl+L / Escape sequence that returns focus to the files."""
    lab.focus(main)
    lab.key('ctrl+l')
    lab.key('Escape')


def _start_on_fixture(lab):
    folder = lab.fixture_folder('Essai TestLab', files={'note.txt': 'Fichier jetable du TestLab.\n'},
                                folders=['Existant'])
    with lab.step('Démarrer l’application installée sur un dossier jetable'):
        application = lab.launch(folder)
        main = lab.wait_window(MAIN_WINDOW, timeout=60)
    with lab.step('Fermer « Premiers pas » au clavier (Entrée)'):
        dialog = lab.wait_window(FIRST_USE, timeout=20)
        lab.wait_focus(dialog)
        lab.screenshot('premiers-pas')
        lab.key('Return')
        lab.wait_no_window(FIRST_USE)
    with lab.step('Afficher le dossier jetable et donner le focus à la vue (Ctrl+L, Échap)'):
        lab.wait_until(lambda: re.search(r'Essai TestLab', dict(lab.visible_windows()).get(main, '')),
                       30, 'titre de la fenêtre principale contenant le dossier jetable')
        focus_file_view(lab, main)
        lab.key('ctrl+a')
        lab.key('ctrl+c')
        expected = {(folder / name).as_uri() for name in ('Existant', 'note.txt')}
        lab.wait_until(lambda: set(lab.clipboard().split()) == expected, 10,
                       'Ctrl+A puis Ctrl+C copient exactement les deux éléments jetables')
        lab.screenshot('fenetre-principale')
    return application, main, folder


def new_folder(lab):
    """Create a folder with Ctrl+Shift+N, the dialog and Enter, then quit with Ctrl+Q."""
    application, main, folder = _start_on_fixture(lab)
    with lab.step('Ouvrir « Nouveau dossier » avec Ctrl+Maj+N'):
        lab.key('ctrl+shift+n')
        dialog = lab.wait_window(NEW_FOLDER_DIALOG, timeout=15)
        lab.wait_focus(dialog)
        lab.screenshot('dialogue-nouveau-dossier')
    with lab.step('Saisir le nom et valider avec Entrée'):
        lab.type_text(NEW_FOLDER_NAME)
        lab.key('Return')
        lab.wait_no_window(NEW_FOLDER_DIALOG)
        lab.wait_until(lambda: (folder / NEW_FOLDER_NAME).is_dir(), 20,
                       f'création de « {NEW_FOLDER_NAME} » sur le disque par KIO')
    with lab.step('Retrouver le nouveau dossier dans la vue par la recherche clavier'):
        focus_file_view(lab, main)
        lab.type_text(NEW_FOLDER_NAME[:9])
        lab.key('ctrl+c')
        expected = (folder / NEW_FOLDER_NAME).as_uri()
        lab.wait_until(lambda: lab.clipboard().split() == [expected], 10,
                       f'seule l’URL du nouveau dossier dans le presse-papiers ({expected})')
        lab.screenshot('apres-creation')
    with lab.step('Quitter avec Ctrl+Q'):
        lab.focus(main)
        lab.key('ctrl+q')
        code = lab.wait_exit(application, 30)
        lab.check(code == 0, f'Code de sortie inattendu : {code}')
    with lab.step('Contrôler les données jetables et l’isolation'):
        names = sorted(path.name for path in folder.iterdir())
        lab.check(names == sorted(['Existant', 'note.txt', NEW_FOLDER_NAME]), f'Contenu inattendu : {names}')
        lab.check((folder / 'note.txt').read_text(encoding='utf-8') == 'Fichier jetable du TestLab.\n',
                  'Le fichier témoin a été modifié.')
        lab.check((lab.xdg_config / 'pdenams' / 'Mirivue.conf').is_file(),
                  'Les préférences n’ont pas été écrites dans le XDG_CONFIG_HOME jetable.')
        lab.check(not lab.trash_files.exists() or not any(lab.trash_files.iterdir()),
                  'La corbeille jetable n’est pas vide.')


def failure_control(lab):
    """Negative control: expects a window that never exists, so it must fail."""
    _start_on_fixture(lab)
    with lab.step('Attendre une fenêtre qui n’existe pas (échec attendu)'):
        lab.wait_window(r'^Fenêtre inexistante du TestLab$', timeout=3)


# name -> (function, description, engine). The Wayland scenarios live in
# wayland_scenarios.py and run in WaylandLab (KWin virtual backend).
SCENARIOS = {
    'nouveau-dossier': (new_folder, 'Création d’un dossier au clavier dans la vraie fenêtre', 'x11'),
    'controle-echec': (failure_control, 'Contrôle négatif : doit échouer avec capture et rapport', 'x11'),
}


def all_scenarios():
    from . import wayland_scenarios
    scenarios = dict(SCENARIOS)
    scenarios.update({
        'wayland-essentiel': (wayland_scenarios.essential,
                              'Focus, activation, raccourcis, dialogue et presse-papiers en Wayland natif', 'wayland'),
        'wayland-glisser-deposer': (wayland_scenarios.drag_and_drop,
                                    'Glisser-déposer au pointeur et menu de dépôt en Wayland natif', 'wayland'),
        'wayland-controle-echec': (wayland_scenarios.failure_control,
                                   'Contrôle négatif Wayland : doit échouer avec capture et rapport', 'wayland'),
    })
    return scenarios
