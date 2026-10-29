"""Hidden-file facts, resolved on inventory/update rather than while painting.

KIO's KCoreDirLister supplements KFileItem::isHidden with exact names read from
the local .hidden file. The local media inventory uses the same QTextStream
line semantics; KIO listings transport the lister's own boolean unchanged.
"""
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QFile, QIODevice, QTextStream, QUrl


@lru_cache(maxsize=64)
def _read_hidden_names(filename, signature):
    stream_file = QFile(filename)
    if not stream_file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        return frozenset()
    try:
        stream = QTextStream(stream_file)
        names = set()
        while not stream.atEnd():
            name = stream.readLine()
            if name:
                names.add(name)
        return frozenset(names)
    finally:
        stream_file.close()


def hidden_names(folder):
    """Bound the cache and invalidate it after a .hidden edit or replacement."""
    filename = Path(folder) / '.hidden'
    try:
        info = filename.stat()
    except OSError:
        return frozenset()
    signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return _read_hidden_names(str(filename), signature)


def local_is_hidden(path, names=None):
    path = Path(path)
    return (len(path.name) > 1 and path.name.startswith('.')) or path.name in (
        hidden_names(path.parent) if names is None else names)


def kio_is_hidden(item):
    """An explicit UDS/lister status takes precedence over the display label."""
    if 'hidden' in item:
        return bool(item['hidden'])
    name = QUrl(str(item.get('url', ''))).fileName() or str(item.get('name', ''))
    return len(name) > 1 and name.startswith('.')
