"""Durable publication helpers for user files."""

from __future__ import annotations

import os
import errno
from pathlib import Path

from .diagnostics import record_tool_failure


def fsync_directory(directory):
    """Persist directory-entry changes when the local filesystem supports it."""
    directory = Path(directory)
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
    descriptor = os.open(directory, flags)
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EOPNOTSUPP):
                raise
            # FAT/exFAT and some mounts do not implement directory fsync.
            # The file itself has already been flushed; note the reduced
            # crash durability instead of presenting a committed edit as failed.
            record_tool_failure('synchronisation du dossier', f'{directory}: {error}')
    finally:
        os.close(descriptor)


def durable_replace(source, target):
    """Atomically replace *target*, then persist its parent directory entry."""
    source, target = Path(source), Path(target)
    os.replace(source, target)
    try:
        fsync_directory(target.parent)
    except OSError as error:
        # Replacement already succeeded.  Report reduced crash durability
        # without falsely claiming that the user's write failed.
        record_tool_failure('synchronisation du dossier', f'{target.parent}: {error}')

