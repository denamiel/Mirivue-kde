"""Installation contract accepts delayed configure, rejects actual refusal."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestNativeContractTiming(unittest.TestCase):
    def run_contract(self, mode):
        library = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY', '')
        self.assertTrue(Path(library).is_file(), 'Valider must compile the native widget library')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
        done = subprocess.run([sys.executable, str(ROOT / 'tests/helpers/native_contract_peer.py'), mode],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn('Invalid URL: QUrl("")', done.stderr)
        return done.stdout

    def test_delayed_configure_runs_the_entire_native_contract(self):
        self.assertIn('NATIVE_CONTRACT_PASSED', self.run_contract('delayed'))

    def test_a_real_refusal_still_fails_with_geometry_diagnostics(self):
        self.assertIn('PERSISTENT_REFUSAL_DETECTED', self.run_contract('refused'))
