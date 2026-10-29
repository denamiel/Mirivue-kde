"""Path-segment helpers shared by the Dolphin-style location bars."""

from pathlib import Path


def local_place_breadcrumb(path, places, home=None, home_title='Dossier personnel', show_full=False):
    """Return ``(path, label)`` segments rooted at the closest KDE Place.

    Dolphin can display a breadcrumb relative to the current Places entry.  A
    folder below Documents therefore starts with ``Documents`` instead of
    repeating ``Dossier personnel > Documents``.  The deepest matching Place
    wins, which also covers nested bookmarks and mounted volumes.
    """
    current = Path(path).expanduser()
    home = Path.home() if home is None else Path(home).expanduser()
    best = None

    if show_full:
        anchor = Path(current.anchor or '/')
        result = [(anchor, anchor.name or str(anchor))]
        cursor = anchor
        for name in current.relative_to(anchor).parts:
            cursor /= name
            result.append((cursor, name))
        return result

    for _group, title, raw_path, _icon in places:
        place = Path(raw_path).expanduser()
        try:
            relative = current.relative_to(place)
        except ValueError:
            continue
        candidate = (len(place.parts), place, str(title), relative)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is not None:
        _depth, anchor, anchor_title, relative = best
    else:
        try:
            relative = current.relative_to(home)
            anchor, anchor_title = home, home_title
        except ValueError:
            anchor = Path(current.anchor or '/')
            anchor_title = anchor.name or str(anchor)
            relative = current.relative_to(anchor)

    result = [(anchor, anchor_title)]
    cursor = anchor
    for name in relative.parts:
        cursor /= name
        result.append((cursor, name))
    return result
