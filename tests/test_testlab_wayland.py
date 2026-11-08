# SPDX-License-Identifier: MIT
"""Mirivue TestLab on native Wayland.

* The pure-Python fake-input client is checked against a fake compositor
  socket: exact wire messages, roundtrips and protocol errors.
* Screenshot decoding and the coverage claims are checked without KWin.
* With kwin_wayland, a DRM render node and the installed mirivue-kde, the real
  scenarios run: native Wayland (no Xwayland), focus, activation, shortcuts,
  clipboard, drag and drop and the negative control. They run only with
  MIRIVUE_TESTLAB_RUN_REAL=1 or MIRIVUE_TESTLAB_REQUIRE_WAYLAND=1 (CI, where a
  missing prerequisite is a failure).
"""
import glob
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from testlab import harness, wayland  # noqa: E402
from testlab.harness import EnvironmentUnavailable  # noqa: E402
from testlab.wayland_lab import WaylandLab, raw_to_rows  # noqa: E402

RUNNER = TESTS / 'testlab' / 'run.py'
REQUIRE_WAYLAND = os.environ.get('MIRIVUE_TESTLAB_REQUIRE_WAYLAND') == '1'
# The real application only runs where explicitly allowed (CI, disposable
# container or VM), never by accident in a developer's personal session.
RUN_REAL = REQUIRE_WAYLAND or os.environ.get('MIRIVUE_TESTLAB_RUN_REAL') == '1'
TEST_USER = os.environ.get('MIRIVUE_TESTLAB_USER')


class FakeCompositor(threading.Thread):
    """Answers get_registry/sync and records every request sent to fake-input."""

    def __init__(self, path, fake_input_version=6, error_on_key=False):
        super().__init__(daemon=True)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(1)
        self.version = fake_input_version
        self.error_on_key = error_on_key
        self.requests = []
        self.bound = None
        self.start()

    @staticmethod
    def message(object_id, opcode, payload=b''):
        return struct.pack('=II', object_id, (8 + len(payload)) << 16 | opcode) + payload

    def run(self):
        connection, _ = self.server.accept()
        buffer = b''
        registry = None
        with connection:
            while True:
                data = connection.recv(65536)
                if not data:
                    return
                buffer += data
                while len(buffer) >= 8:
                    object_id, header = struct.unpack_from('=II', buffer)
                    size, opcode = header >> 16, header & 0xFFFF
                    if len(buffer) < size:
                        break
                    payload, buffer = buffer[8:size], buffer[size:]
                    if object_id == 1 and opcode == 1:          # get_registry
                        registry = struct.unpack('=I', payload)[0]
                        for name, interface, version in ((1, 'wl_seat', 7),
                                                         (9, wayland.FAKE_INPUT, self.version)):
                            connection.sendall(self.message(
                                registry, 0, struct.pack('=I', name) + wayland._string(interface)
                                + struct.pack('=I', version)))
                    elif object_id == 1 and opcode == 0:        # sync
                        callback = struct.unpack('=I', payload)[0]
                        connection.sendall(self.message(callback, 0, struct.pack('=I', 0)))
                    elif object_id == registry and opcode == 0:  # bind
                        self.bound = payload
                    else:
                        self.requests.append((object_id, opcode, payload))
                        if self.error_on_key and opcode == wayland.KEYBOARD_KEY:
                            connection.sendall(self.message(1, 0, struct.pack('=II', object_id, 3)
                                                            + wayland._string('refusé')))


