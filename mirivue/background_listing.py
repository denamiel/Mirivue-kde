"""Background directory search, media row discovery, and folder size tasks."""
import os
import fnmatch
import codecs
from collections import deque
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from .i18n import tr
from .metadata import EXTENSIONS, basic_entry, update_modification
from .file_visibility import hidden_names, local_is_hidden, kio_is_hidden

class RecursiveSearchWorker(QThread):
    """Search names below one local folder without blocking the interface."""
    listed = Signal(object)
    progress = Signal(int, int, str)
    notice = Signal(str)

    def __init__(self, folder, query, recursive=True, show_hidden=False, kind='all', content=False):
        super().__init__()
        self.folder = Path(folder)
        self.query = str(query).casefold().strip()
        self.recursive = bool(recursive)
        self.show_hidden = bool(show_hidden)
        self.kind = str(kind or 'all')
        self.content = bool(content)
        self.cancelled = False
        self.scanned = 0
        self.found = 0

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

    def accepts(self, path, is_dir):
        if self.query:
            name = path.name.casefold()
            name_matches = (fnmatch.fnmatchcase(name, self.query) if any(c in self.query for c in '*?[')
                            else self.query in name)
            if self.content:
                if is_dir or not self.content_matches(path):
                    return False
            elif not name_matches:
                return False
        if self.kind == 'folders':
            return is_dir
        if self.kind == 'files':
            return not is_dir
        if is_dir:
            return self.kind == 'all'
        if self.kind == 'all':
            return True
        from .media import expected_kind
        media_kind = expected_kind(path)
        if self.kind in ('video', 'audio', 'image'):
            return media_kind == tr(self.kind)
        return self.kind == 'other' and media_kind == tr('other')

    def content_matches(self, path):
        """Search bounded, readable local files without loading them into memory."""
        try:
            if path.stat().st_size > 16 * 1024 * 1024:
                return False
            needle = self.query
            decoder = codecs.getincrementaldecoder('utf-8')('strict')
            with path.open('rb') as stream:
                previous = ''
                while not self.isInterruptionRequested():
                    chunk = stream.read(65536)
                    if not chunk:
                        break
                    if b'\0' in chunk:
                        return False
                    data = previous + decoder.decode(chunk).casefold()
                    if needle in data:
                        return True
                    previous = data[-(len(needle) - 1):] if len(needle) > 1 else ''
        except (OSError, UnicodeError):
            return False
        return False

    def run(self):
        batch = []

        def send():
            nonlocal batch
            if batch:
                self.listed.emit(batch)
                batch = []

        def walk_error(error):
            self.notice.emit(str(error))

        try:
            for root, dirs, files in os.walk(self.folder, onerror=walk_error, followlinks=False):
                if self.isInterruptionRequested():
                    return
                hidden = hidden_names(root)
                if not self.show_hidden:
                    dirs[:] = [name for name in dirs if not local_is_hidden(Path(root) / name, hidden)]
                    files = [name for name in files if not local_is_hidden(Path(root) / name, hidden)]
                entries = [(name, True) for name in dirs] + [(name, False) for name in files]
                for name, is_dir in entries:
                    if self.isInterruptionRequested():
                        return
                    path = Path(root) / name
                    self.scanned += 1
                    if not self.accepts(path, is_dir):
                        continue
                    try:
                        row = (basic_entry(path, True, hidden=local_is_hidden(path, hidden)) if is_dir
                               else listed_media_entry(path, self.isInterruptionRequested, hidden=local_is_hidden(path, hidden)))
                        update_modification(row)
                        relative_parent = path.parent.relative_to(self.folder)
                        location = tr('.') if not relative_parent.parts else str(relative_parent)
                        row.values[12] = location
                        row.sort_values[12] = location.casefold()
                        batch.append(row)
                        self.found += 1
                    except (OSError, ValueError, TimeoutError):
                        continue
                    if len(batch) >= 128:
                        send()
                    if self.scanned % 256 == 0:
                        self.progress.emit(self.scanned, self.found, str(path.parent))
                if not self.recursive:
                    break
            send()
            self.progress.emit(self.scanned, self.found, str(self.folder))
        except Exception as error:
            self.notice.emit(str(error))


