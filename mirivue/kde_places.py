"""Read KDE's shared Places bookmark file without requiring a GUI session."""

from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


GROUP_HIDDEN_KEYS = {
    0: 'GroupState-Places-IsHidden',
    1: 'GroupState-Remote-IsHidden',
    2: 'GroupState-RecentlySaved-IsHidden',
    3: 'GroupState-SearchFor-IsHidden',
    4: 'GroupState-Devices-IsHidden',
    5: 'GroupState-RemovableDevices-IsHidden',
    7: 'GroupState-Tags-IsHidden',
}


def _xml_name(tag):
    return str(tag).split('}')[-1]


def _metadata_text(element, name, default=''):
    wanted = str(name).casefold()
    for node in element.iter():
        if _xml_name(node.tag).casefold() == wanted:
            return (node.text or '').strip()
    return default


def _bookmark_title(bookmark, href):
    for node in bookmark:
        if _xml_name(node.tag).casefold() == 'title':
            title = (node.text or '').strip()
            if title:
                return title
    parsed = urlsplit(href)
    return Path(unquote(parsed.path)).name or href


def _bookmark_icon(bookmark):
    for node in bookmark.iter():
        if _xml_name(node.tag).casefold() == 'icon' and node.get('name'):
            return str(node.get('name'))
    return 'folder'


def _bookmark_group(href, device=False):
    if device:
        return 4
    scheme = urlsplit(href).scheme.casefold()
    if scheme in {'timeline', 'recentlyused'}:
        return 2
    if 'search' in scheme:
        return 3
    if scheme in {'bluetooth', 'obexftp', 'kdeconnect'}:
        return 4
    if scheme == 'tags':
        return 7
    if scheme == 'remote' or (scheme and scheme not in {'file', 'trash'}):
        return 1
    return 0


def kde_places_bookmarks(path):
    """Return every KDE bookmark, including entries hidden by item or group."""
    path = Path(path)
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            return []
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError):
        return []

    group_hidden = {
        group_id: _metadata_text(root, key).casefold() == 'true'
        for group_id, key in GROUP_HIDDEN_KEYS.items()
    }
    places = []
    for bookmark in root.iter():
        if _xml_name(bookmark.tag).casefold() != 'bookmark':
            continue
        href = str(bookmark.get('href') or '').strip()
        parsed = urlsplit(href)
        if not href or not parsed.scheme:
            continue
        device = bool(_metadata_text(bookmark, 'UDI'))
        group = _bookmark_group(href, device=device)
        individually_hidden = _metadata_text(bookmark, 'IsHidden').casefold() == 'true'
        places.append({
            'name': _bookmark_title(bookmark, href),
            'url': href,
            'icon': _bookmark_icon(bookmark),
            'group': group,
            'device': device,
            'fixed': _metadata_text(bookmark, 'isSystemItem').casefold() == 'true',
            'setupNeeded': False,
            'teardownAllowed': False,
            'ejectAllowed': False,
            'sharedHidden': individually_hidden,
            'sharedGroupHidden': group_hidden.get(group, False),
        })
    return places


def merge_kde_places(model_places, bookmark_places):
    """Restore hidden XBEL rows while retaining live KIO/Solid information."""
    model_places = [dict(place) for place in (model_places or [])]
    indexes = defaultdict(deque)
    for index, place in enumerate(model_places):
        url = str(place.get('url') or '')
        if url:
            indexes[url].append(index)

    used = set()
    merged = []
    for bookmark in bookmark_places or []:
        url = str(bookmark.get('url') or '')
        if indexes[url]:
            index = indexes[url].popleft()
            used.add(index)
            place = dict(bookmark)
            place.update(model_places[index])
            place['sharedHidden'] = bool(place.get('sharedHidden') or bookmark.get('sharedHidden'))
            place['sharedGroupHidden'] = bool(place.get('sharedGroupHidden') or bookmark.get('sharedGroupHidden'))
            merged.append(place)
        elif bookmark.get('sharedHidden') or bookmark.get('sharedGroupHidden'):
            merged.append(dict(bookmark))
    merged.extend(place for index, place in enumerate(model_places) if index not in used)
    return merged
