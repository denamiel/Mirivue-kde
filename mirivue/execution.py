from __future__ import annotations

import stat
from pathlib import Path


SCRIPT_MIME_TYPES = {
    'application/x-awk',
    'application/x-fishscript',
    'application/x-perl',
    'application/x-ruby',
    'application/x-shellscript',
    'text/javascript',
    'text/x-lua',
    'text/x-python',
    'text/x-python3',
}


def is_executable_text_file(path, mime_type) -> bool:
    """Match Dolphin's executable-script predicate for a local file.

    ``mime_type`` is deliberately injected so this small policy remains
    independent from Qt and can be tested without starting the interface.
    """
    if not isinstance(path, Path):
        return False
    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    if not stat.S_ISREG(mode) or not mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return False
    try:
        mime_name = str(mime_type.name())
    except (AttributeError, TypeError):
        mime_name = ''
    try:
        dolphin_match = (
            bool(mime_type.inherits('application/x-executable'))
            and bool(mime_type.inherits('text/plain'))
        )
    except (AttributeError, TypeError):
        dolphin_match = False
    if dolphin_match or mime_name in SCRIPT_MIME_TYPES:
        return True
    # QMimeDatabase alone does not always expose the KIO-enriched inheritance
    # used by Dolphin.  A textual shebang is the portable equivalent for an
    # executable script and avoids treating native binaries as text scripts.
    try:
        with path.open('rb') as source:
            beginning = source.read(4096)
    except OSError:
        return False
    return beginning.startswith(b'#!') and b'\0' not in beginning
