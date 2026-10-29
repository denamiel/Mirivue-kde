"""Local diagnostics, bounded logs, and abnormal-session detection."""

from __future__ import annotations

import importlib.util
from importlib import metadata as package_metadata
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import traceback


LOGGER_NAME = "mirivue"
MAX_LOG_BYTES = 1024 * 1024
LOG_BACKUPS = 3
_session_marker: Path | None = None


def state_directory() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "mirivue"


def log_path() -> Path:
    return state_directory() / "mirivue.log"


def _logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def configure_logging(version: str) -> Path:
    """Configure one local rotating log and exception hooks.

    Logging must never prevent Mirivue from starting. No handler transmits data.
    """
    path = log_path()
    logger = _logger()
    if logger.handlers:
        return path
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        handler = RotatingFileHandler(
            path, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUPS,
            encoding="utf-8", delay=True,
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(threadName)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
    except (OSError, ValueError):
        logger.addHandler(logging.NullHandler())
    logger.info("Démarrage de Mirivue %s", version)
    _install_exception_hooks()
    return path


def _install_exception_hooks() -> None:
    previous = sys.excepthook

    def unhandled(kind, value, trace):
        if issubclass(kind, KeyboardInterrupt):
            previous(kind, value, trace)
            return
        _logger().critical("Exception non gérée", exc_info=(kind, value, trace))
        _show_exception_dialog(kind, value, trace)
        previous(kind, value, trace)

    sys.excepthook = unhandled

    if hasattr(threading, "excepthook"):
        previous_thread = threading.excepthook

        def unhandled_thread(arguments):
            _logger().critical(
                "Exception non gérée dans une tâche Python",
                exc_info=(arguments.exc_type, arguments.exc_value, arguments.exc_traceback),
            )
            previous_thread(arguments)

        threading.excepthook = unhandled_thread

    if hasattr(sys, "unraisablehook"):
        previous_unraisable = sys.unraisablehook

        def unraisable(arguments):
            _logger().error(
                "Exception différée non gérée: %s", arguments.err_msg or arguments.object,
                exc_info=(arguments.exc_type, arguments.exc_value, arguments.exc_traceback),
            )
            previous_unraisable(arguments)

        sys.unraisablehook = unraisable


def _show_exception_dialog(kind, value, trace) -> None:
    """Show a recoverable GUI report only for an exception on Qt's main thread."""
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication, QMessageBox
        application = QApplication.instance()
        if application is None or QThread.currentThread() is not application.thread():
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Erreur inattendue")
        box.setText("Mirivue a rencontré une erreur inattendue. Le journal local a été mis à jour.")
        box.setInformativeText("Vous pouvez copier le diagnostic avant de poursuivre ou de fermer Mirivue.")
        details = "".join(traceback.format_exception(kind, value, trace))
        box.setDetailedText(details)
        copy_button = box.addButton("Copier le diagnostic", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is copy_button:
            QApplication.clipboard().setText(diagnostic_report() + "\n\nErreur récente :\n" + details)
    except Exception:
        _logger().exception("Impossible d’afficher la fenêtre d’incident")


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def begin_session() -> bool:
    """Create a PID marker and report whether an earlier process ended abruptly."""
    global _session_marker
    folder = state_directory()
    marker = folder / f"session-{os.getpid()}.json"
    previous_unclean = False
    try:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for old_marker in folder.glob("session-*.json"):
            if old_marker == marker:
                continue
            try:
                previous_pid = int(json.loads(old_marker.read_text(encoding="utf-8")).get("pid", 0))
                stale = not _pid_is_running(previous_pid)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                stale = True
            if stale:
                previous_unclean = True
                try:
                    old_marker.unlink()
                except OSError:
                    pass
        marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        os.chmod(marker, 0o600)
        _session_marker = marker
    except OSError:
        _logger().exception("Impossible de créer le marqueur de session")
    if previous_unclean:
        _logger().warning("Le lancement précédent ne s’est pas terminé normalement")
    return previous_unclean


def end_session() -> None:
    global _session_marker
    try:
        if _session_marker and _session_marker.is_file():
            payload = json.loads(_session_marker.read_text(encoding="utf-8"))
            if int(payload.get("pid", 0)) == os.getpid():
                _session_marker.unlink()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _logger().exception("Impossible de supprimer le marqueur de session")
    _session_marker = None
    _logger().info("Arrêt normal de Mirivue")


def record_tool_failure(tool: str, detail: object) -> None:
    """Record a bounded backend failure without exposing it outside the computer."""
    message = str(detail or "échec sans détail").replace("\x00", "")
    _logger().error("Échec de %s: %s", Path(str(tool)).name, message[:4000])


def _command_version(command: str) -> str:
    executable = shutil.which(command)
    if not executable:
        return "absent"
    if command in {"ffmpeg", "ffprobe"}:
        arguments = [executable, "-version"]
    elif command == "exiftool":
        arguments = [executable, "-ver"]
    elif command in {"7z", "7zz", "unrar"}:
        # These tools print their version banner when invoked without an
        # archive.  GNU-style --version is rejected and produced a misleading
        # diagnostic even though the executable was healthy.
        arguments = [executable]
    elif command == "unar":
        arguments = [executable, "-v"]
    else:
        arguments = [executable, "--version"]
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=3, check=False)
        lines = [line.strip() for line in (result.stdout or result.stderr).splitlines() if line.strip()]
        if command == "mediainfo" and len(lines) > 1:
            return " / ".join(lines[:2])[:180]
        return lines[0][:180] if lines else f"présent ({executable})"
    except (OSError, subprocess.TimeoutExpired):
        return f"présent ({executable})"


def _module_state(module: str) -> str:
    try:
        if importlib.util.find_spec(module) is None:
            return "absent"
        distribution = {
            "PIL": "Pillow",
            "mutagen": "mutagen",
            "shiboken6": "shiboken6",
        }.get(module, "PySide6" if module.startswith("PySide6") else module.split(".", 1)[0])
        try:
            return f"disponible ({package_metadata.version(distribution)})"
        except package_metadata.PackageNotFoundError:
            return "disponible"
    except (ImportError, ValueError):
        return "absent"


def _os_description() -> str:
    try:
        values = {}
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip().strip('"')
        return values.get("PRETTY_NAME") or platform.platform()
    except OSError:
        return platform.platform()


def _kio_state() -> str:
    helper = Path(__file__).resolve().parent.parent / "tools" / "mirivue-kio-service"
    if not helper.is_file() or not os.access(helper, os.X_OK):
        return "utilitaire Mirivue absent"
    try:
        result = subprocess.run(["ldd", str(helper)], capture_output=True, text=True, timeout=3, check=False)
        missing = [line.strip().split()[0] for line in result.stdout.splitlines() if "not found" in line]
        return "disponible" if result.returncode == 0 and not missing else "bibliothèques absentes : " + ", ".join(missing)
    except (OSError, subprocess.TimeoutExpired):
        return "contrôle indisponible"


def diagnostic_report(version: str | None = None) -> str:
    if version is None:
        try:
            from . import __version__ as version
        except ImportError:
            version = "inconnue"
    modules = ["PySide6.QtWidgets", "PySide6.QtDBus", "PySide6.QtMultimedia",
               "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PIL", "mutagen", "shiboken6"]
    tools = ["ffmpeg", "ffprobe", "mediainfo", "ark", "exiftool", "mkvpropedit", "mkvextract"]
    lines = [
        "Diagnostic Mirivue KDE",
        f"Version Mirivue : {version}",
        f"Système : {_os_description()}",
        f"Python : {platform.python_version()}",
        f"Session : {os.environ.get('XDG_SESSION_TYPE', 'inconnue')} / {os.environ.get('XDG_CURRENT_DESKTOP', 'inconnu')}",
        "",
        "Modules Python :",
    ]
    lines.extend(f"- {module} : {_module_state(module)}" for module in modules)
    lines.extend(("", "Outils externes :"))
    lines.extend(f"- {tool} : {_command_version(tool)}" for tool in tools)
    seven_zip = "7z" if shutil.which("7z") else "7zz" if shutil.which("7zz") else None
    rar_reader = "unar" if shutil.which("unar") else "unrar" if shutil.which("unrar") else None
    lines.append(f"- 7z/7zz : {_command_version(seven_zip) if seven_zip else 'absent'}")
    lines.append(f"- unar/unrar : {_command_version(rar_reader) if rar_reader else 'absent'}")
    lines.append(f"- KIO/KF6 : {_kio_state()}")
    lines.extend(("", f"Journal local : {log_path()}", "Télémétrie : désactivée (aucune transmission automatique)"))
    return "\n".join(lines)
