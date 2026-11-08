# SPDX-License-Identifier: MIT
"""Mirivue TestLab on native Wayland: a disposable KWin with its virtual backend.

The application runs with QT_QPA_PLATFORM=wayland against a private
``kwin_wayland --virtual`` started *without* Xwayland and with no DISPLAY, so
an X11 fallback is impossible. Nothing here uses xdotool or X11:

* input: KWin's org_kde_kwin_fake_input protocol, spoken by the pure-Python
  client in ``wayland.py`` (keyboard, absolute pointer, buttons);
* windows, activation and focus: KWin scripts loaded over D-Bus
  (``workspace.windowList()``, ``workspace.activeWindow``); their JSON output
  comes back as a D-Bus call observed by ``dbus-monitor``;
* clipboard: ``wl-paste`` through the ext-data-control protocol;
* screenshots: org.kde.KWin.ScreenShot2 via ``busctl`` (file descriptor
  passing), converted to PNG without third-party modules.

KWIN_WAYLAND_NO_PERMISSION_CHECKS=1 opens these restricted interfaces for
the disposable compositor only.

Limits: this is KWin alone. There is no plasmashell (panels, notifications,
global menu), no xdg-desktop-portal, no real GPU or input device, and no
Plasma session services. KWin 6.8's virtual backend needs a DRM render node
(/dev/dri/renderD*) for compositing; without one, KWin crashes as soon as a
client requests an xdg-activation token, so the lab refuses to start.
"""
import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from . import wayland, xwd
from .harness import EnvironmentUnavailable, Lab, ScenarioFailure

SOCKET = 'wayland-testlab'
WIDTH, HEIGHT = 1280, 800
TOKEN = 'TESTLAB'
SINK = ('org.mirivue.TestLab', '/', 'org.mirivue.TestLab', 'report')

# QImage::Format values that KWin's ScreenShot2 returns, with the byte order in memory.
IMAGE_FORMATS = {
    4: ('B', 'G', 'R', 'X'),     # Format_RGB32 (little-endian 0xffRRGGBB)
    5: ('B', 'G', 'R', 'A'),     # Format_ARGB32
    6: ('B', 'G', 'R', 'A'),     # Format_ARGB32_Premultiplied
    16: ('R', 'G', 'B', 'X'),    # Format_RGBX8888
    17: ('R', 'G', 'B', 'A'),    # Format_RGBA8888
    18: ('R', 'G', 'B', 'A'),    # Format_RGBA8888_Premultiplied
}


def raw_to_rows(data, width, height, stride, image_format):
    if image_format not in IMAGE_FORMATS:
        raise ScenarioFailure(f'Format d’image KWin non pris en charge : {image_format}')
    order = IMAGE_FORMATS[image_format]
    red, green, blue = (order.index(channel) for channel in 'RGB')
    rows = []
    for y in range(height):
        line = data[y * stride:y * stride + width * 4]
        if len(line) < width * 4:
            raise ScenarioFailure('Image ScreenShot2 tronquée.')
        row = bytearray(width * 3)
        row[0::3] = line[red::4]
        row[1::3] = line[green::4]
        row[2::3] = line[blue::4]
        rows.append(bytes(row))
    return rows


def busctl_value(field):
    return field.get('data') if isinstance(field, dict) else field


