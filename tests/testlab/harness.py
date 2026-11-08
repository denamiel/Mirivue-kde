# SPDX-License-Identifier: MIT
"""Mirivue TestLab: run the real application in a disposable graphical session.

Each run owns a private root directory holding HOME, every XDG directory, the
KIO Trash, TMPDIR and the disposable fixtures. The application is started as a
separate process on a private Xvfb display with a private D-Bus session bus.
Input goes through the X server (XTEST, via xdotool) so keyboard focus,
shortcuts, dialogs and the real event loop are exercised. Screenshots are taken
from the X framebuffer, outside the application.

Whatever happens, the run ends by collecting diagnostics, stopping every
process it started, deleting its root directory and verifying that both steps
succeeded. The machine-readable result is written as JSON and JUnit XML.

Xvfb is an X11 server without a window manager or Plasma: a passing scenario
proves the application's behaviour on X11, not a Plasma Wayland session.
"""
from contextlib import contextmanager
import datetime
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import select
import shutil
import signal
import struct
import subprocess
import sys
import time
import traceback
from xml.sax.saxutils import escape, quoteattr

from . import xwd

EXIT_SUCCESS = 0
EXIT_SCENARIO_FAILED = 1
EXIT_ENVIRONMENT_UNAVAILABLE = 2
EXIT_CLEANUP_FAILED = 3

DISPLAY_TOOLS = ('Xvfb', 'xdotool', 'xwd', 'xclip')
BUS_TOOLS = ('dbus-daemon',)
MARKER = 'MIRIVUE_TESTLAB_ROOT'
SCREEN = '1280x800x24'

# Mirivue and KIO state that would reveal a write outside the disposable root.
SENSITIVE_HOME_PATHS = (
    '.config/pdenams', '.config/kiorc', '.config/kdeglobals', '.config/dolphinrc',
    '.local/share/Trash', '.local/share/user-places.xbel', '.local/share/mirivue',
    '.local/state/mirivue', '.cache/mirivue',
)


class ScenarioFailure(AssertionError):
    """The application did not behave as the scenario expects."""


class EnvironmentUnavailable(RuntimeError):
    """A required tool is missing: the run proves nothing either way."""


def account_home():
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def is_within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def missing_tools(display=True):
    tools = BUS_TOOLS + (DISPLAY_TOOLS if display else ())
    return [tool for tool in tools if shutil.which(tool) is None]


def write_xauthority(path, cookie):
    """One FamilyWild MIT-MAGIC-COOKIE-1 entry, valid for any display number."""
    def counted(value):
        return struct.pack('>H', len(value)) + value
    entry = (struct.pack('>H', 0xFFFF) + counted(b'') + counted(b'')
             + counted(b'MIT-MAGIC-COOKIE-1') + counted(cookie))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        output.write(entry)


def snapshot(paths, limit=20000, depth_limit=3):
    """Record type, size and mtime of each path and of its first levels."""
    state = {}
    for base in paths:
        base = Path(base)
        try:
            info = base.lstat()
        except FileNotFoundError:
            state[str(base)] = None
            continue
        state[str(base)] = ('d' if base.is_dir() and not base.is_symlink() else 'f', info.st_size, info.st_mtime_ns)
        if not state[str(base)][0] == 'd':
            continue
        pending = [(base, 0)]
        while pending and len(state) < limit:
            directory, depth = pending.pop()
            try:
                children = list(os.scandir(directory))
            except OSError:
                continue
            for child in children:
                try:
                    info = child.stat(follow_symlinks=False)
                except OSError:
                    continue
                is_dir = child.is_dir(follow_symlinks=False)
                state[child.path] = ('d' if is_dir else 'f', info.st_size, info.st_mtime_ns)
                if is_dir and depth + 1 < depth_limit:
                    pending.append((Path(child.path), depth + 1))
    return state


def snapshot_difference(before, after):
    changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
    return changed[:50]


def marked_processes(root):
    """PIDs of this user's processes whose environment carries the run marker."""
    needle = f'{MARKER}={root}'.encode()
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            if entry.stat().st_uid != os.getuid():
                continue
            environment = (entry / 'environ').read_bytes()
        except OSError:
            continue
        if needle in environment.split(b'\0'):
            found.append(int(entry.name))
    return sorted(found)


