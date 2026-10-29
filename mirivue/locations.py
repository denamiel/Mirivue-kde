"""Unified local-path and URI locations used by the file backends."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse
from PySide6.QtCore import QUrl

ARCHIVE_PROTOCOLS = frozenset({'zip', 'tar', 'sevenz', 'ar'})
ARCHIVE_SUFFIXES = (
    '.tar.gz', '.tar.bz2', '.tar.xz', '.tar.zst', '.tbz2',
    '.tgz', '.tbz', '.txz', '.tzst', '.zip', '.7z', '.rar', '.tar',
    '.rpm', '.deb', '.ar',
)

def archive_protocol(path: str | Path) -> str | None:
    """Return the KIO Archive protocol for common archive file types."""
    name = str(path).casefold()
    if name.endswith('.zip'):
        return 'zip'
    if name.endswith('.7z'):
        return 'sevenz'
    if name.endswith('.rar'):
        return 'rar'
    if name.endswith(('.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz', '.tbz2', '.tar.xz', '.txz', '.tar.zst', '.tzst')):
        return 'tar'
    if name.endswith(('.ar', '.deb', '.rpm')):
        return 'ar'
    return None

def archive_url(path: str | Path) -> str | None:
    protocol = archive_protocol(path)
    if not protocol or protocol == 'rar':
        return None
    url = QUrl()
    url.setScheme(protocol)
    url.setPath(str(Path(path).expanduser().resolve()))
    return url.toString()

def archive_subfolder_name(path: str | Path) -> str:
    """Return Ark's automatic subfolder name without the archive suffix."""
    name = Path(path).name
    lower = name.casefold()
    suffix = next((value for value in ARCHIVE_SUFFIXES if lower.endswith(value)), '')
    trimmed = name[:-len(suffix)] if suffix else Path(name).stem
    return trimmed or Path(name).stem or name

def archive_source_path(value: str | Path) -> Path | None:
    """Get the backing local archive file from a KIO archive URL."""
    location = Location.from_value(value)
    if not location.is_uri:
        return None
    url = QUrl(location.value)
    if url.scheme().casefold() not in ARCHIVE_PROTOCOLS:
        return None
    parts = [part for part in url.path().split('/') if part]
    for index, part in enumerate(parts):
        if archive_protocol(part):
            return Path('/' + '/'.join(parts[:index + 1]))
    return None

def parent_location(value: str | Path) -> str:
    """Return the parent URL/path, including the host folder above an archive."""
    location = Location.from_value(value)
    if not location.is_uri:
        return str(Path(value).parent)
    url = QUrl(location.value)
    protocol = url.scheme().casefold()
    path = url.path().rstrip('/')
    if protocol in ARCHIVE_PROTOCOLS:
        parts = path.split('/')
        archive_end = next((i for i, part in enumerate(parts) if archive_protocol(part)), None)
        if archive_end is not None:
            if archive_end < len(parts) - 1:
                url.setPath('/'.join(parts[:]) .rsplit('/', 1)[0] or '/')
                return url.toString()
            archive_path = '/'.join(parts[:archive_end + 1])
            return Path(archive_path).parent.as_uri()
    url.setPath(path.rsplit('/', 1)[0] or '/')
    return url.toString()


@dataclass(frozen=True)
class Location:
    """A filesystem path or a desktop URI.

    Local locations keep a :class:`Path` for compatibility with the existing
    media and file workers. URI locations remain textual until the KIO backend
    resolves them, so they are never accidentally passed to ``os.path``.
    """

    value: str

    @property
    def is_uri(self) -> bool:
        parsed = urlparse(self.value)
        return bool(parsed.scheme and (parsed.scheme != "file" or self.value.startswith("file://")))

    @property
    def path(self) -> Path | None:
        if self.is_uri:
            return None
        if self.value.startswith("file://"):
            parsed = urlparse(self.value)
            return Path(unquote(parsed.path))
        return Path(self.value).expanduser()

    @property
    def uri(self) -> str:
        if self.is_uri:
            return self.value
        return self.path.resolve().as_uri()

    @classmethod
    def from_value(cls, value: str | Path | Location) -> "Location":
        if isinstance(value, cls):
            return value
        return cls(str(value))

    def __str__(self) -> str:
        return self.value


def is_uri(value: str | Path | Location) -> bool:
    return Location.from_value(value).is_uri
