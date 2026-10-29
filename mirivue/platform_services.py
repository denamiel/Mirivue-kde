from __future__ import annotations
from .i18n import tr, trf
tr('Small, explicit bridges to the operating system.\n\nThe media and file-management core must never need to know whether it runs on\nLinux, macOS or Windows.  Unsupported desktop features are described as a\ncapability instead of being guessed from a Linux command name.\n')
import errno
import ctypes
import os
import shutil
import sys
import json
import selectors
import subprocess
import time
import threading
import uuid
import select
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QDir, QObject, QProcess, QStandardPaths, Signal
from PySide6.QtGui import QDesktopServices, QColor, QPalette
from PySide6.QtWidgets import QApplication

@contextmanager
def _kio_turn(lock, cancelled):
    acquired = False
    try:
        while not acquired:
            if cancelled is not None and cancelled():
                yield False
                return
            acquired = lock.acquire(timeout=0.05)
        yield True
    finally:
        if acquired:
            lock.release()
from PySide6.QtCore import QUrl
from .diagnostics import record_tool_failure

@dataclass(frozen=True)
class Capabilities:
    applications: bool
    empty_trash: bool
    terminal: bool
    kde_theme: bool
    kde_places: bool

class KioServiceEvents(QObject):
    undo_state_changed = Signal(bool, str)
    redo_state_changed = Signal(bool, str)