def process_description(pid):
    try:
        command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace').strip()
    except OSError:
        command = '?'
    return f'{pid} {command[:200]}'


def _disable_core_dumps():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


class Lab:
    """One disposable graphical session for one scenario."""

    def __init__(self, scenario, artifacts, *, app=None, timeout=180.0, display=True,
                 base=None, watch=None, launch_cwd=None, extra_environment=None):
        self.scenario = scenario
        self.artifacts = Path(artifacts).resolve()
        self.app_command = list(app or ['mirivue-kde'])
        self.timeout = float(timeout)
        self.use_display = display
        self.base = Path(base or os.environ.get('MIRIVUE_TESTLAB_TMP') or '/tmp')
        homes = {account_home(), Path(os.environ.get('HOME') or account_home())}
        self.watch = [str(path) for path in watch] if watch is not None else sorted(
            str(home / relative) for home in homes for relative in SENSITIVE_HOME_PATHS)
        self.launch_cwd = launch_cwd
        self.extra_environment = dict(extra_environment or {})
        self.root = None
        self.environment = {}
        self.steps = []
        self.captures = []
        self.services = {}
        self.applications = []
        self.started = None
        self.deadline = None
        self.display = None

    # ----------------------------------------------------------------- paths
    @property
    def home(self):
        return self.root / 'home'

    @property
    def xdg_config(self):
        return self.root / 'xdg' / 'config'

    @property
    def xdg_data(self):
        return self.root / 'xdg' / 'data'

    @property
    def xdg_state(self):
        return self.root / 'xdg' / 'state'

    @property
    def trash_files(self):
        return self.xdg_data / 'Trash' / 'files'

    @property
    def fixtures(self):
        return self.root / 'donnees'

    def log_path(self, name):
        return self.artifacts / 'journaux' / f'{name}.log'

    # ----------------------------------------------------------- preparation
    def prepare(self):
        missing = missing_tools(self.use_display)
        if missing:
            raise EnvironmentUnavailable('Outils absents : ' + ', '.join(missing))
        (self.artifacts / 'journaux').mkdir(parents=True, exist_ok=True)
        (self.artifacts / 'captures').mkdir(exist_ok=True)
        self.base.mkdir(parents=True, exist_ok=True)
        import tempfile
        self.root = Path(tempfile.mkdtemp(prefix='mirivue-testlab-', dir=self.base)).resolve()
        for home in {account_home(), Path(os.environ.get('HOME') or account_home())}:
            if is_within(self.root, home):
                raise EnvironmentUnavailable(
                    f'Le dossier jetable {self.root} se trouve dans un dossier personnel ; '
                    'choisir MIRIVUE_TESTLAB_TMP hors de HOME.')
        for directory in (self.home, self.xdg_config, self.xdg_data, self.xdg_state,
                          self.root / 'xdg' / 'cache', self.root / 'run', self.root / 'tmp', self.fixtures):
            directory.mkdir(parents=True, mode=0o700)
        user = pwd.getpwuid(os.getuid()).pw_name
        self.environment = {
            'PATH': os.environ.get('PATH') or '/usr/bin:/bin',
            'HOME': str(self.home), 'USER': user, 'LOGNAME': user, 'SHELL': '/bin/sh',
            'LANG': 'C.UTF-8',
            'XDG_CONFIG_HOME': str(self.xdg_config), 'XDG_DATA_HOME': str(self.xdg_data),
            'XDG_CACHE_HOME': str(self.root / 'xdg' / 'cache'), 'XDG_STATE_HOME': str(self.xdg_state),
            'XDG_RUNTIME_DIR': str(self.root / 'run'), 'TMPDIR': str(self.root / 'tmp'),
            'XDG_CONFIG_DIRS': '/etc/xdg', 'XDG_DATA_DIRS': '/usr/local/share:/usr/share',
            'QT_QPA_PLATFORM': 'xcb' if self.use_display else 'offscreen',
            'QT_ACCESSIBILITY': '0', 'NO_AT_BRIDGE': '1',
            'PYTHONFAULTHANDLER': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            MARKER: str(self.root),
        }
        self.environment.update(self.extra_environment)
        if self.use_display:
            self._start_display()
        self._start_bus()

    def _service(self, name, command, *, pass_fds=(), stdout=None):
        log = open(self.log_path(name), 'ab')
        process = subprocess.Popen(
            command, env=self.environment, cwd=self.root, stdin=subprocess.DEVNULL,
            stdout=stdout if stdout is not None else log, stderr=log,
            pass_fds=pass_fds, start_new_session=True)
        log.close()
        self.services[name] = process
        return process

    @staticmethod
    def _read_line(stream_fd, timeout, what):
        deadline = time.monotonic() + timeout
        data = b''
        while not data.endswith(b'\n'):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([stream_fd], [], [], remaining)[0]:
                raise EnvironmentUnavailable(f'{what} n’a pas répondu dans le délai.')
            chunk = os.read(stream_fd, 256)
            if not chunk:
                raise EnvironmentUnavailable(f'{what} s’est arrêté au démarrage.')
            data += chunk
        return data.decode().strip()

    def _start_display(self):
        authority = self.root / 'Xauthority'
        write_xauthority(authority, secrets.token_bytes(16))
        reader, writer = os.pipe()
        try:
            self._service('xvfb', ['Xvfb', '-displayfd', str(writer), '-screen', '0', SCREEN,
                                   '-nolisten', 'tcp', '-auth', str(authority), '-noreset'],
                          pass_fds=(writer,))
            os.close(writer)
            writer = None
            number = self._read_line(reader, 20, 'Xvfb')
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)
        self.display = f':{number}'
        self.environment.update(DISPLAY=self.display, XAUTHORITY=str(authority))

    def _start_bus(self):
        process = self._service(
            'dbus', ['dbus-daemon', '--session', '--nofork', '--nopidfile', '--print-address=1',
                     f'--address=unix:path={self.root / "run" / "bus"}'],
            stdout=subprocess.PIPE)
        try:
            address = self._read_line(process.stdout.fileno(), 20, 'dbus-daemon')
        finally:
            process.stdout.close()
        self.environment['DBUS_SESSION_BUS_ADDRESS'] = address

    # -------------------------------------------------------------- fixtures
    def fixture_folder(self, name, files=None, folders=()):
        folder = self.fixtures / name
        folder.mkdir()
        for child in folders:
            (folder / child).mkdir()
        for child, content in (files or {}).items():
            (folder / child).write_text(content, encoding='utf-8')
        return folder

    # ----------------------------------------------------------- application
    def launch(self, *arguments, name='mirivue'):
        log = open(self.log_path(name), 'ab')
        process = subprocess.Popen(
            [*self.app_command, *map(str, arguments)], env=self.environment,
            cwd=self.launch_cwd or self.root / 'tmp', stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            preexec_fn=_disable_core_dumps)
        log.close()
        self.applications.append((name, process))
        return process

    def wait_exit(self, process, timeout=30):
        try:
            return process.wait(timeout=self._bounded(timeout))
        except subprocess.TimeoutExpired:
            raise ScenarioFailure(f'Le processus {process.pid} ne s’est pas arrêté en {timeout} s.') from None

    # ------------------------------------------------------------ assertions
    def _bounded(self, timeout):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ScenarioFailure(f'Délai global du scénario dépassé ({self.timeout:.0f} s).')
        return min(timeout, remaining)

    def wait_until(self, predicate, timeout, description, interval=0.2, allow_exit=False):
        deadline = time.monotonic() + self._bounded(timeout)
        while True:
            result = predicate()
            if result:
                return result
            if time.monotonic() >= deadline:
                raise ScenarioFailure(f'Attente expirée ({timeout} s) : {description}.')
            for name, process in self.applications:
                if not allow_exit and process.poll() is not None:
                    raise ScenarioFailure(
                        f'{name} s’est arrêté (code {process.returncode}) en attendant : {description}.')
            time.sleep(interval)

    def check(self, condition, message):
        if not condition:
            raise ScenarioFailure(message)

    @contextmanager
    def step(self, title):
        record = {'titre': title, 'statut': 'en cours'}
        self.steps.append(record)
        start = time.monotonic()
        try:
            yield record
        except BaseException as error:
            record['statut'] = 'échec'
            record['erreur'] = f'{type(error).__name__}: {error}'
            raise
        else:
            record['statut'] = 'réussi'
        finally:
            record['durée_s'] = round(time.monotonic() - start, 3)

    # ------------------------------------------------------------------- X11
    def xdotool(self, *arguments, timeout=15):
        result = subprocess.run(['xdotool', *map(str, arguments)], env=self.environment,
                                capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip()

    def visible_windows(self):
        code, output = self.xdotool('search', '--onlyvisible', '--name', '.')
        windows = []
        for identifier in output.split() if code == 0 else ():
            _, name = self.xdotool('getwindowname', identifier)
            windows.append((identifier, name))
        return windows

    def wait_window(self, pattern, timeout=20):
        expression = re.compile(pattern)

        def find():
            return next((wid for wid, name in self.visible_windows() if expression.search(name)), None)
        return self.wait_until(find, timeout, f'fenêtre visible « {pattern} »', interval=0.3)

    def wait_no_window(self, pattern, timeout=20):
        expression = re.compile(pattern)
        self.wait_until(lambda: not any(expression.search(name) for _, name in self.visible_windows()),
                        timeout, f'disparition de la fenêtre « {pattern} »', interval=0.3)

    def focused_window(self):
        code, identifier = self.xdotool('getwindowfocus', '-f')
        return identifier if code == 0 else None

    def focus(self, window):
        """Give X input focus (there is no window manager under Xvfb)."""
        self.xdotool('windowfocus', '--sync', window)
        self.wait_until(lambda: self.focused_window() == str(window), 5, f'focus clavier sur {window}')

    def wait_focus(self, window, timeout=10):
        self.wait_until(lambda: self.focused_window() == str(window), timeout, f'focus clavier sur {window}')

    def key(self, *keys):
        code, output = self.xdotool('key', '--clearmodifiers', '--delay', '80', *keys)
        self.check(code == 0, f'xdotool key {" ".join(keys)} a échoué : {output}')
        time.sleep(0.15)

    def type_text(self, text):
        code, output = self.xdotool('type', '--delay', '40', '--', text)
        self.check(code == 0, f'xdotool type a échoué : {output}')

    def clipboard(self, target='text/uri-list'):
        """Read the X CLIPBOARD selection owned by the application."""
        result = subprocess.run(['xclip', '-o', '-selection', 'clipboard', '-t', target],
                                env=self.environment, capture_output=True, timeout=10)
        return result.stdout.decode('utf-8', 'replace') if result.returncode == 0 else ''

    def screenshot(self, name):
        index = len(self.captures) + 1
        stem = f'{index:02d}-{re.sub(r"[^A-Za-z0-9_-]+", "-", name)}'
        raw = self.root / 'tmp' / f'{stem}.xwd'
        target = self.artifacts / 'captures' / f'{stem}.png'
        result = subprocess.run(['xwd', '-root', '-silent', '-out', str(raw)], env=self.environment,
                                capture_output=True, timeout=20)
        if result.returncode != 0:
            raise ScenarioFailure(f'Capture impossible : {result.stderr.decode(errors="replace")}')
        try:
            width, height = xwd.convert(raw, target)
        except xwd.XwdError:
            target = target.with_suffix('.xwd')
            shutil.copyfile(raw, target)
            width = height = None
        raw.unlink()
        self.captures.append({'nom': name, 'fichier': str(target.relative_to(self.artifacts)),
                              'largeur': width, 'hauteur': height})
        return target

    # ----------------------------------------------------- failure evidence
    def _collect_failure_evidence(self):
        notes = []
        if self.display and self.services.get('xvfb') and self.services['xvfb'].poll() is None:
            try:
                self.screenshot('echec')
            except Exception as error:  # evidence collection must not mask the failure
                notes.append(f'capture d’échec impossible : {error}')
            try:
                lines = [f'{wid}\t{name}' for wid, name in self.visible_windows()]
                (self.artifacts / 'fenetres-visibles.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
            except Exception as error:
                notes.append(f'liste des fenêtres impossible : {error}')
        # A still-running Python application prints every thread's stack on
        # SIGABRT (PYTHONFAULTHANDLER=1): useful when the event loop is stuck.
        for name, process in self.applications:
            if process.poll() is None:
                for pid in self._group_members(process.pid):
                    if b'mirivue' in self._cmdline(pid):
                        try:
                            os.kill(pid, signal.SIGABRT)
                        except ProcessLookupError:
                            pass
                time.sleep(2)
        return notes

    @staticmethod
    def _cmdline(pid):
        try:
            return Path(f'/proc/{pid}/cmdline').read_bytes()
        except OSError:
            return b''

    @staticmethod
    def _group_members(pgid):
        members = []
        for entry in Path('/proc').iterdir():
            if entry.name.isdigit():
                try:
                    if os.getpgid(int(entry.name)) == pgid:
                        members.append(int(entry.name))
                except OSError:
                    pass
        return members

    # ------------------------------------------------------------- shutdown
    @staticmethod
    def _stop_group(process, grace=5.0):
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                pass
        # The leader may be gone while its children still run.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def _stop_everything(self):
        for _, process in self.applications:
            self._stop_group(process)
        if self.root is not None:
            for signal_number, pause in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 1.0)):
                remaining = marked_processes(self.root)
                for pid in remaining:
                    try:
                        os.kill(pid, signal_number)
                    except ProcessLookupError:
                        pass
                if remaining:
                    time.sleep(pause)
        for name in ('dbus', 'xvfb'):
            if name in self.services:
                self._stop_group(self.services[name])

    def _remove_display_lock(self):
        """Xvfb leaves /tmp/.X<n>-lock behind only when it was killed."""
        if not self.display:
            return
        number = self.display.lstrip(':')
        lock = Path(f'/tmp/.X{number}-lock')
        xvfb = self.services.get('xvfb')
        try:
            owner = int(lock.read_text().strip())
        except (OSError, ValueError):
            return
        if xvfb is not None and owner == xvfb.pid and xvfb.poll() is not None:
            lock.unlink(missing_ok=True)
            Path(f'/tmp/.X11-unix/X{number}').unlink(missing_ok=True)

    def _preserve_application_logs(self):
        """Mirivue writes its own logs into the disposable XDG_STATE_HOME."""
        if self.root is None or not self.xdg_state.exists():
            return
        for path in sorted(self.xdg_state.rglob('*')):
            if path.is_file() and path.suffix in ('.log', '') and path.stat().st_size < 5_000_000:
                target = self.artifacts / 'journaux' / ('etat-' + '-'.join(path.relative_to(self.xdg_state).parts))
                shutil.copyfile(path, target)

    def _cleanup(self):
        report = {'processus_restants': [], 'dossier_supprime': None, 'verrou_x11': None}
        self._stop_everything()
        if self.root is not None:
            leftovers = marked_processes(self.root)
            report['processus_restants'] = [process_description(pid) for pid in leftovers]
            self._preserve_application_logs()

            def make_writable(function, path, _error):
                os.chmod(Path(path).parent, 0o700)
                os.chmod(path, 0o700)
                function(path)
            shutil.rmtree(self.root, onexc=make_writable) if sys.version_info >= (3, 12) else \
                shutil.rmtree(self.root, onerror=make_writable)
            report['dossier_supprime'] = not self.root.exists()
        self._remove_display_lock()
        if self.display:
            number = self.display.lstrip(':')
            report['verrou_x11'] = not Path(f'/tmp/.X{number}-lock').exists()
        report['reussi'] = (not report['processus_restants'] and report['dossier_supprime'] is not False
                            and report['verrou_x11'] is not False)
        return report

    # ------------------------------------------------------------------ run
    def run(self, scenario_function):
        """Execute the scenario and always clean up; return the exit code."""
        self.started = datetime.datetime.now(datetime.timezone.utc)
        start = time.monotonic()
        self.deadline = start + self.timeout
        status, error, notes = 'réussi', None, []
        before = snapshot(self.watch)
        try:
            self.prepare()
            self.deadline = time.monotonic() + self.timeout
            scenario_function(self)
        except EnvironmentUnavailable as problem:
            status, error = 'indisponible', str(problem)
        except BaseException as problem:  # KeyboardInterrupt and timeouts must still clean up
            status = 'échec'
            error = ''.join(traceback.format_exception_only(type(problem), problem)).strip()
            (self.artifacts / 'journaux').mkdir(parents=True, exist_ok=True)
            with self.log_path('harness').open('a', encoding='utf-8') as log:
                log.write(traceback.format_exc())
            notes = self._collect_failure_evidence()
        cleanup = self._cleanup()
        changed = snapshot_difference(before, snapshot(self.watch))
        isolation = {'chemins_surveilles': self.watch, 'modifications': changed, 'reussi': not changed}
        code = {'réussi': EXIT_SUCCESS, 'échec': EXIT_SCENARIO_FAILED,
                'indisponible': EXIT_ENVIRONMENT_UNAVAILABLE}[status]
        if status != 'indisponible' and not (cleanup['reussi'] and isolation['reussi']):
            code = EXIT_CLEANUP_FAILED
        self.report = {
            'scenario': self.scenario, 'statut': status, 'code_sortie': code, 'erreur': error,
            'notes': notes, 'debut': self.started.isoformat(timespec='seconds'),
            'duree_s': round(time.monotonic() - start, 3), 'delai_s': self.timeout,
            'environnement': {
                'affichage': f'Xvfb {SCREEN} sans gestionnaire de fenêtres' if self.use_display else 'aucun',
                'plateforme_qt': self.environment.get('QT_QPA_PLATFORM'),
                'bus': 'dbus-daemon de session privé', 'application': self.app_command,
                'limite': 'X11/Xvfb : ne valide ni Wayland, ni KWin, ni Plasma.',
            },
            'etapes': self.steps, 'captures': self.captures,
            'nettoyage': cleanup, 'isolation': isolation,
        }
        self.write_reports()
        return code

    def write_reports(self):
        self.artifacts.mkdir(parents=True, exist_ok=True)
        (self.artifacts / 'rapport.json').write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (self.artifacts / 'junit.xml').write_text(junit_xml([self.report]), encoding='utf-8')


