# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""One KIO inventory for ordinary local/remote folders and background updates."""
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QUrl
from .platform_services import services
from .file_visibility import kio_is_hidden
from .metadata import entry_stat


def local_entries(folder, cancelled=lambda: False):
    entries = services.list_kio_location(QUrl.fromLocalFile(str(Path(folder).absolute())).toString(),
                                         cancelled=cancelled)
    if entries is None:
        if cancelled(): raise InterruptedError()
        raise OSError(f'Impossible de lire le dossier : {folder}')
    for item in entries:
        if cancelled(): raise InterruptedError()
        url = QUrl(str(item.get('url', '')))
        if not url.isLocalFile(): continue
        yield Path(url.toLocalFile()), bool(item.get('directory')), kio_is_hidden(item)


def directory_snapshot(folder, cancelled=lambda: False):
    """Keep exact nanosecond signatures; all filesystem reads stay off the GUI."""
    result = {}
    try:
        for path, is_dir, hidden in local_entries(folder, cancelled):
            try:
                info = entry_stat(path)       # keeps dangling symlinks visible
                result[path] = (is_dir, info.st_mtime_ns, info.st_size, hidden)
            except OSError:
                continue
    except OSError:
        return None
    return result


class DirectorySnapshotWorker(QThread):
    def __init__(self, folders):
        super().__init__()
        self.folders = tuple(folders)
        self.snapshots = {}

    def run(self):
        try:
            for folder in self.folders:
                if self.isInterruptionRequested(): return
                self.snapshots[folder] = directory_snapshot(folder, self.isInterruptionRequested)
        except InterruptedError:
            return
