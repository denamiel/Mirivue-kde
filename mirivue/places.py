from .i18n import tr, trf
tr('Places supplied by Qt, with optional desktop-specific additions.')
from pathlib import Path
from PySide6.QtCore import QStandardPaths, QStorageInfo, QUrl
from .platform_services import services
from .kde_places import kde_places_bookmarks

def kde_bookmarks(path):
    places = []
    for bookmark in kde_places_bookmarks(path):
        url = QUrl(str(bookmark.get('url') or ''))
        if bookmark.get('sharedHidden') or not url.isLocalFile() or url.host() not in ('', tr('localhost')):
            continue
        location = url.toLocalFile()
        if not Path(location).is_absolute():
            continue
        places.append((str(bookmark.get('name') or Path(location).name or location), location,
                       str(bookmark.get('icon') or tr('folder-favorites'))))
    return places


def location_identity(location):
    """Source-only fallback for the native Places caption and URL icon."""
    from .locations import Location
    from .folder_icons import directory_icon_name, standard_folder_icons
    from PySide6.QtCore import QUrlQuery
    value = str(location or Path.home())
    target = Location.from_value(value)
    url = QUrl(value) if target.is_uri else QUrl.fromLocalFile(value)
    if url.path() in ('', '/'):
        title = QUrlQuery(url).queryItemValue('title')
        if title:
            return title, 'folder'
    for data_home in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.GenericDataLocation):
        for bookmark in kde_places_bookmarks(Path(data_home) / 'user-places.xbel'):
            if QUrl(bookmark['url']).matches(url, QUrl.ComponentFormattingOption(
                    QUrl.UrlFormattingOption.StripTrailingSlash.value)):
                return str(bookmark['name']), str(bookmark.get('icon') or 'folder')
    if not target.is_uri:
        path = Path(value)
        for _group, title, place, icon in local_places():
            if Path(place) == path:
                return title, icon
        return path.name or '/', directory_icon_name(path) or standard_folder_icons().get(path, 'folder')
    title = url.fileName() or (url.path() if url.path() != '/' else '') or url.host() or url.toString()
    return title, {'trash': 'user-trash', 'recentlyused': 'document-open-recent',
                   'smb': 'network-server', 'sftp': 'network-server'}.get(url.scheme(), 'folder')

def local_places():
    standard = QStandardPaths.StandardLocation
    entries, seen = ([], set())

    def add(group, title, path, icon):
        if path and path not in seen and Path(path).is_dir():
            entries.append((group, title, path, icon))
            seen.add(path)
    for title, kind, icon in [(tr('Dossier personnel'), standard.HomeLocation, tr('user-home')), (tr('Bureau'), standard.DesktopLocation, tr('user-desktop')), (tr('Téléchargements'), standard.DownloadLocation, tr('folder-download')), (tr('Documents'), standard.DocumentsLocation, tr('folder-documents')), (tr('Vidéos'), standard.MoviesLocation, tr('folder-videos')), (tr('Images'), standard.PicturesLocation, tr('folder-pictures')), (tr('Musique'), standard.MusicLocation, tr('folder-music'))]:
        add(tr('Emplacements'), title, QStandardPaths.writableLocation(kind), icon)
    if services.name != tr('windows'):
        add(tr('Emplacements'), tr('Système de fichiers'), tr('/'), tr('drive-harddisk'))
    if services.capabilities.kde_places:
        for data_home in QStandardPaths.standardLocations(standard.GenericDataLocation):
            for title, path, icon in kde_bookmarks(Path(data_home) / tr('user-places.xbel')):
                add(tr('Favoris du système'), title, path, icon)
    root_device = bytes(QStorageInfo.root().device())
    seen_devices = {root_device}
    for volume in QStorageInfo.mountedVolumes():
        path, device = (volume.rootPath(), bytes(volume.device()))
        filesystem = bytes(volume.fileSystemType())
        if device in seen_devices or filesystem in (b'tmpfs', b'devtmpfs', b'proc', b'sysfs', b'overlay') or (not volume.isValid()) or (not volume.isReady()):
            continue
        if not Path(path).is_dir():
            continue
        if services.name == tr('linux') and (path.startswith((tr('/proc'), tr('/sys'), tr('/dev'))) or (path.startswith(tr('/run')) and (not path.startswith(tr('/run/media/'))))):
            continue
        seen_devices.add(device)
        add(tr('Volumes'), volume.displayName() or path, path, tr('drive-removable-media'))
    return entries


def automatic_tab_text(title):
    """Use Dolphin's native rsqueeze, after escaping Qt accelerators."""
    import ctypes
    import os
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if path:
        try:
            library = ctypes.CDLL(path)
            library.mirivue_tab_text.argtypes = [ctypes.c_char_p]
            library.mirivue_tab_text.restype = ctypes.c_char_p
            return library.mirivue_tab_text(str(title).encode('utf-8')).decode('utf-8')
        except (OSError, AttributeError):
            pass
    # Source-only fallback follows QString's UTF-16 length and the three dots.
    escaped = str(title).replace('&', '&&')
    encoded = escaped.encode('utf-16-le')
    if len(encoded) <= 80:
        return escaped
    prefix = encoded[:74].decode('utf-16-le', errors='ignore')
    return prefix + '...'


def set_automatic_tab_text(tab_bar, index, title):
    """Set the native QString directly, without a lossy UTF-8 output conversion."""
    import ctypes
    import os
    import shiboken6
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if path:
        try:
            library = ctypes.CDLL(path)
            library.mirivue_tab_set_text.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
            library.mirivue_tab_set_text.restype = ctypes.c_int
            if library.mirivue_tab_set_text(shiboken6.getCppPointer(tab_bar)[0], index, str(title).encode('utf-8')) >= 0:
                return
        except (OSError, AttributeError):
            pass
    tab_bar.setTabText(index, automatic_tab_text(title))