class WaylandLab(Lab):
    """One disposable KWin Wayland session (virtual backend) for one scenario."""

    DISPLAY_TOOLS = ('kwin_wayland', 'dbus-monitor', 'busctl', 'wl-paste')
    BACKEND = 'wayland-kwin-virtuel'
    COVERAGE = {
        'x11_xvfb': 'non couvert',
        'wayland': 'couvert',
        'kwin': 'couvert (backend virtuel, sans Xwayland)',
        'plasma': 'non couvert',
        'glisser_deposer': 'non couvert',
    }
    LIMIT = ('KWin Wayland virtuel sans Xwayland : pas de plasmashell, de portails, de services de '
             'session Plasma ni de matériel réel. Ce n’est pas une session Plasma complète.')

    def __init__(self, *arguments, **options):
        super().__init__(*arguments, **options)
        self.input = None
        self.script_number = 0
        self.monitor_log = None
        self.kwin_binary = None

    def display_description(self):
        return f'kwin_wayland --virtual {WIDTH}x{HEIGHT}, sans Xwayland'

    # ------------------------------------------------------------- services
    def _start_services(self):
        """Wayland: the bus first (KWin registers on it), then KWin."""
        if not glob.glob('/dev/dri/renderD*'):
            raise EnvironmentUnavailable(
                'Aucun nœud de rendu DRM (/dev/dri/renderD*) : KWin 6.8 ne compose pas sans lui. '
                'En CI, charger le module vgem et transmettre /dev/dri au conteneur.')
        for variable in ('DISPLAY', 'XAUTHORITY'):
            self.environment.pop(variable, None)
        self._start_bus()
        self._start_monitor()
        self._start_kwin()

    def _start_monitor(self):
        self.monitor_log = self.root / 'tmp' / 'kwin-scripts.log'
        output = open(self.monitor_log, 'ab')
        self._own(self.monitor_log)
        process = subprocess.Popen(
            ['dbus-monitor', '--session', f'interface={SINK[2]}'], env=self.environment,
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, cwd=self.root,
            start_new_session=True, **self._process_options())
        output.close()
        self.services['monitor'] = process
        self.wait_until(lambda: self.monitor_log.stat().st_size > 0, 10, 'démarrage de dbus-monitor',
                        allow_exit=True)

    def _start_kwin(self):
        # kwin_wayland carries cap_sys_nice, which a container cannot grant:
        # a private copy without file capabilities runs everywhere.
        (self.root / 'bin').mkdir(mode=0o700)
        self.kwin_binary = self.root / 'bin' / 'kwin_wayland'
        shutil.copyfile(shutil.which('kwin_wayland'), self.kwin_binary)
        self.kwin_binary.chmod(0o755)
        self._own(self.root / 'bin')
        environment = dict(self.environment)
        for variable in ('QT_QPA_PLATFORM', 'WAYLAND_DISPLAY'):
            environment.pop(variable, None)
        environment.update(KWIN_WAYLAND_NO_PERMISSION_CHECKS='1', QT_FORCE_STDERR_LOGGING='1',
                           XDG_SESSION_TYPE='wayland')
        self._service('kwin', [str(self.kwin_binary), '--virtual', '--width', str(WIDTH), '--height', str(HEIGHT),
                               '--socket', SOCKET, '--no-lockscreen', '--no-kactivities'],
                      as_test_account=True, environment=environment)
        socket_path = self.root / 'run' / SOCKET
        self.wait_until(socket_path.exists, 20, 'socket Wayland de KWin', allow_exit=True)
        self.environment.update(WAYLAND_DISPLAY=SOCKET, QT_QPA_PLATFORM='wayland', XDG_SESSION_TYPE='wayland')
        self.display = SOCKET
        # KWin registers org.kde.KWin once its scripting is ready.
        self.wait_until(lambda: self._busctl('status', 'org.kde.KWin', check=False)[0] == 0, 20,
                        'service D-Bus org.kde.KWin', allow_exit=True)
        self.input = wayland.Connection(socket_path)
        self.input.bind_fake_input()

    def _display_alive(self):
        server = self.services.get('kwin')
        return bool(server and server.poll() is None)

    def _service_names(self):
        return ('monitor', 'kwin', 'dbus')

    def _remove_display_lock(self):
        return True

    def _cleanup(self):
        if self.input is not None:
            self.input.close()
            self.input = None
        report = super()._cleanup()
        report.pop('verrou_x11', None)
        return report

    # ---------------------------------------------------------------- D-Bus
    def _busctl(self, *arguments, check=True, pass_fds=(), timeout=20):
        result = subprocess.run(
            ['busctl', f'--address={self.environment["DBUS_SESSION_BUS_ADDRESS"]}', '--json=short', *arguments],
            env=self.environment, capture_output=True, text=True, timeout=timeout, pass_fds=pass_fds,
            **self._process_options())
        if check and result.returncode:
            raise ScenarioFailure(f'busctl {" ".join(arguments[:4])} : {result.stderr.strip()}')
        return result.returncode, result.stdout

    def kwin_script(self, body, timeout=10):
        """Run a KWin script; ``report(value)`` sends JSON back to the harness."""
        self.script_number += 1
        number = self.script_number
        path = self.root / 'tmp' / f'kwin-script-{number}.js'
        path.write_text(
            f'function report(value) {{ callDBus({json.dumps(SINK[0])}, {json.dumps(SINK[1])}, '
            f'{json.dumps(SINK[2])}, {json.dumps(SINK[3])}, "{TOKEN}:{number}:" + JSON.stringify(value)); }}\n'
            + body, encoding='utf-8')
        self._own(path)
        _, output = self._busctl('call', 'org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', 'loadScript',
                                 'ss', str(path), f'testlab-{number}')
        identifier = busctl_value(json.loads(output)['data'][0])
        try:
            self._busctl('call', 'org.kde.KWin', f'/Scripting/Script{identifier}', 'org.kde.kwin.Script', 'run')
            pattern = re.compile(rf'string "{TOKEN}:{number}:(.*)"\s*$')

            def result():
                for line in self.monitor_log.read_text(encoding='utf-8', errors='replace').splitlines():
                    match = pattern.search(line)
                    if match:
                        return [json.loads(match.group(1))]
                return None
            return self.wait_until(result, timeout, 'réponse du script KWin', interval=0.1)[0]
        finally:
            self._busctl('call', 'org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', 'unloadScript',
                         's', f'testlab-{number}', check=False)

    def windows(self):
        return self.kwin_script('''
report(workspace.windowList().filter(w => !w.deleted).map(w => ({
    id: w.internalId.toString(), caption: w.caption, pid: w.pid, active: w.active,
    resourceClass: w.resourceClass, dialog: w.dialog, normal: w.normalWindow,
    x: w.frameGeometry.x, y: w.frameGeometry.y, width: w.frameGeometry.width, height: w.frameGeometry.height,
})));''')

    # --------------------------------------------- window API used by scenarios
    def visible_windows(self):
        return [(window['id'], window['caption']) for window in self.windows()]

    def window(self, identifier):
        return next((window for window in self.windows() if window['id'] == identifier), None)

    def focused_window(self):
        return next((window['id'] for window in self.windows() if window['active']), None)

    def focus(self, window):
        """Activate through KWin, as a click on the task manager would."""
        self.kwin_script(f'''
for (const w of workspace.windowList()) {{
    if (w.internalId.toString() === {json.dumps(window)}) {{ workspace.activeWindow = w; }}
}}
report(true);''')
        self.wait_until(lambda: self.focused_window() == window, 5, f'activation de {window}')

    def key(self, *keys):
        for combination in keys:
            self.input.press(combination.lower())
        time.sleep(0.15)

    def type_text(self, text):
        self.input.type_text(text)

    def pointer_drag(self, start, end, steps=12, hold=0.3):
        """Press, move in steps and release: a real compositor-mediated drag."""
        self.input.move_to(*start)
        time.sleep(0.2)
        self.input.button(wayland.BTN_LEFT, True)
        time.sleep(hold)
        for step in range(1, steps + 1):
            fraction = step / steps
            self.input.move_to(start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction)
            time.sleep(0.04)
        time.sleep(hold)
        self.input.button(wayland.BTN_LEFT, False)
        time.sleep(0.3)

    def click(self, position, button=wayland.BTN_LEFT):
        self.input.move_to(*position)
        time.sleep(0.1)
        self.input.button(button, True)
        self.input.button(button, False)
        time.sleep(0.2)

    def clipboard(self, target='text/uri-list'):
        result = subprocess.run(['wl-paste', '--no-newline', '--type', target], env=self.environment,
                                capture_output=True, timeout=10, **self._process_options())
        return result.stdout.decode('utf-8', 'replace') if result.returncode == 0 else ''

    def screenshot(self, name):
        stem, target = self._capture_target(name)
        reader, writer = os.pipe()
        chunks = []

        def drain():
            while True:
                data = os.read(reader, 1 << 20)
                if not data:
                    return
                chunks.append(data)
        thread = threading.Thread(target=drain, daemon=True)
        thread.start()
        try:
            code, output = self._busctl('call', 'org.kde.KWin.ScreenShot2', '/org/kde/KWin/ScreenShot2',
                                        'org.kde.KWin.ScreenShot2', 'CaptureWorkspace', 'a{sv}h',
                                        '1', 'native-resolution', 'b', 'true', str(writer),
                                        pass_fds=(writer,), check=False)
        finally:
            os.close(writer)
        thread.join(20)
        os.close(reader)
        if code:
            raise ScenarioFailure(f'Capture KWin impossible : {output.strip()}')
        metadata = {key: busctl_value(value) for key, value in json.loads(output)['data'][0].items()}
        width, height = int(metadata['width']), int(metadata['height'])
        rows = raw_to_rows(b''.join(chunks), width, height, int(metadata['stride']), int(metadata['format']))
        target.write_bytes(xwd.png_bytes(width, height, rows))
        return self._record_capture(name, target, width, height)

    def window_listing(self):
        return [f'{w["id"]}\t{"actif" if w["active"] else "-"}\t{w["x"]},{w["y"]} {w["width"]}x{w["height"]}'
                f'\t{w["resourceClass"]}\t{w["caption"]}' for w in self.windows()]

    # ------------------------------------------------------------ Wayland proof
    def application_platform(self, process):
        """Return the Qt platform plugins mapped by the application's Python process."""
        for pid in self._group_members(process.pid):
            if b'mirivue' not in self._cmdline(pid):
                continue
            result = subprocess.run(['cat', f'/proc/{pid}/maps'], capture_output=True, text=True,
                                    timeout=10, **self._process_options())
            if result.returncode == 0:
                plugins = set(re.findall(r'/platforms/(lib\w+)\.so', result.stdout))
                if plugins:
                    return plugins
        return set()

    def assert_native_wayland(self, process):
        self.check('DISPLAY' not in self.environment, 'DISPLAY ne doit pas exister dans la session Wayland.')
        self.check('--xwayland' not in self.services['kwin'].args, 'KWin ne doit pas démarrer Xwayland.')
        plugins = self.application_platform(process)
        self.check('libqwayland' in plugins, f'Greffon Qt Wayland non chargé : {sorted(plugins)}')
        self.check(not any('xcb' in plugin for plugin in plugins), f'Greffon X11 chargé : {sorted(plugins)}')
        return sorted(plugins)
