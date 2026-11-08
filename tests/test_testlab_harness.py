# SPDX-License-Identifier: MIT
"""Mirivue TestLab: the harness must record success, detect failure, stop
every process, delete its disposable root and never write to a personal home.

The display tests need Xvfb, xdotool, xwd, xclip and the installed
mirivue-kde. They are skipped where those are absent, except when
MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1 (CI), where a missing tool is a failure.
"""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zlib

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from testlab import harness, xwd  # noqa: E402
from testlab.harness import Lab  # noqa: E402

FAKE = TESTS / 'helpers' / 'testlab_fake_application.py'
RUNNER = TESTS / 'testlab' / 'run.py'
REQUIRE_DISPLAY = os.environ.get('MIRIVUE_TESTLAB_REQUIRE_DISPLAY') == '1'


def alive(pid):
    try:
        state = Path(f'/proc/{pid}/stat').read_text().split(')')[-1].split()[0]
    except OSError:
        return False
    return state != 'Z'


@unittest.skipUnless(shutil.which('dbus-daemon'), 'dbus-daemon absent')
class FakeApplicationRuns(unittest.TestCase):
    """Harness behaviour with a stand-in application and no display."""

    def setUp(self):
        self.workspace = Path(tempfile.mkdtemp(prefix='testlab-essai-'))
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        # A personal home stand-in with existing content: it must not change.
        self.personal = self.workspace / 'personnel'
        (self.personal / '.config' / 'pdenams').mkdir(parents=True)
        (self.personal / '.config' / 'pdenams' / 'Mirivue.conf').write_text('[x]\na=1\n')
        (self.personal / '.local' / 'share' / 'Trash' / 'files').mkdir(parents=True)
        self.base = self.workspace / 'racines'
        self.artifacts = self.workspace / 'artefacts'
        self.env_report = self.workspace / 'environnement.json'
        patcher = mock.patch.dict(os.environ, {'HOME': str(self.personal)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def lab(self, **options):
        options.setdefault('timeout', 30)
        return Lab('essai', self.artifacts, app=[sys.executable, str(FAKE)], display=False,
                   base=self.base, watch=[self.personal], **options)

    def report(self):
        return json.loads((self.artifacts / 'rapport.json').read_text(encoding='utf-8'))

    def assert_clean(self, lab):
        self.assertFalse(lab.root.exists(), 'le dossier jetable doit être supprimé')
        self.assertEqual(harness.marked_processes(lab.root), [])
        self.assertEqual(list(self.base.iterdir()), [])
        self.assertTrue(self.report()['nettoyage']['reussi'])

    def test_success_is_recorded_and_isolated(self):
        lab = self.lab()

        def scenario(lab):
            with lab.step('application factice'):
                code = lab.wait_exit(lab.launch('succes', self.env_report), 20)
                lab.check(code == 0, f'code {code}')
        self.assertEqual(lab.run(scenario), harness.EXIT_SUCCESS)
        report = self.report()
        self.assertEqual(report['statut'], 'réussi')
        self.assertEqual([step['statut'] for step in report['etapes']], ['réussi'])
        self.assertTrue(report['isolation']['reussi'])
        environment = json.loads(self.env_report.read_text())
        for key in ('HOME', 'TMPDIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME',
                    'XDG_STATE_HOME', 'XDG_RUNTIME_DIR'):
            self.assertTrue(environment[key].startswith(str(lab.root) + '/'), (key, environment[key]))
        self.assertIn(str(lab.root / 'run' / 'bus'), environment['DBUS_SESSION_BUS_ADDRESS'])
        self.assertFalse((self.personal / 'marqueur-testlab').exists())
        self.assertNotIn('<failure', (self.artifacts / 'junit.xml').read_text())
        self.assert_clean(lab)

    def test_failure_returns_non_zero_and_keeps_diagnostics(self):
        lab = self.lab()

        def scenario(lab):
            with lab.step('application factice en échec'):
                code = lab.wait_exit(lab.launch('echec', self.env_report), 20)
                lab.check(code == 0, f'code de sortie {code}')
        self.assertEqual(lab.run(scenario), harness.EXIT_SCENARIO_FAILED)
        report = self.report()
        self.assertEqual(report['statut'], 'échec')
        self.assertIn('code de sortie 3', report['erreur'])
        self.assertEqual(report['etapes'][0]['statut'], 'échec')
        self.assertIn('échec simulé', (self.artifacts / 'journaux' / 'mirivue.log').read_text())
        self.assertIn('ScenarioFailure', (self.artifacts / 'journaux' / 'harness.log').read_text())
        junit = (self.artifacts / 'junit.xml').read_text()
        self.assertIn('failures="1"', junit)
        self.assertIn('<failure message=', junit)
        self.assert_clean(lab)

    def test_hung_application_and_detached_child_are_killed(self):
        lab = self.lab(timeout=6)

        def scenario(lab):
            with lab.step('application bloquée'):
                lab.launch('bloque', self.env_report)
                lab.wait_until(lambda: Path(str(self.env_report) + '.enfant').exists(), 5, 'enfant démarré')
                lab.wait_exit(lab.applications[0][1], 60)
        start = time.monotonic()
        self.assertEqual(lab.run(scenario), harness.EXIT_SCENARIO_FAILED)
        self.assertLess(time.monotonic() - start, 30, 'le délai global doit borner le scénario')
        child = int(Path(str(self.env_report) + '.enfant').read_text())
        self.assertFalse(alive(child), 'un processus détaché ignorant SIGTERM doit être arrêté')
        self.assertIn('ne s’est pas arrêté', self.report()['erreur'])
        self.assert_clean(lab)

    def test_write_outside_the_disposable_root_is_detected(self):
        lab = self.lab()
        target = self.personal / '.config' / 'pdenams' / 'intrus.conf'

        def scenario(lab):
            with lab.step('écriture interdite'):
                lab.wait_exit(lab.launch('ecrit', self.env_report, target), 20)
        self.assertEqual(lab.run(scenario), harness.EXIT_CLEANUP_FAILED)
        report = self.report()
        self.assertFalse(report['isolation']['reussi'])
        self.assertIn(str(target), report['isolation']['modifications'])
        self.assertIn('<failure', (self.artifacts / 'junit.xml').read_text())

    def test_missing_tool_is_reported_as_unavailable(self):
        empty = self.workspace / 'vide'
        empty.mkdir()
        lab = self.lab()
        with mock.patch.dict(os.environ, {'PATH': str(empty)}):
            self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        report = self.report()
        self.assertEqual(report['statut'], 'indisponible')
        self.assertIn('dbus-daemon', report['erreur'])

    def test_disposable_root_inside_a_home_is_refused(self):
        lab = Lab('essai', self.artifacts, app=[sys.executable, str(FAKE)], display=False,
                  base=self.personal / 'tmp', watch=[])
        self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        self.assertIn('dossier personnel', self.report()['erreur'])
        self.assertEqual(list((self.personal / 'tmp').iterdir()), [])


class ReportFormats(unittest.TestCase):
    def test_xwd_to_png_both_byte_orders(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (10, 20, 30)]
        for byte_order, endian in ((0, '<'), (1, '>')):
            with self.subTest(byte_order=byte_order):
                name = b'essai\0'
                header_size = 100 + len(name)
                fields = [header_size, 7, 2, 24, 2, 2, 0, byte_order, 32, byte_order, 32, 32, 8,
                          4, 0xFF0000, 0x00FF00, 0x0000FF, 8, 256, 0, 2, 2, 0, 0, 0]
                body = b''.join((r << 16 | g << 8 | b).to_bytes(4, 'little' if byte_order == 0 else 'big')
                                for r, g, b in pixels)
                data = struct.pack(endian + '25I', *fields) + name + body
                width, height, rows = xwd.decode(data)
                self.assertEqual((width, height), (2, 2))
                self.assertEqual(rows, [bytes([255, 0, 0, 0, 255, 0]), bytes([0, 0, 255, 10, 20, 30])])
                png = xwd.png_bytes(width, height, rows)
                self.assertTrue(png.startswith(b'\x89PNG\r\n\x1a\n'))
                idat = png[png.index(b'IDAT') + 4:png.index(b'IEND') - 8]
                self.assertEqual(zlib.decompress(idat), b'\0' + rows[0] + b'\0' + rows[1])

    def test_xwd_rejects_unknown_data(self):
        with self.assertRaises(xwd.XwdError):
            xwd.decode(b'\0' * 200)

    def test_xauthority_entry_is_wildcard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'auth'
            harness.write_xauthority(path, b'\x01' * 16)
            data = path.read_bytes()
            self.assertEqual(data[:2], b'\xff\xff')
            self.assertIn(b'MIT-MAGIC-COOKIE-1', data)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


def display_requirements():
    missing = harness.missing_tools(display=True)
    if shutil.which('mirivue-kde') is None:
        missing.append('mirivue-kde')
    return missing


class InstalledApplicationOnXvfb(unittest.TestCase):
    """The real window: the negative control must fail with evidence."""

    def setUp(self):
        missing = display_requirements()
        if missing:
            if REQUIRE_DISPLAY:
                self.fail('Outils requis absents : ' + ', '.join(missing))
            self.skipTest('Outils absents : ' + ', '.join(missing))
        self.workspace = Path(tempfile.mkdtemp(prefix='testlab-reel-'))
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def run_scenario(self, name):
        artifacts = self.workspace / name
        environment = dict(os.environ)
        environment.pop('GITHUB_STEP_SUMMARY', None)
        result = subprocess.run([sys.executable, str(RUNNER), name, '--artefacts', str(artifacts),
                                 '--delai', '120'], env=environment, capture_output=True, text=True, timeout=300)
        report = json.loads((artifacts / 'rapport.json').read_text(encoding='utf-8'))
        return result, report, artifacts

    def test_negative_control_fails_with_screenshot_logs_and_cleanup(self):
        result, report, artifacts = self.run_scenario('controle-echec')
        self.assertEqual(result.returncode, harness.EXIT_SCENARIO_FAILED, result.stdout + result.stderr)
        self.assertEqual(report['statut'], 'échec')
        failure = [capture for capture in report['captures'] if capture['nom'] == 'echec']
        self.assertEqual(len(failure), 1, report['captures'])
        png = (artifacts / failure[0]['fichier']).read_bytes()
        self.assertTrue(png.startswith(b'\x89PNG'))
        self.assertGreater(len(png), 5000, 'la capture doit contenir la fenêtre, pas un écran vide')
        self.assertIn('Mirivue', (artifacts / 'fenetres-visibles.txt').read_text(encoding='utf-8'))
        self.assertTrue((artifacts / 'journaux' / 'etat-mirivue-mirivue.log').exists())
        self.assertTrue(report['nettoyage']['reussi'])
        self.assertTrue(report['isolation']['reussi'])

    def test_new_folder_scenario_succeeds(self):
        result, report, artifacts = self.run_scenario('nouveau-dossier')
        self.assertEqual(result.returncode, harness.EXIT_SUCCESS, result.stdout + result.stderr)
        self.assertTrue(all(step['statut'] == 'réussi' for step in report['etapes']))
        self.assertGreaterEqual(len(report['captures']), 4)
        self.assertFalse([c for c in report['captures'] if c['nom'] == 'echec'])


if __name__ == '__main__':
    unittest.main()