class WireProtocol(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix='testlab-wl-'))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.path = self.directory / 'wayland-essai'

    def connect(self, **options):
        compositor = FakeCompositor(self.path, **options)
        connection = wayland.Connection(self.path, timeout=5)
        self.addCleanup(connection.close)
        return compositor, connection

    def test_registry_and_bind_request(self):
        compositor, connection = self.connect()
        self.assertEqual(connection.globals[wayland.FAKE_INPUT], (9, 6))
        connection.bind_fake_input('Essai', 'raison')
        name = struct.unpack_from('=I', compositor.bound)[0]
        self.assertEqual(name, 9)
        self.assertIn(wayland.FAKE_INPUT.encode() + b'\0', compositor.bound)
        version, new_id = struct.unpack_from('=II', compositor.bound, len(compositor.bound) - 8)
        self.assertEqual((version, new_id), (6, connection.fake_input))
        object_id, opcode, payload = compositor.requests[0]
        self.assertEqual((object_id, opcode), (connection.fake_input, wayland.AUTHENTICATE))
        self.assertIn(b'Essai\0', payload)

    def keys(self, compositor, connection):
        return [struct.unpack('=II', payload) for object_id, opcode, payload in compositor.requests
                if object_id == connection.fake_input and opcode == wayland.KEYBOARD_KEY]

    def test_shortcut_presses_modifiers_first_and_releases_in_reverse(self):
        compositor, connection = self.connect()
        connection.bind_fake_input()
        connection.press('ctrl+shift+n', delay=0)
        self.assertEqual(self.keys(compositor, connection),
                         [(29, 1), (42, 1), (49, 1), (49, 0), (42, 0), (29, 0)])

    def test_text_uses_shift_for_capitals_and_symbols(self):
        compositor, connection = self.connect()
        connection.bind_fake_input()
        connection.type_text('Ab 1!', delay=0)
        self.assertEqual(self.keys(compositor, connection), [
            (42, 1), (30, 1), (30, 0), (42, 0), (48, 1), (48, 0), (57, 1), (57, 0),
            (2, 1), (2, 0), (42, 1), (2, 1), (2, 0), (42, 0)])

    def test_pointer_uses_fixed_point_coordinates(self):
        compositor, connection = self.connect()
        connection.bind_fake_input()
        connection.move_to(10.5, 20)
        connection.button(wayland.BTN_LEFT, True)
        motion = [p for i, o, p in compositor.requests if o == wayland.POINTER_MOTION_ABSOLUTE][0]
        self.assertEqual(struct.unpack('=ii', motion), (int(10.5 * 256), 20 * 256))
        button = [p for i, o, p in compositor.requests if o == wayland.BUTTON][0]
        self.assertEqual(struct.unpack('=II', button), (wayland.BTN_LEFT, 1))

    def test_protocol_error_is_raised(self):
        compositor, connection = self.connect(error_on_key=True)
        connection.bind_fake_input()
        with self.assertRaisesRegex(wayland.WaylandError, 'refusé'):
            connection.press('a', delay=0)

    def test_old_fake_input_without_keyboard_is_refused(self):
        compositor, connection = self.connect(fake_input_version=3)
        with self.assertRaisesRegex(wayland.WaylandError, 'clavier indisponible'):
            connection.bind_fake_input()

    def test_unknown_keys_and_characters_are_refused(self):
        with self.assertRaises(wayland.WaylandError):
            wayland.combination('ctrl+inconnue')
        with self.assertRaises(wayland.WaylandError):
            wayland.text_keys('é')


class ScreenshotAndClaims(unittest.TestCase):
    def test_raw_formats_are_converted_to_rgb(self):
        rgbx = bytes([10, 20, 30, 255, 40, 50, 60, 255])
        self.assertEqual(raw_to_rows(rgbx, 2, 1, 8, 16), [bytes([10, 20, 30, 40, 50, 60])])
        argb_little_endian = bytes([30, 20, 10, 255, 60, 50, 40, 255])
        self.assertEqual(raw_to_rows(argb_little_endian, 2, 1, 8, 6), [bytes([10, 20, 30, 40, 50, 60])])
        with self.assertRaises(harness.ScenarioFailure):
            raw_to_rows(rgbx, 2, 1, 8, 99)

    def test_wayland_lab_never_claims_plasma_or_x11(self):
        self.assertTrue(WaylandLab.COVERAGE['wayland'].startswith('couvert'))
        self.assertEqual(WaylandLab.COVERAGE['plasma'], 'non couvert')
        self.assertEqual(WaylandLab.COVERAGE['x11_xvfb'], 'non couvert')
        self.assertEqual(WaylandLab.COVERAGE['glisser_deposer'], 'non couvert',
                         'seul un scénario de glisser-déposer réussi peut le déclarer couvert')
        self.assertIn('pas une session Plasma complète', WaylandLab.LIMIT)

    def test_missing_render_node_is_an_unavailable_environment(self):
        if os.geteuid() == 0 and not TEST_USER:
            self.skipTest('en root, MIRIVUE_TESTLAB_USER est nécessaire')
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o711)  # the dedicated account traverses it in uid mode
            lab = WaylandLab('essai', Path(directory) / 'artefacts', display=True, base=directory,
                             watch=[], user=TEST_USER, confinement='aucun' if os.geteuid() else 'auto')
            with mock.patch.object(harness, 'missing_tools', return_value=[]), \
                    mock.patch('testlab.wayland_lab.glob.glob', return_value=[]):
                self.assertEqual(lab.run(lambda lab: None), harness.EXIT_ENVIRONMENT_UNAVAILABLE)
            report = json.loads((Path(directory) / 'artefacts' / 'rapport.json').read_text())
            self.assertIn('nœud de rendu', report['erreur'])
            self.assertTrue(report['nettoyage']['reussi'])


