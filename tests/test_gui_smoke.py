import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    subprocess.run(
        [sys.executable, '-c', 'import PySide6'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0,
    'PySide6 absent de cet environnement',
)
class TestGuiSmoke(unittest.TestCase):
    def test_real_main_window_can_be_constructed_offscreen(self):
        environment = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM='offscreen')
        result = subprocess.run(
            [sys.executable, '-m', 'mirivue', '--smoke-test'],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('interface initialisée', result.stdout)

    def test_real_toolbar_views_split_and_search_interactions(self):
        with tempfile.TemporaryDirectory(prefix='mirivue-ui-') as isolated:
            environment = dict(os.environ, PYTHONPATH=str(ROOT), QT_QPA_PLATFORM='offscreen',
                               XDG_CONFIG_HOME=isolated + '/config', XDG_STATE_HOME=isolated + '/state')
            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'mirivue', '--ui-contract'],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired as error:
                output = error.stderr or b''
                if isinstance(output, bytes):
                    output = output.decode('utf-8', 'replace')
                self.fail('Le contrôle graphique est bloqué. Dernières étapes et pile :\n'
                          + output[-8000:])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('interactions de l’interface vérifiées', result.stdout)


if __name__ == '__main__':
    unittest.main()
