"""Resolve local folder icons with the same KDE conventions as Dolphin."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon


def standard_folder_icons() -> dict[Path, str]:
    """Map the XDG user directories to their semantic Breeze icon names."""
    standard = QStandardPaths.StandardLocation
    locations = (
        (standard.HomeLocation, 'user-home'),
        (standard.DesktopLocation, 'user-desktop'),
        (standard.DownloadLocation, 'folder-download'),
        (standard.DocumentsLocation, 'folder-documents'),
        (standard.MoviesLocation, 'folder-videos'),
        (standard.PicturesLocation, 'folder-pictures'),
        (standard.MusicLocation, 'folder-music'),
        (standard.TemplatesLocation, 'folder-templates'),
        (standard.PublicShareLocation, 'folder-publicshare'),
    )
    result = {}
    for location, icon_name in locations:
        value = QStandardPaths.writableLocation(location)
        if value:
            result[Path(value).expanduser().absolute()] = icon_name
    return result


def directory_icon_name(path: Path) -> str:
    """Read the KDE ``Icon`` key without interpreting arbitrary config data."""
    metadata = path / '.directory'
    try:
        if not metadata.is_file() or metadata.stat().st_size > 64 * 1024:
            return ''
        in_desktop_entry = False
        for raw_line in metadata.read_text(encoding='utf-8', errors='replace').splitlines():
            line = raw_line.strip()
            if line.startswith('[') and line.endswith(']'):
                in_desktop_entry = line.casefold() == '[desktop entry]'
            elif in_desktop_entry and line.startswith('Icon='):
                return line.partition('=')[2].strip()
    except OSError:
        pass
    return ''


def themed_folder_icon(path, standard_icons: dict[Path, str] | None = None) -> QIcon:
    """Return a custom, XDG-semantic, or generic icon for a local directory."""
    folder = Path(path).expanduser().absolute()
    custom = directory_icon_name(folder)
    if custom:
        custom_path = Path(custom).expanduser()
        icon = QIcon(str(custom_path)) if custom_path.is_absolute() else QIcon.fromTheme(custom)
        if not icon.isNull():
            return icon
    icon_name = (standard_icons or standard_folder_icons()).get(folder, 'folder')
    return QIcon.fromTheme(icon_name)