class KioRemoteSearchWorker(RecursiveSearchWorker):
    """Search remote names using the same KIO listing backend as the folder view."""

    def __init__(self, location, query, **kwargs):
        super().__init__(location, query, **kwargs)
        self.location = str(location)

    def run(self):
        from .platform_services import services
        from .metadata import remote_entry
        from urllib.parse import quote
        from .media import AUDIO_EXT, IMAGE_EXT
        pending = deque([(self.location, tr('.'))])
        seen = set()
        batch = []
        while pending and not self.isInterruptionRequested():
            location, relative = pending.popleft()
            if location in seen:
                continue
            seen.add(location)
            entries = services.list_kio_location(location)
            if entries is None:
                self.notice.emit(trf('Impossible de lire : \x1f0\x1f', location))
                continue
            for item in entries:
                if self.isInterruptionRequested():
                    return
                name = str(item.get(tr('name'), ''))
                if not name or (not self.show_hidden and kio_is_hidden(item)):
                    continue
                is_dir = bool(item.get(tr('directory')))
                url = str(item.get(tr('url'), ''))
                if not url:
                    url = location.rstrip('/') + '/' + quote(name)
                self.scanned += 1
                if is_dir and self.recursive:
                    pending.append((url, name if relative == tr('.') else relative + '/' + name))
                matched = (fnmatch.fnmatchcase(name.casefold(), self.query)
                           if any(c in self.query for c in '*?[') else self.query in name.casefold())
                if self.query and not matched:
                    continue
                suffix = Path(name).suffix.lower()
                media_kind = ('video' if suffix in EXTENSIONS else 'audio' if suffix in AUDIO_EXT
                              else 'image' if suffix in IMAGE_EXT else 'other')
                if self.kind == 'folders' and not is_dir or self.kind == 'files' and is_dir:
                    continue
                if self.kind in ('video', 'audio', 'image', 'other') and (is_dir or media_kind != self.kind):
                    continue
                row = remote_entry(url, name, is_dir, item.get(tr('size'), 0), item.get(tr('modified'), 0), item.get(tr('mime'), ''),
                accessed=item.get('accessed', 0), original_path=item.get('originalPath', ''),
                deleted=item.get('deleted', ''), local_path=item.get('localPath', ''), hidden=kio_is_hidden(item))
                row.values[12] = relative
                row.sort_values[12] = relative.casefold()
                batch.append(row)
                self.found += 1
                if len(batch) >= 128:
                    self.listed.emit(batch)
                    batch = []
                if self.scanned % 256 == 0:
                    self.progress.emit(self.scanned, self.found, location)
        if batch and not self.isInterruptionRequested():
            self.listed.emit(batch)
        self.progress.emit(self.scanned, self.found, self.location)

def listed_media_entry(path, cancelled=lambda: False, *, hidden=None):
    """Use validated cache data and repair only legacy missing durations."""
    from .media import AUDIO_EXT, IMAGE_EXT, cached_media, expected_kind
    suffix = path.suffix.lower()
    if suffix in EXTENSIONS:
        from .metadata import cached_video
        cached = cached_video(path, cancelled=cancelled)
    elif suffix in AUDIO_EXT | IMAGE_EXT:
        cached = cached_media(path, cancelled=cancelled)
    else:
        cached = None
    if cached is not None:
        cached.metadata_loaded = True
        cached.is_hidden = local_is_hidden(path) if hidden is None else hidden
        return cached
    row = basic_entry(path, hidden=hidden)
    row.is_video = suffix in EXTENSIONS
    row.media_type = expected_kind(path)
    row.values[10] = row.sort_values[10] = tr('Informations détaillées non lues')
    return row

class FolderSizeWorker(QThread):
    tr('Folder counts or recursive sizes are deliberately deferred until navigation ends.')
    results_ready = Signal(object, str)

    def __init__(self, folders, mode='count'):
        super().__init__()
        self.folders = tuple(folders)
        self.mode = mode if mode in ('count', 'size') else 'count'

    def cancel(self):
        self.requestInterruption()

    def run(self):
        results = []
        for folder in self.folders:
            if self.isInterruptionRequested():
                return
            if folder.is_symlink():
                results.append((folder, 0, False))
                continue
            if self.mode == 'count':
                try:
                    count = sum(1 for _entry in folder.iterdir())
                    results.append((folder, count, True))
                except OSError:
                    results.append((folder, 0, False))
                continue
            total, complete = (0, True)

            def size_error(_error):
                nonlocal complete
                complete = False
            for root, _dirs, files in os.walk(folder, onerror=size_error, followlinks=False):
                if self.isInterruptionRequested():
                    return
                for name in files:
                    if self.isInterruptionRequested():
                        return
                    try:
                        candidate = Path(root) / name
                        if not candidate.is_symlink():
                            total += candidate.stat().st_size
                    except OSError:
                        complete = False
            results.append((folder, total, complete))
        if not self.isInterruptionRequested():
            self.results_ready.emit(results, self.mode)