def junit_xml(reports):
    cases, failures, errors, skipped, total_time = [], 0, 0, 0, 0.0
    for report in reports:
        steps = report['etapes'] or [{'titre': 'préparation', 'statut': report['statut'],
                                      'erreur': report['erreur'], 'durée_s': report['duree_s']}]
        for step in steps:
            body = ''
            if step['statut'] == 'échec' or (step['statut'] == 'en cours' and report['statut'] == 'échec'):
                failures += 1
                body = f'<failure message={quoteattr(step.get("erreur") or report["erreur"] or "")}/>'
            elif step['statut'] == 'indisponible':
                skipped += 1
                body = f'<skipped message={quoteattr(step.get("erreur") or "")}/>'
            cases.append(f'    <testcase classname={quoteattr("testlab." + report["scenario"])} '
                         f'name={quoteattr(step["titre"])} time="{step.get("durée_s", 0)}">{body}</testcase>')
        for label, part in (('nettoyage', report['nettoyage']), ('isolation', report['isolation'])):
            if report['statut'] == 'indisponible':
                continue
            body = '' if part['reussi'] else f'<failure message={quoteattr(json.dumps(part, ensure_ascii=False))}/>'
            errors += 0 if part['reussi'] else 1
            cases.append(f'    <testcase classname={quoteattr("testlab." + report["scenario"])} '
                         f'name={quoteattr(label)} time="0">{body}</testcase>')
        total_time += report['duree_s']
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<testsuite name="Mirivue TestLab" tests="{len(cases)}" failures="{failures}" '
            f'errors="{errors}" skipped="{skipped}" time="{total_time:.3f}">\n'
            + '\n'.join(cases) + '\n</testsuite>\n')


def markdown_summary(report):
    icon = {'réussi': '✅', 'échec': '❌', 'indisponible': '⚠️'}[report['statut']]
    lines = [f'### {icon} TestLab — {report["scenario"]} ({report["duree_s"]:.1f} s)', '',
             '| Étape | Statut | Durée |', '|---|---|---|']
    for step in report['etapes']:
        lines.append(f'| {escape(step["titre"])} | {step["statut"]} | {step.get("durée_s", 0):.2f} s |')
    lines += ['', f'- Nettoyage vérifié : {"oui" if report["nettoyage"]["reussi"] else "NON"}',
              f'- Dossiers personnels inchangés : {"oui" if report["isolation"]["reussi"] else "NON"}',
              f'- Captures : {len(report["captures"])}',
              f'- Limite : {report["environnement"]["limite"]}']
    if report['erreur']:
        lines.append(f'- Erreur : `{report["erreur"]}`')
    return '\n'.join(lines) + '\n'
