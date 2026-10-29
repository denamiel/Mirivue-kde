#!/usr/bin/env python3
"""Read-only Plasma details-view splitter profile for the installed RC194."""

import cProfile
import argparse
import io
import os
import pstats
import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

if not Path('/usr/lib/mirivue-kde/mirivue').is_dir():
    raise SystemExit('Mirivue KDE doit être installé comme paquet système.')

parser = argparse.ArgumentParser(description='Comparer le glissement des panneaux de Mirivue RC194.')
parser.add_argument('dossier', nargs='?', default=str(Path.home() / 'Téléchargements'))
parser.add_argument('--mes-reglages', action='store_true',
                    help='utiliser une COPIE temporaire des réglages personnels')
arguments = parser.parse_args()
original_config_home = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))

# Keep the user's Mirivue preferences, caches and history out of this run.
temporary = tempfile.TemporaryDirectory(prefix='mirivue-render-diagnostic-')
for directory in ('CONFIG', 'CACHE', 'DATA', 'STATE'):
    target = Path(temporary.name) / directory.lower()
    target.mkdir()
    os.environ[f'XDG_{directory}_HOME'] = str(target)
if arguments.mes_reglages:
    source = original_config_home / 'pdenams' / 'Mirivue.conf'
    if not source.is_file():
        raise SystemExit(f'Réglages personnels introuvables : {source}')
    target = Path(temporary.name) / 'config' / 'pdenams' / 'Mirivue.conf'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
sys.path.insert(0, '/usr/lib/mirivue-kde')

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication
from mirivue import __version__
from mirivue.app import Window, prepare_audio_stream_identity, prepare_system_style
from mirivue.platform_services import services

prepare_audio_stream_identity()
if __version__ != '1.0.0-rc194':
    raise SystemExit(f'RC194 nécessaire ; version installée : {__version__}')
services.initialize_icon_theme()
application = QApplication(['Mirivue', '--render-diagnostic'])
prepare_system_style(application)
window = Window()
folder = Path(arguments.dossier).expanduser()
if not folder.is_dir():
    raise SystemExit(f'Dossier introuvable : {folder}')
window.prepare_startup_browsing(str(folder))
window.set_split_view(True, navigate_new=False)
window.prime_startup_pane(window.panes[1], str(folder))
window.show()
window.sync_path_toolbar_alignment()
QTimer.singleShot(0, window.start_browsing)


def describe(widget):
    style = widget.style()
    return (f'{widget.metaObject().className()} '
            f'geometry={widget.geometry().getRect()} '
            f'style={style.metaObject().className()}:{style.objectName()} '
            f'background={widget.autoFillBackground()} '
            f'stylesheet={widget.styleSheet()!r}')


def start():
    if any(pane.scanning for pane in window.panes):
        if time.perf_counter() - startup_time < 30:
            QTimer.singleShot(250, start)
            return
        print('ATTENTION : le chargement du dossier se poursuit pendant la mesure.', flush=True)
    for pane in window.panes:
        pane.content_stack.setCurrentWidget(pane.table)
    application.processEvents()
    print('Réglages :', 'copie des réglages personnels' if arguments.mes_reglages
          else 'réglages neufs', '; dossier :', folder, flush=True)
    print('Inclure les sous-dossiers :', window.recursive.isChecked(), flush=True)
    print('Taille des dossiers :', window.settings.value('view/folder-size-display', 'count'), flush=True)
    print('Style application :', describe(window), flush=True)
    print('Barre :', describe(window.navigation_bar), flush=True)
    for number, pane in enumerate(window.panes, 1):
        if pane.native_navigator is None:
            print(f'Panneau {number} : aucun KUrlNavigator natif', flush=True)
            continue
        nav = pane.native_navigator.widget
        header = pane.table.horizontalHeader()
        visible_columns = sum(not header.isSectionHidden(column)
                              for column in range(header.count()))
        print(f'Panneau {number} :', describe(nav), flush=True)
        print(f'  vue={pane.content_stack.currentIndex()} lignes={pane.model.rowCount()} '
              f'colonnes visibles={visible_columns} '
              f'aperçus={pane.model.show_thumbnails} '
              f'cadre KDE={pane.native_navigator.has_background()} '
              f'saisie={pane.native_navigator.is_editable()}', flush=True)
        for name, widget in [('application', window), ('navigateur', nav)]:
            palette = widget.palette()
            print(f'  palette {name} : '
                  f'Base={palette.color(QPalette.ColorRole.Base).name()} '
                  f'AlternateBase={palette.color(QPalette.ColorRole.AlternateBase).name()} '
                  f'Window={palette.color(QPalette.ColorRole.Window).name()}', flush=True)
        parent = nav.parentWidget()
        while parent is not None and parent is not window:
            print('  parent :', describe(parent), flush=True)
            parent = parent.parentWidget()
        picture = nav.grab().toImage()
        if not picture.isNull():
            middle = picture.width() // 2
            print('  pixels haut/bord/intérieur :',
                  [(x, y, picture.pixelColor(x, y).name())
                   for x, y in ((middle, 0), (middle, 1), (middle, 3),
                                (1, picture.height() // 2), (3, picture.height() // 2))
                   if x < picture.width() and y < picture.height()], flush=True)
    window.pane_splitter.splitterMoved.connect(on_splitter_moved)
    print('Vue détails uniquement : faites glisser le séparateur. '
          'La mesure de 12 secondes commencera au premier mouvement.', flush=True)


def on_splitter_moved(*_args):
    if not phase['started']:
        if any(pane.content_stack.currentWidget() is not pane.table for pane in window.panes):
            raise RuntimeError('La vue détails demandée n’est pas active.')
        phase['started'] = True
        clock['last'] = time.perf_counter()
        clock_timer.start(16)
        phase['profiler'].enable()
        QTimer.singleShot(12000, finish)
        print('Mesure démarrée : continuez à glisser pendant 12 secondes.', flush=True)
    movements.append(time.perf_counter())


def finish():
    phase['profiler'].disable()
    clock_timer.stop()
    print('===== Vue détails =====', flush=True)
    if not movements:
        print('PHASE NON MESURÉE : aucun mouvement du séparateur détecté.', flush=True)
    if intervals:
        print(f'Horloge Qt : {len(intervals)} cycles, médiane '
              f'{statistics.median(intervals):.1f} ms, maximum {max(intervals):.1f} ms, '
              f'{sum(value > 40 for value in intervals)} cycles > 40 ms ; '
              f'{len(movements)} mouvements du séparateur.', flush=True)
    output = io.StringIO()
    pstats.Stats(phase['profiler'], stream=output).strip_dirs().sort_stats('cumulative').print_stats(35)
    print('Profil des appels Python et Qt pendant le glissement :', flush=True)
    print(output.getvalue(), flush=True)
    output = io.StringIO()
    pstats.Stats(phase['profiler'], stream=output).strip_dirs().sort_stats('tottime').print_stats(20)
    print('Temps propre des fonctions (hors appels enfants) :', flush=True)
    print(output.getvalue(), flush=True)
    window.quit_requested = True
    window.closing = True
    window.close()
    application.quit()


phase = {'started': False, 'profiler': cProfile.Profile()}
intervals = []
movements = []
clock = {'last': 0.0}


def tick():
    now = time.perf_counter()
    intervals.append((now - clock['last']) * 1000)
    clock['last'] = now


clock_timer = QTimer()
clock_timer.setTimerType(Qt.TimerType.PreciseTimer)
clock_timer.timeout.connect(tick)
startup_time = time.perf_counter()
QTimer.singleShot(1000, start)
sys.exit(application.exec())
