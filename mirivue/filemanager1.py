"""Freedesktop FileManager1 integration used by browsers and desktop apps."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

from PySide6.QtCore import QObject, Slot

from .launch_targets import parse_launch_arguments, parse_show_items, parse_launch_requests


SERVICE_NAME = 'org.freedesktop.FileManager1'
OBJECT_PATH = '/org/freedesktop/FileManager1'
INTERFACE_NAME = 'org.freedesktop.FileManager1'
DESKTOP_ID = 'org.pdenams.Mirivue.Qt.desktop'
ACTIVATION_MARKER = '# Managed by Mirivue KDE'


def plasma_session() -> bool:
    """Use the current desktop, not the MIME default shared between sessions."""
    desktop = os.environ.get('XDG_CURRENT_DESKTOP') or os.environ.get('XDG_SESSION_DESKTOP', '')
    names = {part.casefold() for part in desktop.split(':') if part}
    if names & {'gnome', 'gnome-classic', 'cinnamon'}:
        return False
    return bool(names & {'kde', 'plasma', 'plasmawayland', 'plasmax11'})


def activation_file_path() -> Path:
    data_home = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    return data_home / 'dbus-1' / 'services' / 'org.freedesktop.FileManager1.service'


def installed_launcher() -> str:
    system = Path('/usr/bin/mirivue-kde')
    if system.exists():
        return str(system)
    bundled = Path(__file__).resolve().parent.parent / 'Lancer.sh'
    return str(bundled)


def default_file_manager() -> str:
    try:
        result = subprocess.run(
            ['xdg-mime', 'query', 'default', 'inode/directory'],
            capture_output=True, text=True, timeout=2, check=False,
        )
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ''


def activation_contents(launcher: str) -> str:
    # D-Bus activation Exec fields accept a program followed by arguments.
    # Mirivue's supported installation paths do not contain newlines.
    escaped = str(launcher).replace('\\', '\\\\').replace(' ', '\\ ')
    return (
        f'{ACTIVATION_MARKER}\n'
        '[D-BUS Service]\n'
        f'Name={SERVICE_NAME}\n'
        # Lancer.sh dispatches at activation time: the same user can log into
        # GNOME later without leaving Mirivue in front of Nautilus.
        f'Exec={escaped} --file-manager-service\n'
    )


def ensure_user_activation() -> bool:
    """Upgrade an owned activation in any session; claim it only in Plasma."""
    target = activation_file_path()
    plasma = plasma_session()
    if plasma and default_file_manager() != DESKTOP_ID:
        try:
            if target.is_file() and ACTIVATION_MARKER in target.read_text(
                    encoding='utf-8', errors='replace'):
                target.unlink()
        except OSError:
            pass
        return False

    if not plasma:
        # RC93 could have written a service pointing at an older user launcher.
        # Replace only our existing file so the next activation delegates to
        # Nautilus in GNOME, even before Mirivue is started there.
        try:
            if not target.is_file() or ACTIVATION_MARKER not in target.read_text(
                    encoding='utf-8', errors='replace'):
                return False
        except OSError:
            return False

    content = activation_contents(installed_launcher())
    try:
        if target.is_file() and target.read_text(encoding='utf-8') == content:
            return plasma
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                'w', encoding='utf-8', dir=target.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        temporary.chmod(0o644)
        temporary.replace(target)
        return plasma
    except OSError:
        return False


class FileManager1(QObject):
    """Implementation of the standard browser-facing file-manager methods."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def _show(self, uri_list, properties=False, folders_only=False, startup_id=''):
        values = [str(value) for value in uri_list if str(value).strip()]
        requests = parse_launch_requests(values, show_items=not folders_only)
        if not requests:
            return
        self.window.open_external_locations(requests, properties=properties, activation_token=startup_id)

    @Slot('QStringList', str)
    def ShowItems(self, uri_list, startup_id):
        self._show(uri_list, startup_id=startup_id)

    @Slot('QStringList', str)
    def ShowFolders(self, uri_list, startup_id):
        self._show(uri_list, folders_only=True, startup_id=startup_id)

    @Slot('QStringList', str)
    def ShowItemProperties(self, uri_list, startup_id):
        self._show(uri_list, properties=True, startup_id=startup_id)


def register_file_manager_service(application, window) -> bool:
    """Own FileManager1 when Mirivue is the selected default file manager."""
    if not plasma_session() or not ensure_user_activation():
        return False
    try:
        from PySide6.QtDBus import QDBusConnection
    except ImportError:
        return False
    bus = QDBusConnection.sessionBus()
    service = FileManager1(window)
    options = QDBusConnection.RegisterOption.ExportAllSlots
    if not bus.registerObject(OBJECT_PATH, INTERFACE_NAME, service, options):
        return False
    if not bus.registerService(SERVICE_NAME):
        bus.unregisterObject(OBJECT_PATH)
        return False
    application._mirivue_filemanager1 = service
    application._mirivue_filemanager1_bus = bus
    return True
