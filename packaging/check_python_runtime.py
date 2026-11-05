"""Exercise the Python runtime without claiming a full native KDE validation."""

import compileall
import importlib
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    'atomic_io', 'archive_security', 'batch_rename_existing_names',
    'execution', 'paste_behavior', 'runtime_tasks', 'safe_metadata_backup',
    'recursive_search', 'window_geometry', 'diagnostics',
    'stability_regressions', 'stability_check', 'release_contract', 'beta3_release',
    'kio_request_cancellation', 'cancelled_kio_conflict', 'kio_engine_contract',
)


def main():
    if sys.version_info < (3, 11):
        raise SystemExit('Python 3.11 ou supérieur est nécessaire.')
    sys.path.insert(0, str(ROOT))
    print('Python :', sys.version, flush=True)
    for name in (
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'PySide6.QtDBus', 'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets', 'PySide6.QtPdf', 'shiboken6',
        'PIL.Image', 'mutagen', 'mirivue.app',
    ):
        importlib.import_module(name)
    if not compileall.compile_dir(ROOT / 'mirivue', quiet=1):
        raise SystemExit('Échec de compilation des modules Python.')
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in TESTS:
        tests = loader.discover(str(ROOT / 'tests'), pattern=f'test_{name}.py')
        if not tests.countTestCases():
            raise SystemExit(f'Aucun test découvert : {name}')
        suite.addTests(tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('Contrôles Python réussis ; le lancement natif KDE est testé séparément.')


if __name__ == '__main__':
    main()
