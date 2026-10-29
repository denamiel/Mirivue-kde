"""Automated splitter measurement on disposable files and isolated settings.

No input, forced extra repaint or user settings are needed. Results measure
Qt's offscreen renderer, not a guarantee about a desktop compositor's timing.
"""
import argparse
import cProfile
import json
import os
from pathlib import Path
import statistics
import platform
import sys
import tempfile
import time
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--columns', type=int, default=6)
parser.add_argument('--steps', type=int, default=180)
parser.add_argument('--no-cache', action='store_true', help='Control: use identical headers without the drawing cache')
args = parser.parse_args()
sys.path.insert(0, str(args.source_root.resolve()))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
temporary = tempfile.TemporaryDirectory(prefix='mirivue-splitter-bench-')
root = Path(temporary.name)
for name in ('CONFIG', 'CACHE', 'DATA', 'STATE'):
    os.environ[f'XDG_{name}_HOME'] = str(root / name.lower())

from PySide6.QtCore import QSettings, qVersion
from PySide6.QtWidgets import QApplication
from mirivue import __version__
from mirivue.app import Window
from mirivue.metadata import basic_entry, HEADERS
if args.no_cache:
    import mirivue.app as app_module
    app_module.presentation_model = lambda source, parent: source

app = QApplication([])
settings = QSettings(str(root / 'preferences.ini'), QSettings.Format.IniFormat)
settings.setValue('view/previews', True)
settings.setValue('view/folder-size-display', 'count')
with patch('mirivue.app.mirivue_settings', return_value=settings):
    window = Window()
window.resize(1500, 800)
window.set_split_view(True, navigate_new=False)
folder = root / 'files'
folder.mkdir()
paths = []
for n in range(120):
    path = folder / (f'Dossier {n}' if n < 40 else f'Fichier {n}.txt')
    if n < 40:
        path.mkdir()
    else:
        path.write_text('Présentation de fichier pour mesure automatisée.')
    paths.append(path)

for pane in window.panes:
    pane.model.add_preliminary([basic_entry(path) for path in paths])
    pane.content_stack.setCurrentWidget(pane.table)
    header = pane.table.horizontalHeader()
    order = [0, 1, 2, 14, 10, 3] + [c for c in range(len(HEADERS)) if c not in (0, 1, 2, 14, 10, 3)]
    for column in range(len(HEADERS)):
        pane.table.setColumnHidden(column, column not in order[:args.columns])
    pane.column_width_mode = 'auto'
    window.apply_pane_column_width_mode(pane)
window.show()
app.processEvents()


def positions(count):
    # Include both directions, narrow views, and the appearance of a scrollbar.
    for n in range(count):
        phase = (n % 80) / 40
        ratio = phase if phase <= 1 else 2 - phase
        yield round(window.pane_splitter.width() * (0.25 + ratio * 0.5))


for position in positions(80):
    window.pane_splitter.moveSplitter(position, 1)
    app.processEvents()
timings = []
for position in positions(args.steps):
    start = time.perf_counter()
    window.pane_splitter.moveSplitter(position, 1)
    app.processEvents()
    timings.append((time.perf_counter() - start) * 1000)

profile = cProfile.Profile()
profile.enable()
for position in positions(80):
    window.pane_splitter.moveSplitter(position, 1)
    app.processEvents()
profile.disable()
calls = {}
filters = {}
for item in profile.getstats():
    code = item.code
    if not isinstance(code, str) and code.co_name == 'eventFilter' and '/mirivue/' in code.co_filename:
        filters[Path(code.co_filename).name] = filters.get(Path(code.co_filename).name, 0) + item.callcount
    if (not isinstance(code, str) and code.co_filename.endswith('/mirivue/app.py')
            and code.co_name in ('data', 'rowCount', 'columnCount', 'flags', 'headerData')):
        calls[code.co_name] = calls.get(code.co_name, 0) + item.callcount
result = dict(version=__version__, columns=args.columns, rows_per_pane=120,
              python=platform.python_version(), qt=qVersion(), style=app.style().objectName(),
              steps=args.steps, median_ms=round(statistics.median(timings), 3),
              p95_ms=round(sorted(timings)[int(len(timings)*0.95)], 3),
              max_ms=round(max(timings), 3), profiled_steps=80, source_calls=calls, python_event_filters=filters,
              native=window.proxy.sourceModel() is not window.model,
              view_engine=(window.table._backend.query()['engine']
                           if hasattr(window.table, '_backend') else 'QTableView'),
              visible_objects=(window.table._backend.query()['visibleObjects']
                               if hasattr(window.table, '_backend') else None))
window.quit_requested = True
window.closing = True
window.close()
app.processEvents()
print(json.dumps(result, ensure_ascii=False))