def wayland_requirements():
    missing = harness.missing_tools(WaylandLab.DISPLAY_TOOLS + harness.BUS_TOOLS)
    if not glob.glob('/dev/dri/renderD*'):
        missing.append('/dev/dri/renderD*')
    if shutil.which('mirivue-kde') is None:
        missing.append('mirivue-kde')
    if os.geteuid() == 0 and not TEST_USER:
        missing.append('MIRIVUE_TESTLAB_USER')
    return missing


class InstalledApplicationOnKWin(unittest.TestCase):
    def setUp(self):
        if not RUN_REAL:
            self.skipTest('application réelle : définir MIRIVUE_TESTLAB_RUN_REAL=1 (CI ou conteneur jetable)')
        missing = wayland_requirements()
        if missing:
            if REQUIRE_WAYLAND:
                self.fail('Prérequis Wayland absents : ' + ', '.join(missing))
            self.skipTest('Prérequis Wayland absents : ' + ', '.join(missing))
        self.workspace = Path(tempfile.mkdtemp(prefix='testlab-wl-reel-'))
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def run_scenario(self, name):
        artifacts = self.workspace / name
        environment = dict(os.environ)
        environment.pop('GITHUB_STEP_SUMMARY', None)
        result = subprocess.run([sys.executable, str(RUNNER), name, '--artefacts', str(artifacts), '--delai', '150'],
                                env=environment, capture_output=True, text=True, timeout=400)
        report = json.loads((artifacts / 'rapport.json').read_text(encoding='utf-8'))
        return result, report, artifacts

    def test_negative_control_fails_with_capture_windows_and_cleanup(self):
        result, report, artifacts = self.run_scenario('wayland-controle-echec')
        self.assertEqual(result.returncode, harness.EXIT_SCENARIO_FAILED, result.stdout + result.stderr)
        self.assertEqual(report['environnement']['moteur'], 'wayland-kwin-virtuel')
        failure = [capture for capture in report['captures'] if capture['nom'] == 'echec']
        self.assertEqual(len(failure), 1, report['captures'])
        png = (artifacts / failure[0]['fichier']).read_bytes()
        self.assertTrue(png.startswith(b'\x89PNG'))
        self.assertGreater(len(png), 5000)
        self.assertIn('Mirivue', (artifacts / 'fenetres-visibles.txt').read_text(encoding='utf-8'))
        self.assertTrue((artifacts / 'journaux' / 'kwin.log').exists())
        self.assertTrue(report['nettoyage']['reussi'])
        self.assertTrue(report['isolation']['reussi'])

    def test_essential_scenario_runs_on_native_wayland(self):
        result, report, _ = self.run_scenario('wayland-essentiel')
        self.assertEqual(result.returncode, harness.EXIT_SUCCESS, result.stdout + result.stderr)
        self.assertEqual(report['etapes'][0]['details']['greffons_qt'], ['libqwayland'])
        self.assertEqual(report['couverture']['plasma'], 'non couvert')

    def test_drag_and_drop_scenario_moves_the_file(self):
        result, report, _ = self.run_scenario('wayland-glisser-deposer')
        self.assertEqual(result.returncode, harness.EXIT_SUCCESS, result.stdout + result.stderr)
        self.assertTrue(report['couverture']['glisser_deposer'].startswith('couvert'))


if __name__ == '__main__':
    unittest.main()
