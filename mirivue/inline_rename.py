"""Initial text selection for single-item inline renaming."""

def selected_name_length(name, is_dir=False, known_suffix=''):
    """Select the same basename as Dolphin's KFileItemListWidget."""
    if is_dir:
        base = name
    elif known_suffix and name.endswith('.' + known_suffix):
        base = name[:-(len(known_suffix) + 1)]
    else:
        dot = name.rfind('.')
        base = name[:dot] if 0 < dot < len(name) - 1 else name
    return len(base.encode('utf-16-le')) // 2
