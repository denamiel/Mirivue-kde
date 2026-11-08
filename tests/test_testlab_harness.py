# SPDX-License-Identifier: MIT
"""Mirivue TestLab: the harness must record success, detect failure, confine
the application, stop every process, delete its disposable root, keep its
reports when cleanup fails and never present Xvfb as a Wayland validation.

When the tests run as root (CI container), MIRIVUE_TESTLAB_USER names the
unprivileged account that runs the application. The display tests need Xvfb,
xdotool, xwd, xclip and the installed mirivue-kde; they are skipped where
those are absent, except when MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1 (CI).
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
REQUIRE_CONFINEMENT = os.environ.get('MIRIVUE_TESTLAB_REQUIRE_CONFINEMENT') == '1'
TEST_USER = os.environ.get('MIRIVUE_TESTLAB_USER')
IS_ROOT = os.geteuid() == 0


def alive(pid):
    try:
        state = Path(f'/proc/{pid}/stat').read_text().split(')')[-1].split()[0]
    except OSError:
        return False
    return state != 'Z'


def confinement_available():
    return (IS_ROOT and bool(TEST_USER)) or harness.bubblewrap_usable()


@unittest.skipUnless(shutil.which('dbus-daemon'), 'dbus-daemon absent')
class FakeApplicationRuns(unittest.TestCase):
    """Harness behaviour with a stand-in application and no display."""

    def setUp(self):
        if IS_ROOT and not TEST_USER:
            self.skipTest('en root, MIRIVUE_TESTLAB_USER est nécessaire')
        self.workspace = Path(tempfile.mkdtemp(prefix='testlab-essai-'))
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)
        if IS_ROOT:
            # The dedicated account must traverse (not read) the workspace.
            self.workspace.chmod(0o711)
        # A personal home stand-in with existing content: it must not change.
        self.personal = self.workspace / 'personnel'
        (self.personal / '.config' / 'pdenams').mkdir(parents=True)
        (self.personal / '.config' / 'pdenams' / 'Mirivue.conf').write_text('[x]\na=1\n')
        (self.personal / '.local' / 'share' / 'Trash' / 'files').mkdir(parents=True)
        self.base = self.workspace / 'racines'
        self.artifacts = self.workspace / 'artefacts'
        self.observed = {}
        patcher = mock.patch.dict(os.environ, {'HOME': str(self.personal)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def lab(self, **options):
        options.setdefault('timeout', 30)
        options.setdefault('user', TEST_USER)
        options.setdefault('base', self.base)
        options.setdefault('watch', [self.personal])
        return Lab('essai', self.artifacts, app=[sys.executable, str(FAKE)], display=False,
                   readonly_paths=[TESTS], **options)

    def run_fake(self, lab, mode, *extra, expect_exit=True):
        """Scenario helper: run the fake application, keep what it observed."""
        output = lab.root / 'tmp' / 'observation.json'
        process = lab.launch(mode, output, *extra)
        if expect_exit:
            code = lab.wait_exit(process, 20)
            self.observed = json.loads(output.read_text(encoding='utf-8'))
            return code
        return process

    def report(self):
        return json.loads((self.artifacts / 'rapport.json').read_text(encoding='utf-8'))

    def assert_clean(self, lab):
        self.assertFalse(lab.root.exists(), 'le dossier jetable doit être supprimé')
        self.assertEqual(harness.marked_processes(lab.root, lab._uids(), lab._dedicated_uid()), [])
        self.assertEqual(list(self.base.iterdir()), [])
        self.assertTrue(self.report()['nettoyage']['reussi'])

    def test_success_is_recorded_and_isolated(self):
        lab = self.lab()

        def scenario(lab):
            with lab.step('application factice'):
                code = self.run_fake(lab, 'succes')
                lab.check(code == 0, f'code {code}')
        self.assertEqual(lab.run(scenario), harness.EXIT_SUCCESS)
        report = self.report()
        self.assertEqual(report['statut'], 'réussi')
        self.assertEqual([step['statut'] for step in report['etapes']], ['réussi'])
        self.assertTrue(report['isolation']['reussi'])
        for key in ('HOME', 'TMPDIR', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME',
                    'XDG_STATE_HOME', 'XDG_RUNTIME_DIR'):
            self.assertTrue(self.observed[key].startswith(str(lab.root) + '/'), (key, self.observed[key]))
        self.assertIn(str(lab.root / 'run' / 'bus'), self.observed['DBUS_SESSION_BUS_ADDRESS'])
        self.assertFalse((self.personal / 'marqueur-testlab').exists())
        self.assertNotIn('<failure', (self.artifacts / 'junit.xml').read_text())
        if IS_ROOT:
            self.assertEqual(report['environnement']['confinement'], 'uid')
            self.assertNotEqual(self.observed['uid'], 0, 'l’application ne doit jamais tourner en root')
        self.assert_clean(lab)

    def test_failure_returns_non_zero_and_keeps_diagnostics(self):
        lab = self.lab()

        def scenario(lab):
            with lab.step('application factice en échec'):
                code = self.run_fake(lab, 'echec')
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
        child = {}

        def scenario(lab):
            with lab.step('application bloquée'):
                process = self.run_fake(lab, 'bloque', expect_exit=False)
                marker = lab.root / 'tmp' / 'observation.json.enfant'
                lab.wait_until(marker.exists, 5, 'enfant démarré')
                child['pid'] = int(marker.read_text())
                lab.wait_exit(process, 60)
        start = time.monotonic()
        self.assertEqual(lab.run(scenario), harness.EXIT_SCENARIO_FAILED)
        self.assertLess(time.monotonic() - start, 30, 'le délai global doit borner le scénario')
        self.assertFalse(alive(child['pid']), 'un processus détaché ignorant SIGTERM doit être arrêté')
        self.assertIn('ne s’est pas arrêté', self.report()['erreur'])
        self.assert_clean(lab)

    @unittest.skipIf(IS_ROOT, 'en root, le harness refuse le mode sans confinement')
    def test_unconfined_write_outside_the_root_is_detected(self):
        lab = self.lab(confinement='aucun')
        target = self.personal / '.config' / 'pdenams' / 'intrus.conf'

        def scenario(lab):
            with lab.step('écriture interdite'):
                self.run_fake(lab, 'ecrit', target)
        self.assertEqual(lab.run(scenario), harness.EXIT_CLEANUP_FAILED)
        report = self.report()
        self.assertEqual(report['environnement']['confinement'], 'aucun')
        self.assertFalse(report['isolation']['reussi'])
        self.assertIn(str(target), report['isolation']['modifications'])
        self.assertIn('<failure', (self.artifacts / 'junit.xml').read_text())

    def test_confined_application_cannot_write_to_a_personal_home(self):
        if not confinement_available():
            if REQUIRE_CONFINEMENT:
                self.fail('Aucun confinement disponible alors qu’il est exigé.')
            self.skipTest('ni compte dédié en root, ni bubblewrap utilisable')
        lab = self.lab(require_confinement=True)
        target = self.personal / '.config' / 'pdenams' / 'intrus.conf'

        def scenario(lab):
            with lab.step('écriture hors du dossier jetable'):
                self.run_fake(lab, 'ecrit', target)
        self.assertEqual(lab.run(scenario), harness.EXIT_SUCCESS)
        self.assertIn(self.report()['environnement']['confinement'], ('uid', 'bwrap'))
        self.assertTrue(self.observed['ecriture'].startswith('refusée'), self.observed)
        self.assertFalse(target.exists())
        self.assertTrue(self.report()['isolation']['reussi'])
        self.assert_clean(lab)

    def test_root_without_a_dedicated_account_is_refused(self):
        lab = self.lab(user=None)
        with mock.patch.object(harness.os, 'geteuid', return_value=0):
            self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        self.assertIn('Refus de lancer l’application en root', self.report()['erreur'])
        self.assertFalse(self.base.exists() and any(self.base.iterdir()))

    def test_dedicated_account_already_in_use_is_refused(self):
        account = harness.pwd.getpwuid(os.getuid())
        lab = self.lab(user=account.pw_name)
        with mock.patch.object(harness.os, 'geteuid', return_value=0), \
                mock.patch.object(harness.pwd, 'getpwnam', return_value=mock.Mock(pw_uid=4242, pw_gid=4242, pw_name=account.pw_name)), \
                mock.patch.object(harness, 'processes_of_uid', return_value=[123]):
            self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        self.assertIn('réservé à TestLab', self.report()['erreur'])

    def test_required_confinement_without_any_mechanism_is_refused(self):
        lab = self.lab(user=None, require_confinement=True)
        with mock.patch.object(harness.os, 'geteuid', return_value=1000), \
                mock.patch.object(harness, 'bubblewrap_usable', return_value=False):
            self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        self.assertIn('Aucun confinement disponible', self.report()['erreur'])

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
        lab = self.lab(base=self.personal / 'tmp', watch=[])
        self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
        self.assertIn('dossier personnel', self.report()['erreur'])
        self.assertEqual(list((self.personal / 'tmp').iterdir()), [])

    # ------------------------------------------------- cleanup failures (P2)
    def failing_lab(self, **patches):
        lab = self.lab()
        for name, effect in patches.items():
            patcher = mock.patch.object(Lab, name, side_effect=effect)
            patcher.start()
            self.addCleanup(patcher.stop)
        return lab

    def test_deletion_failure_keeps_reports_and_scenario_error(self):
        lab = self.failing_lab(_remove_tree=OSError('disque en lecture seule'))
        self.addCleanup(lambda: lab.root and shutil.rmtree(lab.root, ignore_errors=True))

        def scenario(lab):
            with lab.step('application factice en échec'):
                lab.check(self.run_fake(lab, 'echec') == 0, 'échec initial du scénario')
        self.assertEqual(lab.run(scenario), harness.EXIT_CLEANUP_FAILED)
        report = self.report()
        self.assertEqual(report['statut'], 'échec')
        self.assertIn('échec initial du scénario', report['erreur'])
        self.assertFalse(report['nettoyage']['reussi'])
        self.assertFalse(report['nettoyage']['dossier_supprime'])
        self.assertTrue(any('suppression du dossier jetable' in e and 'lecture seule' in e
                            for e in report['nettoyage']['erreurs']), report['nettoyage'])
        self.assertEqual(harness.marked_processes(lab.root, lab._uids(), lab._dedicated_uid()), [], 'les processus sont arrêtés')
        junit = (self.artifacts / 'junit.xml').read_text()
        self.assertIn('name="nettoyage"', junit)
        self.assertIn('errors="1"', junit)
        self.assertTrue((self.artifacts / 'journaux' / 'harness.log').exists())

    def test_log_preservation_and_process_scan_failures_are_reported(self):
        lab = self.failing_lab(_preserve_application_logs=RuntimeError('journal illisible'))
        original = harness.marked_processes
        calls = []

        def flaky(root, uids=None, dedicated_uid=None):
            calls.append(root)
            if len(calls) == 3:
                raise PermissionError('/proc inaccessible')
            return original(root, uids, dedicated_uid)
        patcher = mock.patch.object(harness, 'marked_processes', side_effect=flaky)
        patcher.start()
        self.addCleanup(patcher.stop)

        def scenario(lab):
            with lab.step('application factice'):
                self.run_fake(lab, 'succes')
        self.assertEqual(lab.run(scenario), harness.EXIT_CLEANUP_FAILED)
        report = self.report()
        self.assertEqual(report['statut'], 'réussi')
        errors = ' | '.join(report['nettoyage']['erreurs'])
        self.assertIn('journal illisible', errors)
        self.assertIn('/proc inaccessible', errors)
        self.assertEqual(report['nettoyage']['processus_restants'], ['inconnu : la recherche a échoué'])
        self.assertTrue(report['nettoyage']['dossier_supprime'], 'les étapes suivantes s’exécutent quand même')

    def test_report_write_failure_still_returns_non_zero(self):
        lab = self.failing_lab(write_reports=OSError('artefacts pleins'))

        def scenario(lab):
            with lab.step('application factice'):
                self.run_fake(lab, 'succes')
        with mock.patch('sys.stderr') as stderr:
            code = lab.run(scenario)
        self.assertEqual(code, harness.EXIT_CLEANUP_FAILED)
        printed = ''.join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn('rapport impossible', printed)
        self.assertIn('"scenario": "essai"', printed)
        self.assertFalse(lab.root.exists())


class ZombieHandling(unittest.TestCase):
    def test_zombies_are_not_counted_as_running_processes(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'], env=dict(os.environ, **{
            harness.MARKER: '/tmp/mirivue-testlab-zombie'}))
        deadline = time.monotonic() + 10
        while not harness.is_zombie(Path(f'/proc/{child.pid}/status').read_text()):
            self.assertLess(time.monotonic(), deadline, 'le processus aurait dû devenir zombie')
            time.sleep(0.05)
        try:
            self.assertNotIn(child.pid, harness.marked_processes('/tmp/mirivue-testlab-zombie', {os.getuid()}))
            self.assertNotIn(child.pid, harness.processes_of_uid(os.getuid()))
        finally:
            child.wait()


class DisplayLockSafety(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='testlab-verrou-'))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.lock = self.directory / '.X99-lock'
        self.socket = self.directory / 'X99'

    def dead_pid(self):
        process = subprocess.Popen(['true'])
        process.wait()
        return process.pid

    def write_lock(self, pid):
        self.lock.write_text(f'{pid:>10}\n')

    def test_lock_of_our_dead_server_is_removed(self):
        pid = self.dead_pid()
        self.write_lock(pid)
        self.assertTrue(harness.remove_stale_display_lock(self.lock, self.socket, pid, True))
        self.assertFalse(self.lock.exists())

    def test_lock_is_kept_while_our_server_runs(self):
        pid = self.dead_pid()
        self.write_lock(pid)
        self.assertFalse(harness.remove_stale_display_lock(self.lock, self.socket, pid, False))
        self.assertTrue(self.lock.exists())

    def test_lock_naming_a_live_process_is_kept(self):
        self.write_lock(os.getpid())
        self.assertFalse(harness.remove_stale_display_lock(self.lock, self.socket, os.getpid(), True))
        self.assertTrue(self.lock.exists())

    def test_lock_of_another_server_is_kept(self):
        self.write_lock(self.dead_pid())
        self.assertFalse(harness.remove_stale_display_lock(self.lock, self.socket, self.dead_pid(), True))
        self.assertTrue(self.lock.exists())

    def test_symlinked_lock_is_not_followed(self):
        target = self.directory / 'cible'
        target.write_text('1\n')
        self.lock.symlink_to(target)
        self.assertFalse(harness.remove_stale_display_lock(self.lock, self.socket, 1, True))
        self.assertTrue(target.exists())


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

    def test_x11_lab_never_claims_wayland_or_plasma(self):
        self.assertEqual(Lab.COVERAGE['x11_xvfb'], 'couvert')
        for name in ('wayland', 'kwin', 'plasma', 'glisser_deposer'):
            self.assertEqual(Lab.COVERAGE[name], 'non couvert', name)
        report = {'scenario': 's', 'statut': 'réussi', 'code_sortie': 0, 'erreur': None, 'duree_s': 1.0,
                  'etapes': [], 'captures': [], 'couverture': dict(Lab.COVERAGE),
                  'environnement': {'confinement': 'uid', 'confinement_description': 'x', 'limite': Lab.LIMIT},
                  'nettoyage': {'reussi': True}, 'isolation': {'reussi': True}}
        summary = harness.markdown_summary(report)
        self.assertIn('wayland ❌', summary)
        self.assertIn('plasma ❌', summary)
        self.assertIn('x11_xvfb ✅', summary)


def display_requirements():
    missing = harness.missing_tools(Lab.DISPLAY_TOOLS + harness.BUS_TOOLS)
    if shutil.which('mirivue-kde') is None:
        missing.append('mirivue-kde')
    if IS_ROOT and not TEST_USER:
        missing.append('MIRIVUE_TESTLAB_USER')
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
        if REQUIRE_CONFINEMENT:
            self.assertIn(report['environnement']['confinement'], ('uid', 'bwrap'))


if __name__ == '__main__':
    unittest.main()