class PlatformServices:

    def __init__(self) -> None:
        self.name = tr('windows') if os.name == tr('nt') else tr('macos') if sys.platform == tr('darwin') else tr('linux')
        self.kio_events = KioServiceEvents()
        self._kio_lock = threading.RLock()
        self._kio_process = None
        self._kio_input_path = None
        self._kio_output_path = None
        self._kio_input_fd = None
        self._kio_output_fd = None
        self._kio_undo_available = False
        self._kio_undo_text = ''
        self._kio_redo_available = False
        self._kio_redo_text = ''
        self._icon_theme_library = None
        self._semantic_colors = {}

    @property
    def desktop_names(self) -> set[str]:
        values = tr(' ').join(filter(None, (os.environ.get(tr('XDG_CURRENT_DESKTOP'), ''), os.environ.get(tr('XDG_SESSION_DESKTOP'), ''), os.environ.get(tr('DESKTOP_SESSION'), ''), os.environ.get(tr('KDE_FULL_SESSION'), ''))))
        return {part.casefold() for part in values.replace(tr(':'), tr(' ')).replace(tr(';'), tr(' ')).split()}

    @property
    def is_plasma(self) -> bool:
        return self.name == tr('linux') and bool(self.desktop_names & {tr('kde'), tr('plasma'), tr('plasmawayland'), tr('plasmax11'), tr('true')})

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(applications=self.name == tr('linux'), empty_trash=self.name == tr('linux'), terminal=True, kde_theme=self.is_plasma, kde_places=self.name == tr('linux') and bool(self.tool_path('libmirivue-kio-places-widget.so')))

    def app_directory(self, location: QStandardPaths.StandardLocation) -> Path:
        path = QStandardPaths.writableLocation(location)
        return Path(path) if path else Path.home()

    def cache_directory(self) -> Path:
        return self.app_directory(QStandardPaths.StandardLocation.CacheLocation)

    def shared_cache_directory(self) -> Path:
        """Return the desktop-wide cache root (e.g. ~/.cache), not app-private cache."""
        location = getattr(QStandardPaths.StandardLocation, tr('GenericCacheLocation'), QStandardPaths.StandardLocation.CacheLocation)
        return self.app_directory(location)

    def state_directory(self) -> Path:
        location = getattr(QStandardPaths.StandardLocation, tr('StateLocation'), QStandardPaths.StandardLocation.AppLocalDataLocation)
        return self.app_directory(location)

    def bundled_tool_directories(self) -> list[Path]:
        root = Path(__file__).resolve().parent
        directories = [root / tr('tools'), root.parent / tr('tools'), root.parent / tr('native') / tr('bin')]
        if self.name == tr('macos'):
            directories += [root.parent / tr('Resources') / tr('tools'), root.parent.parent / tr('Resources') / tr('tools')]
        return directories

    def prepare_runtime(self) -> None:
        tr('Make bundled command-line tools available to existing workers.')
        folders = [str(path) for path in self.bundled_tool_directories() if path.is_dir()]
        if folders:
            current = os.environ.get(tr('PATH'), '')
            os.environ[tr('PATH')] = os.pathsep.join([*folders, current]) if current else os.pathsep.join(folders)

    def initialize_icon_theme(self) -> None:
        """Install KF6's icon engine before constructing QApplication."""
        if self.name != 'linux':
            return
        library_path = self.tool_path('libmirivue-kio-places-widget.so')
        if not library_path:
            return  # Source-only validation can run without compiled helpers.
        self._icon_theme_library = ctypes.CDLL(library_path)
        initialize = self._icon_theme_library.mirivue_icon_theme_init
        initialize.argtypes = []
        initialize.restype = None
        initialize()

    def initialize_application_style(self) -> None:
        """Let KF6 select KDE's configured Qt widget style after QApplication."""
        QApplication.instance().paletteChanged.connect(lambda *_: self._semantic_colors.clear())
        if self.name != 'linux' or self._icon_theme_library is None:
            return
        initialize = self._icon_theme_library.mirivue_application_style_init
        initialize.argtypes = []
        initialize.restype = None
        initialize()

    def semantic_color(self, meaning: str, inactive: bool = False) -> QColor:
        """Use the active KF6 View foreground for an item status."""
        roles = {'positive': 0, 'neutral': 1, 'negative': 2, 'link': 3}
        if meaning not in roles:
            raise ValueError(meaning)
        cache_key = (meaning, inactive)
        if cache_key not in self._semantic_colors:
            color = None
            if self._icon_theme_library is not None:
                getter = self._icon_theme_library.mirivue_semantic_foreground
                getter.argtypes = [ctypes.c_int, ctypes.c_int]
                getter.restype = ctypes.c_uint
                rgba = getter(roles[meaning], int(inactive))
                if rgba:
                    color = QColor.fromRgba(rgba)
            if color is None:
                role = QPalette.ColorRole.Link if meaning == 'link' else QPalette.ColorRole.Text
                group = QPalette.ColorGroup.Inactive if inactive else QPalette.ColorGroup.Active
                color = QApplication.palette().color(group, role)
            self._semantic_colors[cache_key] = color
        return self._semantic_colors[cache_key]

    def invalidate_theme_colors(self) -> None:
        self._semantic_colors.clear()

    def format_bytes(self, value: float) -> str | None:
        """Use the KDE unit dialect; return None without the native bridge."""
        if self._icon_theme_library is None:
            return None
        formatter = self._icon_theme_library.mirivue_format_byte_size
        formatter.argtypes = [ctypes.c_double, ctypes.c_void_p, ctypes.c_size_t]
        formatter.restype = ctypes.c_int
        output = ctypes.create_string_buffer(128)
        return output.value.decode('utf-8') if formatter(float(value), output, len(output)) > 0 else None

    def format_relative_date(self, timestamp_ns: int) -> str | None:
        """Use KFormat's relative date style, as Dolphin does."""
        if self._icon_theme_library is None:
            return None
        formatter = getattr(self._icon_theme_library, 'mirivue_format_relative_date', None)
        if formatter is None:
            return None  # Source-only use with an older native library.
        formatter.argtypes = [ctypes.c_longlong, ctypes.c_void_p, ctypes.c_size_t]
        formatter.restype = ctypes.c_int
        output = ctypes.create_string_buffer(4096)
        return output.value.decode('utf-8') if formatter(int(timestamp_ns) // 1_000_000, output, len(output)) > 0 else None

    def tool_path(self, name: str) -> str | None:
        candidates = [name]
        if self.name == tr('windows') and (not name.lower().endswith(tr('.exe'))):
            candidates.insert(0, name + tr('.exe'))
        for directory in self.bundled_tool_directories():
            for candidate in candidates:
                path = directory / candidate
                if path.is_file() and os.access(path, os.X_OK):
                    return str(path)
        for candidate in candidates:
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def places_helper(self) -> str | None:
        return self.tool_path('mirivue-kio-places')

    def list_places(self) -> list[dict] | None:
        # KFilePlacesModel talks to the live Plasma session (Solid and D-Bus).
        # An offscreen/minimal Qt process has no usable desktop session, and
        # probing it can block while the desktop services time out.  Keep
        # command-line and automated tests deterministic by using Mirivue's
        # ordinary local fallback there.  A regular Plasma launch never sets
        # either backend and continues to use the shared Dolphin model.
        if os.environ.get('QT_QPA_PLATFORM', '').casefold() in {'offscreen', 'minimal'}:
            return None
        helper = self.places_helper()
        if not helper:
            return None
        try:
            result = subprocess.run([helper, 'list'], capture_output=True, text=True,
                                    timeout=8, check=False)
            payload = json.loads(result.stdout or '{}')
            if result.returncode == 0 and payload.get('ok') and isinstance(payload.get('places'), list):
                return payload['places']
        except (OSError, subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def change_place(self, operation: str, *arguments: str) -> tuple[bool, str]:
        helper = self.places_helper()
        if not helper:
            return False, 'KIO Places support is unavailable.'
        try:
            result = subprocess.run([helper, operation, *map(str, arguments)], capture_output=True,
                                    text=True, timeout=15, check=False)
            payload = json.loads(result.stdout or '{}')
            if result.returncode == 0 and payload.get('ok'):
                return True, ''
            return False, str(payload.get('error') or result.stderr.strip() or 'Unable to update Places.')
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            return False, str(error)

    def run_place_operation(self, operation: str, url: str, callback) -> bool:
        helper = self.places_helper()
        if not helper:
            return False
        process = QProcess()
        self._places_processes = getattr(self, '_places_processes', set())
        self._places_processes.add(process)
        process.finished.connect(lambda code, _status, proc=process: self._finish_place_setup(proc, code, callback))
        process.start(helper, [operation, str(url)])
        if not process.waitForStarted(1500):
            self._places_processes.discard(process)
            process.deleteLater()
            return False
        return True

    def setup_place(self, url: str, callback) -> bool:
        return self.run_place_operation('setup', url, callback)

    def _finish_place_setup(self, process, code, callback):
        self._places_processes.discard(process)
        try:
            payload = json.loads(bytes(process.readAllStandardOutput()).decode('utf-8') or '{}')
            ok = code == 0 and bool(payload.get('ok'))
            callback(ok, str(payload.get('error', '')))
        except (ValueError, AttributeError):
            callback(False, 'Unable to mount this device.')
        process.deleteLater()

    def reorder_places(self, urls: list[str]) -> tuple[bool, str]:
        return self.change_place('reorder', json.dumps(urls, ensure_ascii=False))

    def start_terminal(self, folder: Path) -> bool:
        """Use KDE's preferred terminal, as Dolphin's terminal actions do."""
        helper = self.tool_path('mirivue-kio-open')
        if not helper:
            return False
        result = QProcess.startDetached(helper, ['--terminal', str(folder)])
        return result[0] if isinstance(result, tuple) else bool(result)

    def run_in_konsole(self, path: Path) -> bool:
        """Run one executable in Konsole exactly like its KIO service menu."""
        path = Path(path)
        konsole = self.tool_path(tr('konsole'))
        if not konsole or not path.is_file():
            return False
        result = QProcess.startDetached(
            konsole,
            [tr('--hold'), tr('-e'), str(path)],
            str(path.parent),
        )
        return result[0] if isinstance(result, tuple) else bool(result)

    def run_executable(self, path: Path) -> bool:
        """Start a local executable directly, without involving a shell."""
        path = Path(path)
        if not path.is_file():
            return False
        result = QProcess.startDetached(str(path), [], str(path.parent))
        return result[0] if isinstance(result, tuple) else bool(result)

    def open_kio_location(self, location: str) -> bool:
        """Open a non-local URL through KDE's KIO service when available."""
        url = str(location)
        if self.name == tr('linux') and self.tool_path(tr('kioclient')):
            result = QProcess.startDetached(self.tool_path(tr('kioclient')), [tr('exec'), url])
            return result[0] if isinstance(result, tuple) else bool(result)
        if self.name == tr('linux'):
            helper = self.tool_path('mirivue-kio-open')
            if not helper:
                return False
            result = QProcess.startDetached(helper, [url])
            return result[0] if isinstance(result, tuple) else bool(result)
        return bool(QDesktopServices.openUrl(QUrl(url)))

    def open_default_file(self, path: Path) -> bool:
        """Use the KDE/KIO association resolver in every Linux session."""
        helper = self.tool_path('mirivue-kio-open') if self.name == tr('linux') else None
        if helper:
            result = QProcess.startDetached(helper, [str(path)])
            return result[0] if isinstance(result, tuple) else bool(result)
        if self.name == tr('linux'):
            return False
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))

    def list_kio_location(self, location: str) -> list[dict] | None:
        """Return a structured KIO directory listing when the native bridge is available."""
        tool = self.tool_path(tr('mirivue-kio-list'))
        if not tool or not str(location).strip():
            return None
        try:
            result = subprocess.run([tool, str(location)], check=False, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 or not result.stdout.strip():
                return None
            payload = json.loads(result.stdout.splitlines()[-1])
            return payload.get(tr('entries'), []) if payload.get(tr('ok')) else None
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None

    def _update_kio_undo_state(self, available, text):
        available = bool(available)
        text = str(text or '')
        if (available, text) == (self._kio_undo_available, self._kio_undo_text):
            return
        self._kio_undo_available, self._kio_undo_text = available, text
        self.kio_events.undo_state_changed.emit(available, text)

    def _update_kio_redo_state(self, available, text):
        available = bool(available)
        text = str(text or '')
        if (available, text) == (self._kio_redo_available, self._kio_redo_text):
            return
        self._kio_redo_available, self._kio_redo_text = available, text
        self.kio_events.redo_state_changed.emit(available, text)

    def _start_kio_service(self):
        if self._kio_process is not None and self._kio_process.poll() is None:
            return self._kio_process
        helper = self.tool_path(tr('mirivue-kio-service'))
        if not helper:
            return None
        suffix = f"{os.getuid()}-{uuid.uuid4().hex[:12]}"
        self._kio_input_path = f"/tmp/mirivue-kio-{suffix}.in"
        self._kio_output_path = f"/tmp/mirivue-kio-{suffix}.out"
        os.mkfifo(self._kio_input_path, 0o600)
        os.mkfifo(self._kio_output_path, 0o600)
        self._kio_input_fd = os.open(self._kio_input_path, os.O_RDWR | os.O_NONBLOCK)
        self._kio_output_fd = os.open(self._kio_output_path, os.O_RDWR | os.O_NONBLOCK)
        self._kio_process = subprocess.Popen(
            [helper, '--service', self._kio_input_path, self._kio_output_path], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.05)
        if self._kio_process.poll() is not None:
            self._close_kio_service()
            return None
        return self._kio_process

    def _close_kio_service(self):
        if self._kio_input_fd is not None:
            os.close(self._kio_input_fd)
            self._kio_input_fd = None
        if self._kio_output_fd is not None:
            os.close(self._kio_output_fd)
            self._kio_output_fd = None
        for path in (self._kio_input_path, self._kio_output_path):
            if path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
        self._kio_input_path = self._kio_output_path = None
        self._kio_process = None

    def _write_kio_service(self, payload):
        data = memoryview((json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8'))
        while data:
            try:
                count = os.write(self._kio_input_fd, data)
                data = data[count:]
            except BlockingIOError:
                select.select([], [self._kio_input_fd], [], 2)

    def _kio_service_request(self, command, *, sources=(), destination='', progress=None, cancelled=None, timeout=300):
        """Send one request to the session-scoped KIO service."""
        if cancelled is not None and cancelled():
            return False, tr('Transfert annulé.')
        with _kio_turn(self._kio_lock, cancelled) as acquired:
            # A cancelled request may have been waiting behind another job.
            # Never start it after that other operation releases the service.
            if not acquired or (cancelled is not None and cancelled()):
                return False, tr('Transfert annulé.')
            try:
                process = self._start_kio_service()
            except OSError as error:
                self._close_kio_service()
                return False, str(error)
            if process is None:
                return False, tr('Service de transfert de fichiers indisponible.')
            request_id = uuid.uuid4().hex
            payload = {'command': command, 'id': request_id}
            if sources:
                payload['sources'] = [str(value) for value in sources]
            if destination:
                payload['destination'] = str(destination)
            try:
                self._write_kio_service(payload)
                selector = selectors.DefaultSelector()
                selector.register(self._kio_output_fd, selectors.EVENT_READ)
                started = time.monotonic()
                cancel_sent = False
                cancel_started = None
                buffer = bytearray()
                try:
                    while True:
                        if cancelled is not None and cancelled() and not cancel_sent:
                            cancel_payload = {'command': 'cancel', 'id': uuid.uuid4().hex, 'target': request_id}
                            self._write_kio_service(cancel_payload)
                            cancel_sent = True
                            cancel_started = time.monotonic()
                        if not cancel_sent and timeout is not None and time.monotonic() - started > timeout:
                            cancel_payload = {'command': 'cancel', 'id': uuid.uuid4().hex, 'target': request_id}
                            self._write_kio_service(cancel_payload)
                            cancel_sent = True
                            cancel_started = time.monotonic()
                        if cancel_started is not None and time.monotonic() - cancel_started > 5:
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                            self._close_kio_service()
                            return False, tr('Le transfert de fichiers ne répond pas après l’annulation.')

                        complete = None
                        while b'\n' in buffer:
                            line, _, rest = buffer.partition(b'\n')
                            buffer[:] = rest
                            try:
                                event = json.loads(line)
                            except (UnicodeDecodeError, ValueError):
                                continue
                            if event.get('event') == 'state':
                                self._update_kio_undo_state(event.get('undo_available'), event.get('undo_text'))
                                self._update_kio_redo_state(event.get('redo_available'), event.get('redo_text'))
                            elif event.get('event') == 'progress' and event.get('id') == request_id:
                                if progress is not None:
                                    progress(int(event.get('value', 0)))
                            elif event.get('event') == 'complete' and event.get('id') == request_id:
                                complete = event
                        if complete is not None:
                            if 'undo_available' in complete:
                                self._update_kio_undo_state(complete.get('undo_available'), complete.get('undo_text'))
                            if 'redo_available' in complete:
                                self._update_kio_redo_state(complete.get('redo_available'), complete.get('redo_text'))
                            if cancel_sent or complete.get('cancelled'):
                                return False, tr('Transfert annulé.')
                            return bool(complete.get('ok')), str(complete.get('error') or '')

                        if process.poll() is not None:
                            self._close_kio_service()
                            return False, tr('Le transfert de fichiers s’est arrêté de façon inattendue.')
                        if selector.select(timeout=0.05):
                            chunk = os.read(self._kio_output_fd, 65536)
                            if not chunk:
                                if process.poll() is not None:
                                    self._close_kio_service()
                                    return False, tr('Le transfert de fichiers s’est arrêté de façon inattendue.')
                                continue
                            buffer.extend(chunk)
                finally:
                    selector.close()
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                self._close_kio_service()
                return False, str(error)

    def undo_kio(self):
        if not self._kio_undo_available:
            return False, tr('Aucune opération distante à annuler.')
        return self._kio_service_request('undo', timeout=3600)

    def redo_kio(self):
        if not self._kio_redo_available:
            return False, tr('Aucune opération de fichiers à rétablir.')
        return self._kio_service_request('redo', timeout=3600)

    def shutdown_kio_service(self):
        if self._kio_process is None or self._kio_process.poll() is not None:
            self._close_kio_service()
            return
        self._kio_service_request('shutdown', timeout=5)
        process = self._kio_process
        if process is not None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)
        self._close_kio_service()

    def create_directory(self, parent: str, name: str, require_undo: bool = False) -> tuple[bool, str]:
        """Create a child directory locally or through the native KIO bridge."""
        location = QUrl(str(parent))
        if location.isValid() and location.scheme() and location.scheme() != tr('file'):
            target = QUrl(location)
            target.setPath(target.path().rstrip(tr('/')) + tr('/') + name)
            if self.tool_path(tr('mirivue-kio-service')):
                result = self._kio_service_request(tr('mkdir'), destination=target.toString(), timeout=60)
                if result[0] or result[1] != tr('Service de transfert de fichiers indisponible.'):
                    return result
            helper = self.tool_path(tr('mirivue-kio-transfer'))
            tool = helper or (self.tool_path(tr('kioclient')) if self.is_plasma else None)
            if not tool:
                return False, tr('La création de dossiers à cet emplacement n’est pas disponible.')
            try:
                arguments = [tr('mkdir'), target.toString()]
                result = subprocess.run([tool, *arguments], check=False, capture_output=True, text=True, timeout=60)
                if helper:
                    payload = json.loads(result.stdout.splitlines()[-1]) if result.stdout.strip() else {}
                    if result.returncode == 0 and payload.get(tr('ok')):
                        return True, tr('')
                    return False, str(payload.get(tr('error')) or result.stderr or result.stdout).strip() or tr('Le dossier n’a pas pu être créé.')
                if result.returncode == 0:
                    return True, tr('')
                return False, (result.stderr or result.stdout).strip() or tr('Le dossier n’a pas pu être créé.')
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                return False, str(error)
        # Record local folder creation in KIO's own undo history as Dolphin
        # does. Keep the direct mkdir fallback for installations without the
        # native KIO bridge.
        helper = self.tool_path(tr('mirivue-kio-service'))
        if helper:
            target = QUrl.fromLocalFile(str((Path(parent) / name).absolute()))
            result = self._kio_service_request(tr('mkdir'), destination=target.toString(), timeout=60)
            if result[0] or result[1] != tr('Service de transfert de fichiers indisponible.'):
                return result
        if require_undo:
            return False, tr('Le service KIO nécessaire à une création annulable est indisponible.')
        try:
            (Path(parent) / name).mkdir()
            return True, tr('')
        except OSError as error:
            return False, str(error)

    def transfer_kio(self, sources: list[str], destination: str, move: bool = False, progress=None, cancelled=None, operation=None) -> tuple[bool, str]:
        command = operation or (tr('move') if move else tr('copy'))
        # Extraction is a copy from a KIO archive URL.  Keep its distinct
        # user-facing label in Mirivue while sending the native copy command
        # understood by the KIO service and compatibility helper.
        if command == tr('extract'):
            command = tr('copy')
        if command not in (tr('copy'), tr('move'), tr('copyas'), tr('moveas'), tr('link'), tr('trash'), tr('restore'), tr('delete')):
            return False, tr('Opération de fichiers inconnue.')
        if self.tool_path(tr('mirivue-kio-service')):
            result = self._kio_service_request(command, sources=sources,
                                               destination=destination, progress=progress,
                                               cancelled=cancelled, timeout=None)
            if result[0] or result[1] != tr('Service de transfert de fichiers indisponible.'):
                return result
        if command in (tr('copyas'), tr('moveas')):
            return False, tr('Service KIO nécessaire au transfert avec nom imposé indisponible.')
        if command in (tr('restore'), tr('delete')):
            return False, tr('Service de transfert de fichiers indisponible.')
        tool = self.tool_path(tr('mirivue-kio-transfer'))
        if not tool or not sources or not destination:
            return False, tr('Service de transfert de fichiers indisponible.')
        process = None
        selector = None
        try:
            arguments = [tool, command, *map(str, sources)]
            if command != tr('trash'):
                arguments.append(str(destination))
            process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
            selector = selectors.DefaultSelector()
            output = {process.stdout: bytearray(), process.stderr: bytearray()}
            for stream in output:
                selector.register(stream, selectors.EVENT_READ)
            payload = {}
            stderr_tail = bytearray()
            started = time.monotonic()
            while selector.get_map() or process.poll() is None:
                if cancelled is not None and cancelled():
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    return False, tr('Transfert annulé.')
                if time.monotonic() - started > 300:
                    process.kill()
                    process.wait()
                    return False, tr('Le transfert de fichiers a dépassé le délai maximal.')
                for key, _mask in selector.select(timeout=0.05):
                    stream = key.fileobj
                    chunk = os.read(stream.fileno(), 65536)
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    if stream is process.stderr:
                        stderr_tail.extend(chunk)
                        if len(stderr_tail) > 16384:
                            del stderr_tail[:-16384]
                        continue
                    buffer = output[stream]
                    buffer.extend(chunk)
                    while b'\n' in buffer:
                        line, _, remainder = buffer.partition(b'\n')
                        buffer[:] = remainder
                        try:
                            item = json.loads(line)
                        except (UnicodeDecodeError, ValueError):
                            continue
                        if 'progress' in item:
                            if progress is not None:
                                progress(int(item['progress']))
                        else:
                            payload = item
            for line in output[process.stdout].splitlines():
                try:
                    item = json.loads(line)
                except (UnicodeDecodeError, ValueError):
                    continue
                if 'progress' in item:
                    if progress is not None:
                        progress(int(item['progress']))
                else:
                    payload = item
            ok = bool(process.returncode == 0 and payload.get(tr('ok')))
            error = str(payload.get(tr('error'), ''))
            if not ok and not error:
                error = stderr_tail.decode(errors='replace').strip()
            if not ok:
                record_tool_failure(tr('KIO'), error or tr('échec sans détail'))
            return ok, error
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            record_tool_failure(tr('KIO'), error)
            return False, str(error)
        finally:
            if selector is not None:
                selector.close()

    def notify(self, title: str, message: str, urgent: bool = False) -> bool:
        """Send a desktop notification without coupling the core to Plasma APIs."""
        tool = self.tool_path(tr('notify-send'))
        if not tool:
            return False
        arguments = ['--app-name=Mirivue']
        if urgent:
            arguments += [tr('--urgency=critical')]
        arguments += [str(title), str(message)]
        result = QProcess.startDetached(tool, arguments)
        return result[0] if isinstance(result, tuple) else bool(result)

    def rename_no_replace(self, source: Path, target: Path) -> None:
        tr('Atomically publish a same-volume rename without replacing a target.')
        source, target = (Path(source), Path(target))
        if self.name == tr('windows'):
            import ctypes
            if not ctypes.windll.kernel32.MoveFileExW(str(source), str(target), 0):
                code = ctypes.get_last_error()
                raise OSError(code, ctypes.FormatError(code), str(target))
            return
        if self.name == tr('macos'):
            import ctypes
            library = ctypes.CDLL(tr('/usr/lib/libSystem.B.dylib'), use_errno=True)
            rename = getattr(library, tr('renamex_np'), None)
            if rename is None:
                raise OSError(errno.ENOTSUP, tr('Renommage sécurisé indisponible sur ce système.'), str(target))
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            if rename(os.fsencode(source), os.fsencode(target), 4):
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code), str(target))
            return
        import ctypes
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, tr('renameat2'), None)
        if rename is None:
            raise OSError(errno.ENOTSUP, tr('Renommage sécurisé indisponible sur ce système.'), str(target))
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(target))

    def shortcut(self, sequence: str) -> str:
        tr('Translate the familiar Ctrl notation to Command on macOS.')
        return sequence.replace(tr('Ctrl+'), tr('Meta+')) if self.name == tr('macos') else sequence

    def validate_portable_name(self, name: str) -> str | None:
        """Check native filename rules; the destination filesystem has final say."""
        if not name or name in (tr('.'), tr('..')):
            return tr('Choisissez un nom non vide.')
        if self.name != tr('windows'):
            if tr('/') in name or '\x00' in name:
                return tr('Ce nom contient un séparateur de chemin ou un caractère nul.')
            return None
        if name.strip() != name:
            return tr('Choisissez un nom sans espace au début ou à la fin.')
        if any((character in name for character in tr('<>:"/\\|?*\x00'))):
            return tr('Ce nom contient un caractère incompatible avec Windows.')
        if name.endswith((tr(' '), tr('.'))):
            return tr('Un nom ne peut pas se terminer par un espace ou un point.')
        stem = name.split(tr('.'), 1)[0].upper()
        if stem in {tr('CON'), tr('PRN'), tr('AUX'), tr('NUL')} or stem in {trf('COM\x1f0\x1f', i) for i in range(1, 10)} | {trf('LPT\x1f0\x1f', i) for i in range(1, 10)}:
            return tr('Ce nom est réservé par Windows.')
        return None
services = PlatformServices()
