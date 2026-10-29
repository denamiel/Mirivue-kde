import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from mirivue import diagnostics


ROOT = Path(__file__).resolve().parents[1]


class TestDiagnostics(unittest.TestCase):
    def tearDown(self):
        diagnostics._session_marker = None

    def test_report_lists_runtime_without_importing_the_gui(self):
        report = diagnostics.diagnostic_report('test-version')
        self.assertIn('Version Mirivue : test-version', report)
        self.assertIn('PySide6.QtMultimediaWidgets', report)
        self.assertIn('FFmpeg'.casefold(), report.casefold())
        self.assertIn('KIO/KF6', report)
        self.assertIn('aucune transmission automatique', report)

    def test_diagnostic_command_precedes_app_import(self):
        source = (ROOT / 'mirivue' / '__main__.py').read_text(encoding='utf-8')
        self.assertLess(source.index("'--diagnostic' in sys.argv"), source.index('from .app import main'))
        self.assertLess(source.index("'--version' in sys.argv"), source.index('from .app import main'))
        launcher = (ROOT / 'Lancer.sh').read_text(encoding='utf-8')
        self.assertIn('"${1:-}" == "--diagnostic"', launcher)

    def test_installer_smoke_test_builds_the_real_window(self):
        source = (ROOT / 'mirivue' / '__main__.py').read_text(encoding='utf-8')
        self.assertIn("'--smoke-test' in sys.argv", source)
        self.assertIn('window = Window()', source)
        self.assertIn('window.centralWidget()', source)

    def test_stale_session_is_detected_and_clean_session_removes_marker(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'XDG_STATE_HOME': folder}):
            state = Path(folder) / 'mirivue'
            state.mkdir()
            marker = state / 'session-2147483647.json'
            marker.write_text(json.dumps({'pid': 2147483647}), encoding='utf-8')
            self.assertTrue(diagnostics.begin_session())
            current_marker = state / f'session-{os.getpid()}.json'
            self.assertFalse(marker.exists())
            self.assertTrue(current_marker.is_file())
            diagnostics.end_session()
            self.assertFalse(current_marker.exists())

    def test_logging_is_bounded_and_never_requires_qt(self):
        with tempfile.TemporaryDirectory() as folder:
            code = (
                'from mirivue.diagnostics import configure_logging, record_tool_failure; '
                'configure_logging("test"); '
                '[record_tool_failure("outil", "x" * 8000) for _ in range(180)]'
            )
            environment = dict(os.environ, XDG_STATE_HOME=folder, PYTHONPATH=str(ROOT))
            result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=environment,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            logs = list((Path(folder) / 'mirivue').glob('mirivue.log*'))
            self.assertGreaterEqual(len(logs), 1)
            self.assertLessEqual(len(logs), diagnostics.LOG_BACKUPS + 1)
            self.assertTrue(all(path.stat().st_size <= diagnostics.MAX_LOG_BYTES for path in logs))

    def test_help_menu_exposes_local_diagnostic(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertIn("self.diagnostics_action = help_menu.addAction(tr('Diagnostic de Mirivue'), self.show_diagnostics)", source)
        self.assertIn("tr('Copier le diagnostic')", source)
        self.assertIn("tr('Ouvrir le dossier des journaux')", source)

    def test_external_backends_record_failures(self):
        for filename in ('persistence.py', 'media_tags.py', 'metadata.py', 'platform_services.py', 'app.py'):
            source = (ROOT / 'mirivue' / filename).read_text(encoding='utf-8')
            self.assertIn('record_tool_failure', source, filename)

    def test_archive_tool_versions_use_their_supported_invocations(self):
        outputs = {
            '7z': '7-Zip 25.01 (x64)',
            'unrar': 'UNRAR 7.11 freeware',
            'unar': 'unar 1.10.8',
        }
        calls = []

        def run(arguments, **_kwargs):
            calls.append(arguments)
            return SimpleNamespace(stdout=outputs[Path(arguments[0]).name], stderr='', returncode=0)

        with patch('mirivue.diagnostics.shutil.which', side_effect=lambda name: '/usr/bin/' + name), \
             patch('mirivue.diagnostics.subprocess.run', side_effect=run):
            self.assertIn('7-Zip', diagnostics._command_version('7z'))
            self.assertIn('UNRAR', diagnostics._command_version('unrar'))
            self.assertIn('unar', diagnostics._command_version('unar'))

        self.assertIn(['/usr/bin/7z'], calls)
        self.assertIn(['/usr/bin/unrar'], calls)
        self.assertIn(['/usr/bin/unar', '-v'], calls)


if __name__ == '__main__':
    unittest.main()
