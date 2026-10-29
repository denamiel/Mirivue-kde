"""Dolphin-style summaries for the footer below each file pane."""


def _row_size(row):
    if getattr(row, 'is_dir', False):
        return 0
    try:
        value = int(row.sort_values[1])
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0
    return max(0, value)


def summarize_items(rows, translate, format_size, selected=False):
    """Describe folders, files and file bytes without counting folder contents."""
    rows = list(rows)
    folders = sum(bool(getattr(row, 'is_dir', False)) for row in rows)
    files = len(rows) - folders
    file_size = sum(_row_size(row) for row in rows)

    if selected:
        count = len(rows)
        if not count:
            return ''
        if folders == count:
            noun = translate('dossier' if count == 1 else 'dossiers')
        elif files == count:
            noun = translate('fichier' if count == 1 else 'fichiers')
        else:
            noun = translate('élément' if count == 1 else 'éléments')
        adjective = translate('sélectionné' if count == 1 else 'sélectionnés')
        text = f'{count} {noun} {adjective}'
    else:
        parts = []
        if folders:
            parts.append(f"{folders} {translate('dossier' if folders == 1 else 'dossiers')}")
        if files:
            parts.append(f"{files} {translate('fichier' if files == 1 else 'fichiers')}")
        text = ', '.join(parts) if parts else f"0 {translate('élément')}"

    if files:
        text += f' ({format_size(file_size)})'
    return text
