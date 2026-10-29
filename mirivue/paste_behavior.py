"""Pure helpers for Dolphin-compatible paste menus."""
from pathlib import Path


def context_paste_destination(selected_rows, current_folder):
    """Return the folder targeted by a context-menu Paste action.

    Dolphin targets the clicked item only when exactly one selected item is a
    directory.  A background click or a multiple selection targets the current
    folder, while a single regular file has no Paste action.
    """
    rows = list(selected_rows)
    if len(rows) == 1:
        return rows[0].path if rows[0].is_dir else None
    return current_folder


def paste_action_label(count, single_is_directory=False):
    """Return the French source label used by the runtime translator."""
    if count == 1:
        return 'Coller un dossier' if single_is_directory else 'Coller un fichier'
    return f'Coller {count} éléments'


def local_clipboard_kind(urls):
    """Identify a single local clipboard item for the dynamic Paste label."""
    if len(urls) != 1 or not urls[0].isLocalFile():
        return False
    return Path(urls[0].toLocalFile()).is_dir()
