"""Preflight checks for paths handed to the native KIO deletion job."""

import os


def selected_mount_points(paths):
    """A selected mount root must not be sent to Trash or permanent deletion."""
    return [path for path in paths if os.path.ismount(path)]
