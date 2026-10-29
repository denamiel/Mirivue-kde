from .i18n import tr, trf
import time
import os
import json
from pathlib import Path
import shutil
import sys
import ctypes
import ctypes.util
import stat as stat_module
from urllib.parse import unquote
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPoint, QSortFilterProxyModel, Qt, QThread, Signal, QUrl, QSettings, QTimer, QDir, QFile, QItemSelectionModel, QProcess, QFileSystemWatcher, QEvent, QSize, QStorageInfo, QMimeDatabase, QLockFile, QStandardPaths
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QShortcut, QKeySequence, QColor, QFont, QAction, QPixmap, QPalette, QActionGroup
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QCheckBox, QTableView, QFormLayout, QFileDialog, QMessageBox, QMenu, QProgressBar, QProgressDialog, QAbstractItemView, QTreeView, QFileSystemModel, QSplitter, QStyle, QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem, QComboBox, QSpinBox, QStackedWidget, QTreeWidget, QTreeWidgetItem, QListView, QScrollArea, QInputDialog, QSystemTrayIcon, QButtonGroup, QFrame, QSizePolicy, QToolButton, QToolBar, QTabWidget, QTabBar, QDockWidget
from types import SimpleNamespace
from .platform_services import services
from .window_geometry import initial_window_size, restore_window_geometry, geometry_to_save
from .natural_sort import natural_name_key, cached_natural_name_key, string_compare
from .i18n import load_system_translation
from .jobs import JobMixin
from .enhancements import EnhancementMixin
from . import library
from .file_visibility import hidden_names, local_is_hidden, kio_is_hidden
from .selection import DetailsView, IconView, IS_DIRECTORY_ROLE
from .item_presentation import presentation_model, PresentationStateMixin, map_file_index

_MODEL_DATA_ROLES = frozenset((
    Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,
    Qt.ItemDataRole.TextAlignmentRole,
    Qt.ItemDataRole.FontRole, Qt.ItemDataRole.DecorationRole,
    Qt.ItemDataRole.UserRole, Qt.ItemDataRole.ToolTipRole,
    IS_DIRECTORY_ROLE, Qt.ItemDataRole.UserRole + 43, Qt.ItemDataRole.UserRole + 44,
))
from .context_menu_settings import ContextMenuMixin, mark_entry, service_enabled
from .menu_visibility import MenuVisibility
from .transfers import TransferMixin
from .paste_behavior import context_paste_destination
from .actions_extra import ExtraActionsMixin
from .desktop import DesktopMixin
from .panes import PaneMixin
from .movement import MovementMixin
from .metadata import HEADERS, EXTENSIONS, inspect, failed, quantity, basic_entry, remote_entry, update_modification, modification_text, normalized_date_format
from .locations import ARCHIVE_PROTOCOLS, Location, archive_protocol, archive_source_path, archive_subfolder_name, archive_url, parent_location
from .launch_targets import LaunchRequest, parse_launch_arguments, parse_launch_requests, is_browsable_location
from .external_locations import ExternalLocationsMixin
from .view_policy import per_folder_views, special_view, ViewPolicyMixin
from .tab_ui import DolphinTabBar
from .session_state import SessionMixin
from .folder_icons import standard_folder_icons, themed_folder_icon
from . import __version__, RELEASE_DATE, AUTHOR
from .diagnostics import begin_session, diagnostic_report, end_session, record_tool_failure, state_directory
from .iconography import themed_icon, set_themed_action_icon, add_destructive_action, add_dynamic_trash_action, context_help_button
from .archive_backend import extract_rar_with_ark, safe_archive_entry_name
from .extensions import prepare_renames, apply_renames, fingerprint, suggest_extension
from .kde_places import kde_places_bookmarks, merge_kde_places
from .places import local_places
from .pane_status import summarize_items
from .runtime_tasks import RuntimeTaskRegistry
from .duration_queue import DurationQueue
from .column_groups import PRIMARY_COLUMNS, MEDIA_COLUMNS
from .action_feedback import set_action_enabled
from .deletion_guard import selected_mount_points
from .duplicates import find_duplicates, keep_one
from .health import explain_error
from .thumbnails import ThumbnailWorker
from .renaming import PRESETS, batch_names, prepare_names, external_command, find_external_renames, folder_rename_rows
from .execution import is_executable_text_file
from .permissions import add_permissions_tab, apply_permissions
from .organization import OrganizationMixin
from .background_listing import RecursiveSearchWorker, KioRemoteSearchWorker, listed_media_entry, FolderSizeWorker
from . import __version__
from PySide6.QtNetwork import QLocalServer, QLocalSocket

def mirivue_settings():
    tr('Create isolated Mirivue preferences and import prior MFM choices once.')
    settings = QSettings('pdenams', 'Mirivue')
    already_configured = bool(settings.allKeys())
    if not settings.contains('startup/allow_multiple_instances'):
        # Dolphin 26.08.2 opens new external folders in windows by default.
        # Existing installations retain Mirivue's former tab default.
        settings.setValue('startup/allow_multiple_instances', not already_configured)
    if not already_configured and not settings.contains('startup/location'):
        settings.setValue('startup/location', 'session')
    if not settings.value('migration/from-mfm-0282', False, type=bool):
        legacy = QSettings(tr('VideoInfoTable'), tr('VideoInfoTable'))
        for key in legacy.allKeys():
            settings.setValue(key, legacy.value(key))
        settings.setValue('migration/from-mfm-0282', True)
        settings.sync()
    return settings
# Version-scoped IPC prevents an already-running older release from silently
# receiving launches intended for the newly installed application.
INSTANCE_SERVER_NAME = 'org.pdenams.Mirivue.instance.' + __version__

def start_single_instance_server(application):
    tr('Return a listening server, or False after delivering a launch to Mirivue.')
    settings = mirivue_settings()
    from .window_instances import route_to_windows
    launch_requests = parse_launch_requests(sys.argv[1:])
    if '--new-window' not in sys.argv[1:]:
        routed = route_to_windows(launch_requests,
            properties='--show-properties' in sys.argv[1:], split='--split' in sys.argv[1:],
            activation_token=os.environ.get('XDG_ACTIVATION_TOKEN', ''))
        if routed:
            return False
        if routed.delivered or routed.uncertain:
            application._mirivue_remaining_launches = routed.remaining
            # The local socket has no per-folder receipt; bypass it after a
            # partial D-Bus delivery instead of retransmitting the whole batch.
            return None
    if '--new-window' in sys.argv[1:]:
        return None
    socket = QLocalSocket(application)
    socket.connectToServer(INSTANCE_SERVER_NAME)
    if socket.waitForConnected(180):
        requests = parse_launch_requests(sys.argv[1:])
        if not requests:
            socket.disconnectFromServer()
            return None
        payload = json.dumps({'locations': [{'folder': r.folder, 'files': r.files}
                                             for r in requests], 'split': '--split' in sys.argv[1:],
                              'properties': '--show-properties' in sys.argv[1:],
                              'activation_token': os.environ.get('XDG_ACTIVATION_TOKEN', '')}).encode('utf-8')
        socket.write(payload)
        socket.flush()
        socket.waitForBytesWritten(180)
        socket.disconnectFromServer()
        return False
    QLocalServer.removeServer(INSTANCE_SERVER_NAME)
    server = QLocalServer(application)
    if server.listen(INSTANCE_SERVER_NAME):
        return server
    lock_path = Path(settings.fileName()).parent / tr('mirivue.instance.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(30000)
    if not lock.tryLock(0):
        return False
    application._mirivue_instance_lock = lock
    return None

def prepare_system_style(application):
    """Use KF6's native style manager in GNOME and the platform theme in Plasma."""
    services.initialize_application_style()

def deliver_launches(server, window):
    while server.hasPendingConnections():
        socket = server.nextPendingConnection()
        socket.setParent(server)

        def receive(source=socket):
            buffered = getattr(source, '_mirivue_launch_buffer', b'') + bytes(source.readAll())
            from .window_instances import MAX_MESSAGE_BYTES
            if len(buffered) > MAX_MESSAGE_BYTES:
                source.disconnectFromServer()
                source.deleteLater()
                return
            source._mirivue_launch_buffer = buffered
            try:
                payload = json.loads(buffered.decode('utf-8'))
            except (ValueError, TypeError, RecursionError):
                # QLocalSocket may deliver a multi-folder request in several
                # readyRead events. Wait for the complete JSON document.
                return
            if hasattr(window, 'receive_launch_payload') and isinstance(payload, dict) and payload.get('locations'):
                window.receive_launch_payload(payload)
                source.disconnectFromServer()
                source.deleteLater()
                return
            locations = payload.get('locations') if isinstance(payload, dict) else None
            if isinstance(locations, list):
                requests = []
                for item in locations:
                    if not isinstance(item, dict) or not isinstance(item.get('folder'), str):
                        continue
                    if not is_browsable_location(item['folder']):
                        continue
                    raw_files = item.get('files', [])
                    files = tuple(path for path in raw_files
                                  if isinstance(path, str) and Path(path).is_file()) if isinstance(raw_files, list) else ()
                    requests.append(LaunchRequest(item['folder'], files))
                if requests:
                    window.open_external_locations(requests)
                else:
                    window.restore_window()
            else:
                # Accept the former socket payload for independent launchers.
                folder = payload.get('folder', '') if isinstance(payload, dict) else ''
                if is_browsable_location(folder):
                    files = [Path(path) for path in payload.get('files', []) if Path(path).is_file()]
                    window.open_external_location(folder, files)
                else:
                    window.restore_window()
            source.disconnectFromServer()
            source.deleteLater()
        socket.readyRead.connect(receive)
        if socket.bytesAvailable():
            receive()

class StayingOpenMenu(QMenu):
    tr('Allow several checkable choices before a click outside closes the menu.')

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.position().toPoint())
        if action and action.isEnabled() and action.isCheckable() and (action.menu() is None):
            action.trigger()
            self.setActiveAction(action)
            return
        super().mouseReleaseEvent(event)


def wheel_zoom_steps(delta, remainder, threshold=120):
    """Convert wheel motion to whole zoom steps, retaining partial motion."""
    total = delta + remainder
    steps = (abs(total) // threshold) * (1 if total >= 0 else -1)
    return steps, total - steps * threshold

class DeleteDialog(QDialog):

    def __init__(self, worker, parent):
        super().__init__(parent)
        self.worker = worker

    def reject(self):
        self.worker.requestInterruption()
        self.setWindowTitle(tr('Arrêt après l’élément en cours…'))

class ChangedEntriesWorker(QThread):
    tr('Inspect only entries that a visible directory watcher has identified.')
    found = Signal(object)
    progress = Signal(int, int)

    def __init__(self, paths, read_metadata=True):
        super().__init__()
        self.paths = tuple(paths)
        self.read_metadata = read_metadata

    def run(self):
        from .media import AUDIO_EXT, IMAGE_EXT
        total = len(self.paths)
        for index, path in enumerate(self.paths, 1):
            if self.isInterruptionRequested():
                return
            try:
                if path.is_dir():
                    row = basic_entry(path, True)
                elif path.suffix.lower() in EXTENSIONS | AUDIO_EXT | IMAGE_EXT:
                    row = inspect(path, self.isInterruptionRequested) if self.read_metadata else listed_media_entry(path, self.isInterruptionRequested)
                else:
                    row = basic_entry(path)
                if not self.isInterruptionRequested():
                    self.found.emit(row)
            except (OSError, ValueError, TimeoutError) as error:
                if not self.isInterruptionRequested():
                    self.found.emit(failed(path, str(error)))
            self.progress.emit(index, total)

class DurationLookupWorker(QThread):
    """Resolve only immediately useful media properties in the background."""
    found = Signal(object, object, object)

    def __init__(self, paths, pane_id, visible=(), parent=None):
        super().__init__(parent)
        self.queue = DurationQueue()
        self.queue.add(paths, visible)
        self.avoid_baloo = len(paths) > 8
        self.pane_id = pane_id

    def run(self):
        from .metadata import cached_quick_metadata
        while not self.isInterruptionRequested():
            path = self.queue.take()
            if path is None:
                return
            if self.isInterruptionRequested():
                return
            try:
                signature = fingerprint(path)
                values = cached_quick_metadata(path, self.isInterruptionRequested,
                                               consult_baloo=not self.avoid_baloo)
                if values and fingerprint(path) == signature and not self.isInterruptionRequested():
                    self.found.emit(path, signature, values)
            except (OSError, ValueError, TimeoutError, TypeError, InterruptedError):
                if self.isInterruptionRequested():
                    return

class ArchiveEntriesWorker(QThread):
    """List an archive root without blocking the interface before extraction."""
    completed = Signal(object, str)

    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.location = str(location)

    def run(self):
        entries = services.list_kio_location(self.location)
        if self.isInterruptionRequested():
            self.completed.emit([], tr('Extraction annulée.'))
        elif entries is None:
            self.completed.emit([], tr('Le contenu de l’archive n’a pas pu être lu.'))
        else:
            self.completed.emit(entries, '')


class RarExtractWorker(QThread):
    progress = Signal(int, str)
    completed = Signal(bool, str)

    def __init__(self, archive, destination, parent=None):
        super().__init__(parent)
        self.archive = Path(archive)
        self.destination = Path(destination)

    def run(self):
        ark = services.tool_path(tr('ark'))
        if not ark:
            self.completed.emit(False, tr('Ark est absent.'))
            return
        ok, error = extract_rar_with_ark(
            ark, self.archive, self.destination,
            cancelled=self.isInterruptionRequested,
            progress=lambda value, message: self.progress.emit(value, tr(message)),
        )
        self.completed.emit(ok, tr(error))

class Scanner(QThread):
    initial = Signal(object)
    listed = Signal(object)
    resolved = Signal(object)
    progress = Signal(int, int)
    notice = Signal(str)
    folder_size = Signal(object, object, bool)

    def __init__(self, folder, recursive, show_hidden=False):
        super().__init__()
        self.folder, self.recursive = (folder, recursive)
        self.show_hidden = show_hidden
        self.cancelled = False
        self.skip_embed_paths = set()

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

    def run(self):
        try:
            from .media import AUDIO_EXT, IMAGE_EXT
            media_extensions = EXTENSIONS | AUDIO_EXT | IMAGE_EXT
            listed = []
            resolved = []

            def send_listed():
                nonlocal listed
                if listed:
                    self.listed.emit(listed)
                    listed = []

            def send_resolved():
                nonlocal resolved
                if resolved:
                    self.resolved.emit(resolved)
                    resolved = []

            def walk_error(error):
                self.notice.emit(str(error))
            for root, dirs, files in os.walk(self.folder, onerror=walk_error, followlinks=False):
                if self.isInterruptionRequested():
                    return
                hidden = hidden_names(root)
                if not self.show_hidden:
                    dirs[:] = [name for name in dirs if not local_is_hidden(Path(root) / name, hidden)]
                    files = [name for name in files if not local_is_hidden(Path(root) / name, hidden)]
                if Path(root) == Path(self.folder):
                    # Build the first visible directory listing in display
                    # order before sending any rows. Streaming arbitrary
                    # os.walk order makes QListView::Adjust move icons every
                    # time an earlier name arrives.
                    initial = []
                    for name in sorted(dirs):
                        folder_path = Path(root) / name
                        entry = basic_entry(folder_path, True, hidden=local_is_hidden(folder_path, hidden))
                        # Dolphin leaves the folder-size field empty until the
                        # asynchronous count is available.  A textual loading
                        # state makes every row change twice and is visually
                        # noisy in an otherwise stable directory listing.
                        entry.values[1] = ''
                        entry.sort_values[1] = -1
                        initial.append(entry)
                for name in files:
                    if self.isInterruptionRequested():
                        return
                    path = Path(root) / name
                    if Path(root) == Path(self.folder):
                        try:
                            entry = listed_media_entry(path, self.isInterruptionRequested, hidden=local_is_hidden(path, hidden)) if path.suffix.lower() in media_extensions else basic_entry(path, hidden=local_is_hidden(path, hidden))
                            update_modification(entry)
                            initial.append(entry)
                        except OSError:
                            pass
                    elif path.suffix.lower() in media_extensions:
                        try:
                            entry = listed_media_entry(path, self.isInterruptionRequested, hidden=local_is_hidden(path, hidden))
                            update_modification(entry)
                            if entry.metadata_loaded:
                                resolved.append(entry)
                                if len(resolved) >= 32:
                                    send_resolved()
                            else:
                                listed.append(entry)
                        except OSError:
                            pass
                        if len(listed) >= 128:
                            send_listed()
                if Path(root) == Path(self.folder):
                    initial.sort(key=lambda entry: natural_name_key(entry.path.name))
                    # Publish one coherent inventory like Dolphin's file
                    # model, instead of visibly moving rows after each batch.
                    self.initial.emit(initial)
                if not self.recursive:
                    break
            send_listed()
            send_resolved()
        except Exception as error:
            self.notice.emit(str(error))



class KioScanner(QThread):
    listed = Signal(object)
    notice = Signal(str)

    def __init__(self, location, show_hidden=False):
        super().__init__()
        self.location = str(location)
        self.show_hidden = show_hidden
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

    def run(self):
        if self.isInterruptionRequested():
            return
        entries = services.list_kio_location(self.location)
        if entries is None:
            if not self.isInterruptionRequested():
                self.notice.emit(tr('Impossible de lire cet emplacement.'))
            return
        rows = []
        for item in entries:
            name = str(item.get(tr('name'), ''))
            if not name or (not self.show_hidden and kio_is_hidden(item)):
                continue
            url = str(item.get(tr('url'), ''))
            if not url:
                from urllib.parse import quote
                url = self.location.rstrip(tr('/')) + tr('/') + quote(name)
            rows.append(remote_entry(url, name, bool(item.get(tr('directory'))), item.get(tr('size'), 0), item.get(tr('modified'), 0), item.get(tr('mime'), ''),
                accessed=item.get('accessed', 0), original_path=item.get('originalPath', ''),
                deleted=item.get('deleted', ''), local_path=item.get('localPath', ''), hidden=kio_is_hidden(item), real_name=item.get('realName', '')))
        if not self.isInterruptionRequested():
            self.listed.emit(rows)


class DeepScanner(QThread):
    item_started = Signal(object)
    failure = Signal(object, str)
    current = Signal(str)
    cleanup_warning = Signal(str)

    def __init__(self, paths, embed=True):
        super().__init__()
        self.paths = paths
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

class DuplicateScanner(DeepScanner):
    groups_found = Signal(object)

    def run(self):
        try:
            self.groups_found.emit(find_duplicates(self.paths, self.isInterruptionRequested, self.current.emit, self.cleanup_warning.emit))
        except InterruptedError:
            return
        except Exception as error:
            self.cleanup_warning.emit(str(error))

class DuplicateCleaner(DeepScanner):
    verified = Signal(object)

    def __init__(self, group, keeper):
        super().__init__([], embed=False)
        self.group, self.keeper = (group, keeper)

    def run(self):
        try:
            planned = []
            removed, errors = keep_one(self.group, self.keeper, planned.append, self.isInterruptionRequested, self.current.emit)
            for error in errors:
                self.cleanup_warning.emit(error)
            if not errors and not self.isInterruptionRequested():
                self.verified.emit(removed)
        except InterruptedError:
            return
        except Exception as error:
            self.cleanup_warning.emit(str(error))

from .model_inventory import ModelInventory


class VideoModel(ModelInventory, PresentationStateMixin, QAbstractTableModel):

    def __init__(self, date_format='locale'):
        super().__init__()
        self.date_format = normalized_date_format(date_format)
        self.mime_database = QMimeDatabase()
        self.mime_icons = {}
        self.row_icons = {}
        self.standard_folder_icons = standard_folder_icons()
        self.rows = []
        self.init_inventory()
        self.thumbnails = {}
        self.preliminary = {}
        self.show_thumbnails = False
        self.rename_handler = None
        self.edit_allowed = lambda: False
        self.path_edit_allowed = lambda path: True
        self.semantic_color_group = QPalette.ColorGroup.Active

    def inventory_is_incomplete(self, row):
        return bool(getattr(row, 'metadata_loaded', False) and media_missing_fields(row))

    def semantic_color(self, meaning):
        return services.semantic_color(meaning, self.semantic_color_group == QPalette.ColorGroup.Inactive)

    def file_icon(self, row):
        """Return the active KDE theme icon for a file's real MIME type."""
        cached = self.row_icons.get(row.path)
        if cached is not None:
            return cached
        if row.is_dir:
            location = Location.from_value(row.path)
            if not location.is_uri:
                icon = themed_folder_icon(row.path, self.standard_folder_icons)
                if not icon.isNull():
                    self.row_icons[row.path] = icon
                    return icon
            icon = QIcon.fromTheme(
                'folder', QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            self.row_icons[row.path] = icon
            return icon

        location = Location.from_value(row.path)
        mime = None
        if location.is_uri:
            mime_name = str(row.values[10] or '')
            if '/' in mime_name:
                mime = self.mime_database.mimeTypeForName(mime_name)
        else:
            path = Path(row.path)
            mode = (QMimeDatabase.MatchMode.MatchExtension if path.suffix
                    else QMimeDatabase.MatchMode.MatchContent)
            mime = self.mime_database.mimeTypeForFile(str(path), mode)

        media_fallback = {
            tr('video'): 'video-x-generic',
            tr('audio'): 'audio-x-generic',
            tr('image'): 'image-x-generic',
        }.get(row.media_type or (tr('video') if row.is_video else ''), 'unknown')
        mime_name = mime.name() if mime is not None and mime.isValid() else ''
        cache_key = mime_name or f'fallback:{media_fallback}'
        cached = self.mime_icons.get(cache_key)
        if cached is not None:
            self.row_icons[row.path] = cached
            return cached

        names = []
        if mime is not None and mime.isValid():
            names.extend((mime.iconName(), mime.genericIconName()))
        names.extend((media_fallback, 'unknown'))
        icon = QIcon()
        for name in dict.fromkeys(filter(None, names)):
            icon = QIcon.fromTheme(name)
            if not icon.isNull():
                break
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        self.mime_icons[cache_key] = icon
        self.row_icons[row.path] = icon
        return icon

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        column = index.column()
        # Unsupported Qt roles are requested for every painted cell. They do
        # not depend on the row, so avoid Python model work for those roles.
        if role not in _MODEL_DATA_ROLES:
            return None
        row = self.rows[index.row()]
        if column == 2 and row.is_dir:
            from .metadata import duration
            if role == Qt.ItemDataRole.DisplayRole:
                return duration(row.total_duration) + (tr(' (partielle)') if tr('résultat partiel') in row.duration_note else '') if row.total_duration is not None else ''
            if role == Qt.ItemDataRole.UserRole:
                return row.total_duration if row.total_duration is not None else -1
            if role == Qt.ItemDataRole.ToolTipRole:
                note = row.duration_note or tr('Calcul à la demande, avec les sous-dossiers.')
                composition = row.values[36] if row.media_counts else ''
                return note + (tr('\nMédias trouvés : ') + composition if composition else '')
        if column == 16:
            rate = row.bitrate_result[0] if row.bitrate_result else None
            if role == Qt.ItemDataRole.DisplayRole:
                return quantity(rate, [tr('bit/s'), tr('kbit/s'), tr('Mbit/s'), tr('Gbit/s')], 1000) if rate else ''
            if role == Qt.ItemDataRole.UserRole:
                return rate or -1
        if column in (14, 38, 39) and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            timestamp = row.modified_ns if column == 14 else row.accessed_ns if column == 38 else row.deleted_ns
            return modification_text(timestamp, mode=self.date_format) if timestamp is not None else ''
        if column == 0 and role == Qt.ItemDataRole.UserRole + 43:
            from .locations import Location
            location = Location.from_value(row.path)
            return QUrl(str(row.path)) if location.is_uri else QUrl.fromLocalFile(str(row.path))
        if column == 0 and role == IS_DIRECTORY_ROLE:
            return row.is_dir
        if column == 0 and role == Qt.ItemDataRole.UserRole + 44:
            return row.is_hidden
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return row.values[column]
        if column in (1, 2, 5, 6, 9) and role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.FontRole and column == 11 and (tr('à corriger') in row.values[11]):
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.DecorationRole and column == 0:
            if self.show_thumbnails and row.path in self.thumbnails:
                return self.thumbnails[row.path]
            return self.file_icon(row)
        if role == Qt.ItemDataRole.UserRole:
            return row.sort_values[column]
        if role == Qt.ItemDataRole.ToolTipRole and column == 1:
            if row.is_dir:
                return row.folder_size_note
            size = row.sort_values[1]
            return trf('\x1f0\x1f octets', format(int(size), ',')).replace(tr(','), tr(' ')) if size >= 0 else tr('Taille inconnue')
        if role == Qt.ItemDataRole.ToolTipRole and column == 7:
            return row.hdr_note
        if role == Qt.ItemDataRole.ToolTipRole:
            missing = media_missing_fields(row)
            missing_note = trf('Données manquantes : \x1f0\x1f', tr(', ').join(missing)) if missing else ''
            notes = [part for part in row.values[10].split(tr(' • '))
                     if part and part not in (tr('OK'), tr('Dossier'), tr('Autre fichier'), row.personal_label)]
            if row.personal_label:
                notes.append(tr('Étiquette : ') + row.personal_label)
            if row.duplicate_group:
                notes.append(trf('Doublon groupe \x1f0\x1f', row.duplicate_group))
            if row.validation_status:
                notes.append(row.validation_status)
            return tr('\n').join(dict.fromkeys(value for value in [str(row.path),
                tr('Modifié : ') + modification_text(row.modified_ns, mode=self.date_format),
                missing_note, *notes, row.error, row.bitrate_note, row.bitrate_error,
                row.validation_error, row.extension_note] if value))

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid():
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        if index.isValid() and index.column() == 0 and self.edit_allowed() and self.path_edit_allowed(self.rows[index.row()].path):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole or not index.isValid() or index.column() != 0 or (not self.edit_allowed()):
            return False
        return bool(self.rename_handler and self.rename_handler(self.rows[index.row()].path, str(value)))

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return HEADERS[section]
            if role == Qt.ItemDataRole.ToolTipRole:
                explanations = {1: tr('Taille des fichiers. Pour les dossiers, Configuration permet de choisir le nombre d’éléments ou la taille totale.'), 6: tr('Débit déclaré dans le fichier. Il peut être absent selon le conteneur.'), 7: tr('HDR/SDR est déterminé à partir des métadonnées de la piste vidéo ; « Indéterminé » signifie qu’aucune indication fiable n’est présente.'), 10: tr('État de lecture, de traitement ou d’erreur.')}
                return explanations.get(section, '')
        return super().headerData(section, orientation, role)

    def add_preliminary(self, rows):
        if not rows:
            return
        start = len(self.rows)
        self.beginInsertRows(QModelIndex(), start, start + len(rows) - 1)
        for row in rows:
            if row.values[10] == tr('Lecture des informations…'):
                self.preliminary[row.path] = len(self.rows)
            self.rows.append(row)
        self.endInsertRows()

    def add(self, video):
        from .media import sync_columns
        sync_columns(video)
        update_modification(video)
        while len(video.values) < len(HEADERS):
            video.values.append('')
        while len(video.sort_values) < len(HEADERS):
            video.sort_values.append(-1)
        position = self.preliminary.pop(video.path, None)
        if position is not None:
            self.row_icons.pop(video.path, None)
            self.rows[position] = video
            self.dataChanged.emit(self.index(position, 0), self.index(position, len(HEADERS) - 1))
            return
        self.beginInsertRows(QModelIndex(), len(self.rows), len(self.rows))
        self.rows.append(video)
        self.endInsertRows()

    def remove_paths(self, paths):
        paths = set(paths)
        for path in paths:
            self.row_icons.pop(path, None)
        for position in reversed([i for i, row in enumerate(self.rows) if row.path in paths]):
            path = self.rows[position].path
            self.beginRemoveRows(QModelIndex(), position, position)
            self.rows.pop(position)
            self.endRemoveRows()
            self.preliminary.pop(path, None)
            self.thumbnails.pop(path, None)
        self.preliminary = {row.path: i for i, row in enumerate(self.rows) if row.path in self.preliminary}

    def clear(self):
        self.beginResetModel()
        self.rows.clear()
        self.preliminary.clear()
        self.thumbnails.clear()
        self.row_icons.clear()
        self.endResetModel()

def media_missing_fields(item):
    """Return the media facts that are genuinely absent for one row."""
    if item.is_dir or not item.metadata_loaded:
        return []
    from .media import kind
    media_kind = kind(item)
    if media_kind not in (tr('video'), tr('audio'), tr('image')):
        return []
    missing = lambda value: value in (None, '', 0, -1, tr('—'))
    fields = []
    if media_kind in (tr('video'), tr('image')):
        width = item.media_technical.get(tr('width'))
        height = item.media_technical.get(tr('height'))
        if missing(width) or missing(height):
            fields.append(tr('résolution'))
    if media_kind == tr('image'):
        return fields
    if missing(item.sort_values[2]):
        fields.append(tr('durée'))
    codec_column = 8 if media_kind == tr('audio') else 4
    if missing(item.sort_values[codec_column]):
        fields.append(tr('codec'))
    if media_kind == tr('video') and missing(item.sort_values[5]):
        fields.append(tr('FPS'))
    bitrate = (item.media_technical.get(tr('bitrate')) or item.sort_values[25]
               if media_kind == tr('audio') else item.sort_values[6])
    if missing(bitrate):
        fields.append(tr('débit'))
    return fields

class FileSortProxy(QSortFilterProxyModel):
    retired_columns = (10, 13, 15, 16, 36)
    state_filter = tr('Tous')
    search_mode = False
    folders_first = True
    sort_mode = 0
    hidden_last = False

    def set_name_filter(self, value):
        if value == getattr(self, 'name_filter', ''):
            return
        begin = getattr(self, 'beginFilterChange', None)
        end = getattr(self, 'endFilterChange', None)
        if callable(begin) and callable(end):
            begin()
            self.name_filter = value
            end(QSortFilterProxyModel.Direction.Rows)
        else:
            # Qt 6.8/6.9 remain supported by the package.
            self.name_filter = value
            self.invalidateFilter()

    def setSourceModel(self, model):
        self.file_model = model
        self.presentation = presentation_model(model, self) if model is not None else None
        super().setSourceModel(self.presentation)

    @staticmethod
    def media_is_incomplete(item):
        return bool(media_missing_fields(item))

    def filterAcceptsRow(self, row, parent):
        if not super().filterAcceptsRow(row, parent):
            return False
        item = self.file_model.rows[row]
        name_filter = getattr(self, 'name_filter', '').casefold()
        if name_filter and name_filter not in str(item.values[0]).casefold():
            return False
        from .media import kind
        query = getattr(self, tr('media_query'), {})
        if self.search_mode and item.is_dir and any(query.values()):
            return False
        if query.get(tr('kind')) and (not item.is_dir) and (kind(item) != query[tr('kind')]):
            return False
        if not item.is_dir:
            size_mib = query.get(tr('size_mib'), 0) or 0
            if size_mib and max(0, item.sort_values[1]) < size_mib * 1024 * 1024:
                return False
            width = item.media_technical.get(tr('width'), 0) or 0
            if query.get(tr('width')) and width < query[tr('width')]:
                return False
            if query.get(tr('duration')) and (not 0 <= item.sort_values[2] <= query[tr('duration')]):
                return False
            if query.get(tr('artist')) and query[tr('artist')].casefold() not in item.media_tags.get(tr('artist'), '').casefold():
                return False
        state = self.state_filter
        if state == tr('En erreur'):
            return bool(item.error or item.bitrate_error or item.validation_error)
        if state in (tr('Doublons'), tr('Doublons exacts')):
            return bool(item.duplicate_group)
        if state == tr('Médias incomplets'):
            return (item.is_dir and not self.search_mode) or self.media_is_incomplete(item)
        if state in (tr('Vidéos'), tr('Audio'), tr('Images')):
            return item.is_dir or kind(item) == {tr('Vidéos'): tr('video'), tr('Audio'): tr('audio'), tr('Images'): tr('image')}[state]
        return True

    def lessThan(self, left, right):
        left_item = self.file_model.rows[left.row()]
        right_item = self.file_model.rows[right.row()]
        if self.hidden_last:
            hidden_a = bool(left_item.is_hidden)
            hidden_b = bool(right_item.is_hidden)
            if hidden_a != hidden_b:
                return not hidden_a if self.sortOrder() == Qt.SortOrder.AscendingOrder else hidden_a
        if self.folders_first and left_item.is_dir != right_item.is_dir:
            return left_item.is_dir if self.sortOrder() == Qt.SortOrder.AscendingOrder else right_item.is_dir
        column = left.column()
        if column in (15, 16):
            a, b = left.data(Qt.ItemDataRole.UserRole), right.data(Qt.ItemDataRole.UserRole)
            if a != b:
                return a < b
        elif column == 3:
            def dimensions(item):
                import re
                width = item.media_technical.get('width')
                height = item.media_technical.get('height')
                if width and height:
                    return int(width), int(height)
                parts = re.findall(r'\d+', str(item.values[3]))
                return tuple(map(int, parts[:2])) if len(parts) >= 2 else (-1, -1)
            a, b = dimensions(left_item), dimensions(right_item)
            if a != b:
                return a < b
        elif column == 21:
            # TrackNumber may be '2/12'. Année/date is not a ReleaseYear role.
            def integer_role(value):
                try:
                    number = int(str(value).partition('/')[0].strip())
                    return number if -(1 << 31) <= number < (1 << 31) else 0
                except (ValueError, TypeError):
                    return 0
            a, b = integer_role(left_item.values[column]), integer_role(right_item.values[column])
            if a != b:
                return a < b
        elif column in (1, 2, 5, 6, 9, 12, 13, 14, 24, 25, 30, 36, 38, 39):
            a, b = left_item.sort_values[column], right_item.sort_values[column]
            if a != b:
                return a < b
        elif column != 0:
            # Media titles/artists/albums are human names, like Dolphin's
            # natural string roles. Protocol paths and technical codec fields
            # retain QString's exact comparison instead of a blanket collation.
            natural_roles = (18, 19, 20, 23, 27, 31, 33, 35)
            if column in (4, 8, 18, 19, 20, 23, 26, 27, 28, 35, 37):
                empty_a, empty_b = not str(left_item.values[column]), not str(right_item.values[column])
                if empty_a != empty_b:
                    return not empty_a
            mode = self.sort_mode if column in natural_roles else 1
            result = string_compare(str(left_item.values[column]), str(right_item.values[column]), mode)
            if result:
                return result < 0
        # Dolphin always breaks equal metadata values by the displayed name,
        # then by a unique location. New equal-sized items do not jump to the
        # end merely because they arrived after the initial listing.
        a, b = cached_natural_name_key(left_item), cached_natural_name_key(right_item)
        result = a.compare(b) if self.sort_mode == 0 else string_compare(a.name, b.name, self.sort_mode)
        if result:
            return result < 0
        from PySide6.QtCore import QUrl
        def real_name(item):
            return (getattr(item, 'real_name', '') or
                    (item.path.name if isinstance(item.path, Path) else QUrl(str(item.path)).fileName()))
        result = string_compare(real_name(left_item), real_name(right_item), self.sort_mode)
        if result:
            return result < 0
        def item_url(item):
            return QUrl.fromLocalFile(str(item.path)).toString() if isinstance(item.path, Path) else QUrl(str(item.path)).toString()
        return string_compare(item_url(left_item), item_url(right_item), 1) < 0

from .media_ui import MediaMixin, is_pdf, is_openable_document

class ActivityProgressBar(QProgressBar):
    """Notify the window when the foreground progress bar appears or hides."""

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.owner.sync_activity_progress_visibility)

    def hideEvent(self, event):
        super().hideEvent(event)
        QTimer.singleShot(0, self.owner.sync_activity_progress_visibility)


class ToolbarCommandGroup(QWidget):
    """A toolbar action whose preferred width never becomes a window minimum."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preferred_width = None
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def sizeHint(self):
        hint = super().sizeHint()
        if self.preferred_width is not None:
            hint.setWidth(self.preferred_width)
        return hint

    def setPreferredWidth(self, width):
        width = None if width is None else max(0, width)
        if width != self.preferred_width:
            self.preferred_width = width
            self.updateGeometry()


class Window(ContextMenuMixin, SessionMixin, ViewPolicyMixin, ExternalLocationsMixin, MediaMixin, TransferMixin, ExtraActionsMixin, DesktopMixin, PaneMixin, MovementMixin, EnhancementMixin, OrganizationMixin, JobMixin, QMainWindow):

    def __init__(self):
        super().__init__()
        self.runtime_tasks = RuntimeTaskRegistry(self)
        self.runtime_tasks.changed.connect(lambda _count: self.update_operations_button_visibility()
                                           if hasattr(self, 'job_button') else None)
        self.setObjectName(tr('mirivueMainWindow'))
        # Native event masks keep drawing/layout notifications out of Python.
        app = QApplication.instance()
        if app is not None:
            from .native_events import install_event_gate
            install_event_gate(app, self, (
                QEvent.Type.ApplicationFontChange, QEvent.Type.ThemeChange,
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick, QEvent.Type.MouseMove,
                QEvent.Type.Enter, QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
                QEvent.Type.FocusIn, QEvent.Type.Wheel, QEvent.Type.ContextMenu,
                QEvent.Type.Resize,
            ))
        # Dolphin leaves the window, menu bar and toolbar to the Qt/KDE style.
        # A stylesheet on QMainWindow installs QStyleSheetStyle over the entire
        # widget tree, including the native KF6 toolbar created below.
        self.thumbnail_worker = None
        self.move_worker = None
        self.worker = None
        self.folder_size_worker = None
        self.archive_extract_worker = None
        self._duration_workers = []
        self.init_jobs()
        self.scanning = False
        self.scan_queued = False
        self.search_active = False
        self.search_root = ''
        self.search_criteria = {}
        self.folder = None
        self.closing = False
        self.quit_requested = False
        self.tray = None
        self.duplicate_groups = []
        self.history = []
        self.history_position = -1
        self.pending_navigation = None
        self.parent_selection = None
        self.pending_external_files = []
        self.pending_external_properties = False
        self.notices = []
        self.settings = mirivue_settings()
        self.settings.setParent(self)
        self.setWindowTitle(tr('Dossier personnel — Mirivue'))
        file_menu = self.menuBar().addMenu(tr('Fichier'))
        edit_menu = self.menuBar().addMenu(tr('Édition'))
        view_menu = self.menuBar().addMenu(tr('Affichage'))
        go_menu = self.menuBar().addMenu(tr('Aller'))
        tools_menu = self.menuBar().addMenu(tr('Outils'))
        # Dolphin exposes one top-level Tools menu.  Mirivue-specific tools
        # remain available as clearly identified submenus instead of creating
        # additional top-level categories which alter KDE's conventional menu
        # structure.
        organize_menu = QMenu(tr('Métadonnées'), self)
        operations_menu = QMenu(tr('Opérations'), self)
        settings_menu = self.menuBar().addMenu(tr('Configuration'))
        help_menu = self.menuBar().addMenu(tr('Aide'))
        self.main_menus = dict(file=file_menu, edit=edit_menu, view=view_menu, go=go_menu,
                               tools=tools_menu, organize=organize_menu,
                               operations=operations_menu, settings=settings_menu, help=help_menu)
        self.search_action = edit_menu.addAction(tr('Rechercher…'), self.search_dialog)
        set_themed_action_icon(self.search_action, tr('edit-find'))
        self.search_action.setShortcut(QKeySequence(services.shortcut(tr('Ctrl+F'))))
        self.close_search_action = edit_menu.addAction(tr('Fermer la recherche'), self.clear_all_search)
        set_themed_action_icon(self.close_search_action, tr('edit-clear'))
        self.configure_action = settings_menu.addAction(tr('Configurer Mirivue…'), self.show_configuration)
        set_themed_action_icon(self.configure_action, tr('configure'))
        self.toolbar_action = settings_menu.addAction(tr('Configurer la barre d’outils…'), self.customize_toolbar)
        set_themed_action_icon(self.toolbar_action, tr('configure-toolbars'))
        self.columns_menu = StayingOpenMenu(tr('Choisir les colonnes'), self)
        set_themed_action_icon(self.columns_menu.menuAction(), tr('view-list-details'))
        view_menu.addMenu(self.columns_menu)
        self.settings.remove('view/status-bar')
        self.set_theme(self.settings.value('theme', tr('auto')))
        for menu in (file_menu, edit_menu, view_menu, go_menu, tools_menu, organize_menu, operations_menu, settings_menu, help_menu):
            menu.aboutToShow.connect(lambda current=menu: self.reserve_submenu_tree(current))
        self.guide_action = help_menu.addAction(tr('Guide de Mirivue'), self.show_features)
        self.guide_action.setShortcut(QKeySequence(tr('F1')))
        self.shortcuts_help_action = help_menu.addAction(tr('Raccourcis clavier'), self.show_shortcuts)
        self.analysis_help_action = help_menu.addAction(tr('Comprendre les informations techniques'), self.show_analysis_explainer)
        self.diagnostics_action = help_menu.addAction(tr('Diagnostic de Mirivue'), self.show_diagnostics)
        self.about_action = help_menu.addAction(tr('À propos de Mirivue'), self.show_about)
        self.resize(*initial_window_size())
        self.setWindowIcon(QIcon(str(Path(__file__).parent / tr('icons/mirivue.svg'))))
        central = QWidget()
        central.setObjectName(tr('mirivueCentral'))
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.setSpacing(7)
        title = QLabel(tr('<h2>Mirivue</h2>'))
        title.hide()
        self.choose = QPushButton(tr('Choisir un dossier…'))
        self.choose.hide()
        self.refresh = QAction(tr('Actualiser'), self)
        self.refresh.setEnabled(False)
        self.stop = QAction(tr('Arrêter le chargement du dossier'), self)
        self.stop.setEnabled(False)
        self.recursive = QAction(tr('Inclure les sous-dossiers'), self)
        self.recursive.setCheckable(True)
        operations_menu.addAction(self.refresh)
        operations_menu.addAction(self.stop)
        operations_menu.addAction(self.recursive)
        navigation = QHBoxLayout()
        navigation.setSpacing(5)
        self.home = QToolButton()
        self.back = QToolButton()
        self.forward = QToolButton()
        self.up = QToolButton()
        for button, title in ((self.home, tr('Dossier personnel')), (self.back, tr('Précédent')), (self.forward, tr('Suivant')), (self.up, tr('Dossier parent'))):
            button.setText(title)
        for button, icon in [(self.home, QStyle.StandardPixmap.SP_DirHomeIcon), (self.up, QStyle.StandardPixmap.SP_ArrowUp), (self.back, QStyle.StandardPixmap.SP_ArrowBack), (self.forward, QStyle.StandardPixmap.SP_ArrowForward)]:
            button.setToolTip(button.text())
            button.setAccessibleName(button.text())
            button.setText('')
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            button.setAutoRaise(True)
            theme_icon = {self.back: tr('go-previous'), self.forward: tr('go-next'), self.up: tr('go-up'), self.home: tr('go-home')}[button]
            button.setIcon(QIcon.fromTheme(theme_icon, self.style().standardIcon(icon)))
            navigation.addWidget(button)
        self.home.setIcon(QIcon.fromTheme(tr('go-home'), self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)))
        self.back_history_menu = QMenu(self.back)
        self.forward_history_menu = QMenu(self.forward)
        for button, menu, direction in ((self.back, self.back_history_menu, -1),
                                        (self.forward, self.forward_history_menu, 1)):
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            menu.aboutToShow.connect(lambda direction=direction, menu=menu:
                                     self.populate_navigation_history(menu, direction))
        navigation.addSpacing(14)
        self.refresh_button = QToolButton()
        self.refresh_button.setAutoRaise(True)
        self.refresh_button.setIcon(QIcon.fromTheme(tr('view-refresh'), self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)))
        self.refresh_button.setToolTip(tr('Actualiser le dossier (F5)'))
        self.refresh_button.setAccessibleName(tr('Actualiser'))
        self.refresh_button.clicked.connect(self.refresh.trigger)
        self.refresh.changed.connect(lambda: self.refresh_button.setEnabled(self.refresh.isEnabled()))
        self.refresh_button.setEnabled(self.refresh.isEnabled())
        navigation.addWidget(self.refresh_button)
        self.address = QLineEdit()
        self.address.setPlaceholderText(tr('Chemin du dossier — Entrée pour ouvrir'))
        self.address_stack = QStackedWidget()
        self.crumbs = QWidget()
        self.crumb_layout = QHBoxLayout(self.crumbs)
        self.crumb_layout.setContentsMargins(0, 0, 0, 0)
        self.crumb_layout.setSpacing(0)
        self.crumb_scroll = QScrollArea()
        self.crumb_scroll.setWidgetResizable(True)
        self.crumb_scroll.setWidget(self.crumbs)
        self.crumb_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.crumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.crumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.crumb_scroll.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, maximum: self.crumb_scroll.horizontalScrollBar().setValue(maximum))
        self.crumb_scroll.setFixedHeight(max(34, self.fontMetrics().height() + 12))
        self.crumb_scroll.setObjectName(tr('mirivuePathBar'))
        self.crumb_scroll.setViewportMargins(3, 2, 3, 2)
        self.address.setFixedHeight(self.crumb_scroll.height())
        self.address_stack.addWidget(self.crumb_scroll)
        self.address_stack.addWidget(self.address)
        navigation.addWidget(self.address_stack, 1)
        self.address_toggle = QToolButton()
        self.address_toggle.setAutoRaise(True)
        self.address_toggle.clicked.connect(lambda: self.set_address_mode(1 - self.address_stack.currentIndex()))
        navigation.addWidget(self.address_toggle)
        self.set_address_mode(self.settings.value('address/mode', 0, type=int) % 2)
        self.path_shortcut = QShortcut(QKeySequence(services.shortcut(tr('Ctrl+L'))), self)
        self.path_shortcut.activated.connect(self.show_active_pane_path_input)
        self.home.clicked.connect(lambda: self.navigate(str(Path.home())))
        self.back.clicked.connect(lambda: self.navigate_history(-1))
        self.forward.clicked.connect(lambda: self.navigate_history(1))
        self.up.clicked.connect(lambda: self.navigate(parent_location(self.folder)) if self.folder else None)
        self.address.returnPressed.connect(lambda: self.navigate(self.address.text()))
        # A real QToolBar is significant to Breeze: it registers this row as
        # the KDE tools area, applies the Header colour set used by Dolphin and
        # joins it visually to the server-side titlebar.  A plain QWidget is
        # painted as Window content and leaves the titlebar separator visible.
        from .native_places_view import create_native_toolbar
        self.navigation_bar = create_native_toolbar(self)
        self.navigation_bar.setObjectName(tr('mirivueNavigationBar'))
        self.navigation_bar.setMovable(False)
        self.navigation_bar.setFloatable(False)
        self.navigation_bar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        if self.navigation_bar.metaObject().className() != 'KToolBar':
            self.navigation_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonFollowStyle)
        # Keep the commands and KUrlNavigators as separate widget actions;
        # KToolBar can then size the path action using the native toolbar style.
        self.navigation_layout = navigation
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.navigation_bar)
        navigation.setContentsMargins(0, 0, 0, 0)
        self.navigation_content = QWidget(central)
        self.navigation_content.setObjectName(tr('mirivueNavigationContent'))
        self.navigation_content_layout = QVBoxLayout(self.navigation_content)
        self.navigation_content_layout.setContentsMargins(0, 0, 0, 0)
        self.navigation_content_layout.setSpacing(0)
        self.location = QLabel(tr('Choisissez un dossier pour commencer.'))
        self.location.setTextFormat(Qt.TextFormat.PlainText)
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location.hide()
        self.search_panel = QWidget(self.navigation_content)
        search_layout = QHBoxLayout(self.search_panel)
        search_layout.setContentsMargins(6, 4, 6, 4)
        search_layout.setSpacing(6)
        self.search = QLineEdit(self.search_panel)
        self.search.setMinimumWidth(180)
        self.search.setPlaceholderText(tr('Nom du fichier ou du dossier…'))
        self.search.setClearButtonEnabled(True)
        self.search.setToolTip(tr('Recherche par nom (avec * et ?) ou dans le contenu des fichiers texte locaux.'))
        search_layout.addWidget(self.search, 1)
        self.search_content = QCheckBox(tr('Contenu'), self.search_panel)
        self.search_content.setToolTip(tr('Chercher dans les fichiers texte locaux de 16 Mio au maximum.'))
        search_layout.addWidget(self.search_content)
        self.search_scope = QComboBox(self.search_panel)
        self.search_scope.addItem(tr('Dossier et sous-dossiers'), 'recursive')
        self.search_scope.addItem(tr('Dossier actif seulement'), 'current')
        self.search_scope.setToolTip(tr('Choisissez si la recherche doit parcourir les sous-dossiers.'))
        search_layout.addWidget(self.search_scope)
        self.search_kind = QComboBox(self.search_panel)
        for label, value in (
            (tr('Tous les éléments'), 'all'), (tr('Fichiers'), 'files'),
            (tr('Dossiers'), 'folders'), (tr('Vidéos'), 'video'),
            (tr('Audio'), 'audio'), (tr('Images'), 'image'),
            (tr('Autres fichiers'), 'other'),
        ):
            self.search_kind.addItem(label, value)
        self.search_kind.setToolTip(tr('Limiter les résultats à un type d’élément.'))
        search_layout.addWidget(self.search_kind)
        self.state_filter = QComboBox(self.search_panel)
        self.state_filter.addItems([tr('Tous les états'), tr('En erreur'), tr('Doublons exacts'), tr('Informations techniques manquantes')])
        self.state_filter.setToolTip(tr('« Doublons exacts » analyse le contenu complet des fichiers trouvés.'))
        search_layout.addWidget(self.state_filter)
        self.search_duplicates_manage = QPushButton(tr('Gérer les doublons…'), self.search_panel)
        self.search_duplicates_manage.setToolTip(tr('Choisir, pour chaque groupe, le fichier à conserver.'))
        self.search_duplicates_manage.clicked.connect(self.choose_duplicate_keeper)
        self.search_duplicates_manage.hide()
        search_layout.addWidget(self.search_duplicates_manage)
        self.search_more = QPushButton(tr('Plus de critères…'), self.search_panel)
        self.search_more.setToolTip(tr('Ajouter des critères de métadonnées : artiste, largeur ou durée.'))
        self.search_more.clicked.connect(self.media_search)
        search_layout.addWidget(self.search_more)
        self.search_start = QPushButton(tr('Rechercher'), self.search_panel)
        self.search_start.setIcon(themed_icon(tr('edit-find'), self, QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.search_start.clicked.connect(self.start_unified_search)
        search_layout.addWidget(self.search_start)
        self.search_close = QToolButton(self.search_panel)
        self.search_close.setIcon(themed_icon(tr('window-close'), self, QStyle.StandardPixmap.SP_DialogCloseButton))
        self.search_close.setToolTip(tr('Fermer la recherche et revenir au dossier'))
        self.search_close.clicked.connect(self.close_search)
        search_layout.addWidget(self.search_close)
        self.search_escape = QShortcut(QKeySequence(tr('Escape')), self.search_panel)
        self.search_escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.search_escape.activated.connect(self.close_search)
        self.live_search_timer = QTimer(self)
        self.live_search_timer.setSingleShot(True)
        self.live_search_timer.setInterval(300)
        self.live_search_timer.timeout.connect(self.start_live_search)
        self.search.textChanged.connect(self.schedule_live_search)
        self.search_scope.currentIndexChanged.connect(self.schedule_live_search)
        self.search_kind.currentIndexChanged.connect(self.schedule_live_search)
        self.search_content.toggled.connect(self.schedule_live_search)
        self.search_panel.hide()
        self.search.returnPressed.connect(self.start_unified_search)
        self.navigation_content_layout.addWidget(self.search_panel)
        self.filter_panel = QWidget(self.navigation_content)
        filter_layout = QHBoxLayout(self.filter_panel)
        filter_layout.setContentsMargins(6, 4, 6, 4)
        filter_layout.addWidget(QLabel(tr('Filtre :'), self.filter_panel))
        self.quick_filter = QLineEdit(self.filter_panel)
        self.quick_filter.setPlaceholderText(tr('Filtrer les noms du dossier affiché…'))
        self.quick_filter.setClearButtonEnabled(True)
        self.quick_filter.textChanged.connect(self.apply_quick_filter)
        filter_layout.addWidget(self.quick_filter, 1)
        filter_close = QToolButton(self.filter_panel)
        filter_close.setIcon(themed_icon(tr('window-close'), self, QStyle.StandardPixmap.SP_DialogCloseButton))
        filter_close.clicked.connect(self.close_quick_filter)
        filter_layout.addWidget(filter_close)
        self.filter_escape = QShortcut(QKeySequence(tr('Escape')), self.filter_panel)
        self.filter_escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.filter_escape.activated.connect(self.close_quick_filter)
        self.filter_panel.hide()
        self.navigation_content_layout.addWidget(self.filter_panel)
        self.model = VideoModel(self.settings.value('view/date-format', 'locale'))
        self.model.path_edit_allowed = lambda path: not self.paths_locked([path])
        self.proxy = FileSortProxy()
        self.proxy.sort_mode = self.settings.value('sorting/mode', 0, type=int)
        self.proxy.hidden_last = self.settings.value('sorting/hidden-last', False, type=bool)
        self.proxy.folders_first = self.settings.value('sorting/folders-first', True, type=bool)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.table = DetailsView()
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setModel(self.proxy)
        self.external_watcher = QFileSystemWatcher(self)
        self.external_timer = QTimer(self)
        self.external_timer.setSingleShot(True)
        self.external_timer.setInterval(500)
        self.external_timer.timeout.connect(self.sync_external_names)
        self.external_watcher.directoryChanged.connect(lambda _: self.external_timer.start())
        self.visible_watcher = QFileSystemWatcher(self)
        self.visible_timer = QTimer(self)
        self.visible_timer.setSingleShot(True)
        self.visible_timer.setInterval(350)
        self.visible_timer.timeout.connect(self.sync_visible_directories)
        self.visible_watcher.directoryChanged.connect(lambda *_: self.visible_timer.start())
        self._visible_snapshots = {}
        self._visible_workers = []
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.apply_details_zoom()
        for column, width in enumerate([240, 85, 85, 110, 90, 65, 160, 125, 100, 65, 125, 175, 125, 150, 240]):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.column_actions = []
        for column, name in enumerate(HEADERS):
            if column in (10, 12, 13, 15, 16, 36):
                self.column_actions.append(None)
                continue
            action = QAction(name, self.columns_menu)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda visible, c=column: self.set_column_visible(c, visible))
            self.column_actions.append(action)
        self.add_grouped_column_actions(self.columns_menu)
        self.columns_menu.addSeparator()
        self.columns_menu.addAction(tr('Réinitialiser les colonnes'), self.reset_columns)
        self.columns_menu.aboutToShow.connect(self.sync_columns_menu)
        header.customContextMenuRequested.connect(lambda pos: self.show_header_menu(header, pos))
        self.incomplete_media_action = QAction(tr('Médias incomplets (0)'), self)
        set_themed_action_icon(self.incomplete_media_action, tr('document-properties'))
        self.incomplete_media_action.setToolTip(tr('Affiche les médias auxquels il manque une durée, une résolution, un codec, des FPS ou un débit.'))
        self.incomplete_media_action.triggered.connect(self.show_incomplete_media)
        self.delete_button = QAction(tr('Mettre à la corbeille'), self)
        # Moving to Trash is reversible; reserve the red destructive icon for
        # the explicit permanent-delete command.
        set_themed_action_icon(self.delete_button, tr('trash-empty'))
        self.delete_button.triggered.connect(lambda: self.delete_selected(tr('trash')))
        self.delete_button.setShortcut(QKeySequence(tr('Delete')))
        self.duplicate_action = QAction(tr('Rechercher les doublons exacts'), self)
        self.duplicate_action.triggered.connect(self.start_duplicate_scan)
        set_themed_action_icon(self.duplicate_action, tr('edit-find'))
        self.keep_one_action = QAction(tr('Choisir le fichier à conserver…'), self)
        self.keep_one_action.triggered.connect(self.choose_duplicate_keeper)
        set_themed_action_icon(self.keep_one_action, tr('edit-select'))
        date_layout_new = self.settings.value('columns-pane-left-v1') is None and self.settings.value('columns-v7') is None
        saved = self.settings.value('columns-pane-left-v1', self.settings.value('columns-v7', self.settings.value('columns-v6')))
        if saved is None:
            saved = self.settings.value('columns-v5', self.settings.value('columns-v4'))
        if saved is not None:
            header.restoreState(saved)
            if self.settings.value('columns-pane-left-role-count', 37, type=int) < len(HEADERS):
                for column in (37, 38, 39):
                    self.table.setColumnHidden(column, True)
        else:
            for column in range(1, len(HEADERS)):
                self.table.setColumnHidden(column, column not in (1, 2, 14))
        self.table.setColumnHidden(10, True)
        self.table.setColumnHidden(12, True)
        self.table.setColumnHidden(15, True)
        self.table.setColumnHidden(16, True)
        self.table.setColumnHidden(36, True)
        # Header state also contains a legacy sort indicator. Folder startup
        # applies the shared sort, or the explicitly enabled per-folder sort.
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.setColumnHidden(0, False)
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        if date_layout_new:
            self.table.setColumnHidden(14, False)
            self.table.setColumnWidth(14, 175)
            header.moveSection(header.visualIndex(14), header.visualIndex(1) + 1)
        # Keep the file name at the leading edge, as Dolphin does.  Normalize
        # saved legacy layouts too, then leave every other section draggable.
        if header.visualIndex(0) != 0:
            header.moveSection(header.visualIndex(0), 0)
        header.setFirstSectionMovable(False)
        self.table.setColumnWidth(15, 150)
        self.filesystem = QFileSystemModel(self)
        self.filesystem.setReadOnly(True)
        self.filesystem.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Hidden)
        self.filesystem.setRootPath(tr('/'))
        self.browser = QTreeView()
        self.browser.setModel(self.filesystem)
        self.browser.setHeaderHidden(True)
        for column in range(1, self.filesystem.columnCount()):
            self.browser.hideColumn(column)
        self.browser.setMinimumWidth(180)
        self.browser.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.browser.clicked.connect(lambda index: self.navigate(self.filesystem.filePath(index)))
        splitter = QSplitter()
        splitter.setObjectName(tr('mirivueMainSplitter'))
        sidebar = QWidget()
        self.sidebar = sidebar
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_panels = QSplitter(Qt.Orientation.Vertical)
        self.sidebar_panels.addWidget(self.browser)
        self.browser.hide()
        places_panel = QWidget()
        places_panel.setObjectName(tr('mirivuePlacesPanel'))
        places_panel.setAutoFillBackground(True)
        places_layout = QVBoxLayout(places_panel)
        self.places_layout = places_layout
        places_layout.setContentsMargins(0, 0, 0, 0)
        self.native_places = None
        self.native_places_error = None
        if (services.name == 'linux'
                and os.environ.get('QT_QPA_PLATFORM', '').casefold() not in {'offscreen', 'minimal'}):
            try:
                from .native_places_view import NativePlacesView
                self.native_places = NativePlacesView(
                    places_panel, self.navigate, self.native_drop_completed,
                    self.open_place_in_split_view, self.open_new_tab, self.open_new_tab,
                    self.open_place_in_new_window,
                    self.report_native_place_error, self.refresh_trash_panes,
                    self.trash_view_has_items)
                places_layout.addWidget(self.native_places.widget)
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                self.native_places_error = str(error)
                record_tool_failure('KFilePlacesView', error)
                places_layout.addWidget(QLabel(tr('Panneau Emplacements KDE indisponible.')))
        self.places_panel = places_panel
        self.sidebar_panels.addWidget(places_panel)
        side_layout.addWidget(self.sidebar_panels, 1)
        self.operations_sidebar_slot = QWidget(sidebar)
        self.operations_sidebar_slot.setObjectName(tr('mirivueOperationsSidebarSlot'))
        operations_sidebar_layout = QHBoxLayout(self.operations_sidebar_slot)
        operations_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        operations_sidebar_layout.setSpacing(0)
        side_layout.addWidget(self.operations_sidebar_slot)
        self.operations_sidebar_slot.hide()
        self.reload_places()
        splitter.addWidget(sidebar)
        self.icons = IconView()
        self.icons.setModel(self.proxy)
        self.icons.setViewMode(QListView.ViewMode.IconMode)
        self.icons.setResizeMode(QListView.ResizeMode.Adjust)
        self.icons.setMovement(QListView.Movement.Snap)
        self.icons.setIconSize(QSize(64, 64))
        self.icons.setGridSize(QSize(208, 155))
        self.icons.setWordWrap(True)
        self.icons.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.icons.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.icons.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.icons.activated.connect(self.open_video)
        self.icons.customContextMenuRequested.connect(self.context_menu)
        self.compact = IconView()
        self.compact.setModel(self.proxy)
        self.compact.setViewMode(QListView.ViewMode.ListMode)
        self.compact.setFlow(QListView.Flow.TopToBottom)
        self.compact.setWrapping(True)
        self.compact.setResizeMode(QListView.ResizeMode.Adjust)
        self.compact.setMovement(QListView.Movement.Static)
        native_small_icon = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize, None, self.compact)
        self.compact.setIconSize(QSize(native_small_icon, native_small_icon))
        self.compact.setUniformItemSizes(True)
        self.compact.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.compact.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.compact.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.compact.activated.connect(self.open_video)
        self.compact.customContextMenuRequested.connect(self.context_menu)
        for view in (self.table, self.icons, self.compact):
            view.setDragEnabled(True)
            view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
            view.drag_handler = self.start_file_drag
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.table)
        self.content_stack.addWidget(self.icons)
        self.content_stack.addWidget(self.compact)
        self.view_buttons = QButtonGroup(self)
        self.details_button = QToolButton()
        self.icons_button = QToolButton()
        self.compact_button = QToolButton()
        for mode, button, title, icon, fallback in [(0, self.details_button, tr('Détails'), tr('view-list-tree'), QStyle.StandardPixmap.SP_FileDialogDetailedView), (1, self.icons_button, tr('Icônes'), tr('view-list-icons'), QStyle.StandardPixmap.SP_FileDialogContentsView), (2, self.compact_button, tr('Vue compacte'), tr('view-list-details'), QStyle.StandardPixmap.SP_FileDialogContentsView)]:
            button.setIcon(themed_icon(icon, self, fallback))
            button.setCheckable(True)
            button.setToolTip(title)
            button.setAccessibleName(title)
            button.setAutoRaise(True)
            self.view_buttons.addButton(button, mode)
            button.clicked.connect(lambda checked=False, target=mode: self.change_view(target))
        initial_mode = self.settings.value('view/mode', 1, type=int) % 3
        self.content_stack.setCurrentIndex(initial_mode)
        if self.view_buttons.button(initial_mode) is not None:
            self.view_buttons.button(initial_mode).setChecked(True)
        self.hidden = QToolButton()
        self.hidden.setAutoRaise(True)
        self.hidden.setIcon(themed_icon(tr('view-hidden'), self, QStyle.StandardPixmap.SP_FileDialogInfoView))
        self.hidden.setAccessibleName(tr('Éléments cachés'))
        self.hidden.setCheckable(True)
        self.hidden.setToolTip(tr('Afficher ou masquer les éléments cachés (Ctrl+H)'))
        hide_hidden_on_startup = self.settings.value('view/hide-hidden-on-startup', False, type=bool)
        self.hidden.setChecked(False if hide_hidden_on_startup else self.settings.value('view/hidden', False, type=bool))
        self.apply_hidden_filter()
        self.hidden.toggled.connect(self.change_hidden)
        self.hidden_shortcut = QShortcut(QKeySequence(services.shortcut(tr('Ctrl+H'))), self)
        self.hidden_shortcut.activated.connect(self.hidden.toggle)
        navigation.addWidget(self.icons_button)
        navigation.addWidget(self.compact_button)
        navigation.addWidget(self.details_button)
        navigation.addWidget(self.hidden)
        self.icons_view_action = view_menu.addAction(tr('Vue en icônes'), lambda: self.change_view(1))
        set_themed_action_icon(self.icons_view_action, tr('view-list-icons'))
        self.icons_view_action.setShortcut(QKeySequence(tr('Ctrl+1')))
        self.icons_view_action.setCheckable(True)
        self.compact_view_action = view_menu.addAction(tr('Vue compacte'), lambda: self.change_view(2))
        set_themed_action_icon(self.compact_view_action, tr('view-list-details'))
        self.compact_view_action.setShortcut(QKeySequence(tr('Ctrl+2')))
        self.compact_view_action.setCheckable(True)
        self.details_view_action = view_menu.addAction(tr('Vue détaillée'), lambda: self.change_view(0))
        set_themed_action_icon(self.details_view_action, tr('view-list-tree'))
        self.details_view_action.setShortcut(QKeySequence(tr('Ctrl+3')))
        self.details_view_action.setCheckable(True)
        self.view_mode_group = QActionGroup(self)
        self.view_mode_group.setExclusive(True)
        self.view_mode_group.addAction(self.details_view_action)
        self.view_mode_group.addAction(self.icons_view_action)
        self.view_mode_group.addAction(self.compact_view_action)
        self.details_view_action.setChecked(self.content_stack.currentIndex() == 0)
        self.icons_view_action.setChecked(self.content_stack.currentIndex() == 1)
        self.compact_view_action.setChecked(self.content_stack.currentIndex() == 2)
        self.view_mode_button = QToolButton()
        self.view_mode_button.setAutoRaise(True)
        self.view_mode_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mode_popup = QMenu(self.view_mode_button)
        for mode_action in (self.icons_view_action, self.compact_view_action, self.details_view_action):
            mode_popup.addAction(mode_action)
        self.view_mode_button.setMenu(mode_popup)
        self.view_mode_button.setToolTip(tr('Mode d’affichage'))
        self.view_mode_button.setAccessibleName(tr('Mode d’affichage'))
        def update_mode_button():
            active = next((a for a in mode_popup.actions() if a.isChecked()), self.icons_view_action)
            fallback = {self.icons_view_action: self.icons_button, self.compact_view_action: self.compact_button, self.details_view_action: self.details_button}[active]
            self.view_mode_button.setIcon(active.icon() if not active.icon().isNull() else fallback.icon())
            self.view_mode_button.setToolTip(tr('Mode d’affichage : ') + active.text())
        for mode_action in mode_popup.actions():
            mode_action.toggled.connect(update_mode_button)
        update_mode_button()
        self.hidden_action = view_menu.addAction(tr('Afficher les éléments cachés'))
        set_themed_action_icon(self.hidden_action, tr('view-hidden'))
        self.hidden_action.setCheckable(True)
        self.hidden_action.setChecked(self.hidden.isChecked())
        self.hidden_action.toggled.connect(self.hidden.setChecked)
        self.hidden.toggled.connect(self.hidden_action.setChecked)
        self.preview_action = QAction(tr('Afficher les miniatures'), self)
        set_themed_action_icon(self.preview_action, tr('view-preview'))
        self.preview_action.setCheckable(True)
        self.preview_action.setChecked(self.settings.value('view/previews', False, type=bool))
        self.model.show_thumbnails = self.preview_action.isChecked()
        self.apply_icon_zoom()
        self.apply_compact_zoom()
        self.preview_action.toggled.connect(self.toggle_previews)
        view_menu.addAction(self.preview_action)
        self.preview_button = QToolButton()
        self.preview_button.setAutoRaise(True)
        self.preview_button.setIcon(themed_icon(tr('view-preview'), self, QStyle.StandardPixmap.SP_FileIcon))
        self.preview_button.setCheckable(True)
        self.preview_button.setToolTip(tr('Afficher ou masquer les miniatures. Ce choix est partagé entre les dossiers, sauf si leur mémorisation séparée est activée. Les emplacements spéciaux conservent leurs réglages.'))
        self.preview_button.setAccessibleName(tr('Afficher ou masquer les miniatures'))
        self.preview_button.setChecked(self.preview_action.isChecked())
        self.preview_button.toggled.connect(self.preview_action.setChecked)
        self.preview_action.toggled.connect(self.preview_button.setChecked)
        navigation.addWidget(self.preview_button)
        self.search_button = QToolButton()
        self.search_button.setAutoRaise(True)
        self.search_button.setIcon(themed_icon(tr('edit-find'), self, QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.search_button.setToolTip(tr('Rechercher (Ctrl+F)'))
        self.search_button.setAccessibleName(tr('Rechercher'))
        self.search_button.setCheckable(True)
        self.search_button.clicked.connect(self.toggle_search)
        navigation.addWidget(self.search_button)
        self.toolbar_overflow = QToolButton()
        self.toolbar_overflow.setObjectName(tr('mirivueToolbarOverflow'))
        self.toolbar_overflow.setText(tr('⋯'))
        self.toolbar_overflow.setToolTip(tr('Autres commandes'))
        self.toolbar_overflow.setAccessibleName(tr('Autres commandes'))
        self.toolbar_overflow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.toolbar_overflow_menu = QMenu(self.toolbar_overflow)
        self.toolbar_overflow.setMenu(self.toolbar_overflow_menu)
        self._toolbar_overflow_widgets = []
        for name, title in ((tr('hidden'), tr('Éléments cachés')), (tr('preview_button'), tr('Miniatures')), (tr('preview_panel_button'), tr('Panneau d’aperçu'))):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            action = self.toolbar_overflow_menu.addAction(title)
            action.setCheckable(hasattr(widget, tr('isCheckable')) and widget.isCheckable())
            if action.isCheckable():
                action.setChecked(widget.isChecked())
                widget.toggled.connect(action.setChecked)
                action.triggered.connect(lambda checked=False, target=widget: target.click())
            elif hasattr(widget, tr('showPopup')):
                action.triggered.connect(widget.showPopup)
            self._toolbar_overflow_widgets.append((name, widget))
        for view in (self.table, self.icons, self.compact):
            view.viewport().installEventFilter(self)
        self.pane_splitter = QSplitter()
        self.pane_splitter.setObjectName(tr('mirivuePaneSplitter'))
        self.pane_splitter.setChildrenCollapsible(False)
        self.pane_splitter.addWidget(self.content_stack)
        self.tab_host = QWidget()
        tab_layout = QVBoxLayout(self.tab_host)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)
        self.tab_bar = DolphinTabBar(self, self.tab_host)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setTabsClosable(self.settings.value('tabs/show-close-buttons', True, type=bool))
        self.tab_bar.setMovable(True)
        self.tab_bar.setVisible(self.settings.value('tabs/always-show-bar', False, type=bool))
        tab_layout.addWidget(self.tab_bar)
        tab_layout.addWidget(self.pane_splitter, 1)
        splitter.addWidget(self.tab_host)
        # A Places dock keeps its chosen width when the main window grows;
        # give the file views the stretch instead of scaling both panes.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 1220])
        self.main_splitter = splitter
        self._sidebar_width_restored = False
        self._sidebar_width_save_timer = QTimer(self)
        self._sidebar_width_save_timer.setSingleShot(True)
        self._sidebar_width_save_timer.setInterval(200)
        self._sidebar_width_save_timer.timeout.connect(self.save_sidebar_width)
        self.left_toolbar_group = ToolbarCommandGroup(self.navigation_bar)
        self.left_toolbar_group.setObjectName(tr('mirivueToolbarLeft'))
        self.left_toolbar_layout = QHBoxLayout(self.left_toolbar_group)
        self.left_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.left_toolbar_layout.setSpacing(2)
        self.right_toolbar_group = ToolbarCommandGroup(self.navigation_bar)
        self.right_toolbar_group.setObjectName(tr('mirivueToolbarRight'))
        self.right_toolbar_layout = QHBoxLayout(self.right_toolbar_group)
        self.right_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.right_toolbar_layout.setSpacing(2)
        self.main_splitter.splitterMoved.connect(self.align_path_during_drag)
        self.main_splitter.splitterMoved.connect(self.schedule_sidebar_width_save)
        self.pane_splitter.splitterMoved.connect(self.align_path_during_drag)
        self.navigation_content_layout.addWidget(splitter, 1)
        layout.addWidget(self.navigation_content, 1)
        self.update_navigation()
        self.update_delete_button()
        self.bar = ActivityProgressBar(self)
        self.bar.hide()
        # KIO changes the progress text as the percentage advances.  Its
        # size hint must not resize Places and the two file-pane splitters.
        self.bar.setMinimumWidth(0)
        self.bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.bar.setMaximumWidth(380)
        # Listing a normal folder is usually quicker than the eye can follow.
        # Delay its indicator so startup and short navigations do not flash.
        # Explicit searches and file operations continue to report at once.
        self.folder_load_progress_timer = QTimer(self)
        self.folder_load_progress_timer.setSingleShot(True)
        self.folder_load_progress_timer.setInterval(450)
        self.folder_load_progress_timer.timeout.connect(self.show_delayed_folder_progress)
        self.folder_load_progress_visible = False
        self.summary = QLabel(tr('0 vidéo'))
        self.summary.hide()
        self.errors = QPushButton(tr('Erreurs'))
        self.errors.setEnabled(False)
        self.errors.hide()
        self.errors_slot = QWidget()
        errors_slot_layout = QHBoxLayout(self.errors_slot)
        errors_slot_layout.setContentsMargins(0, 0, 0, 0)
        errors_slot_layout.setSpacing(0)
        # Keep contextual actions at their natural width; stretching these
        # buttons across the whole Places pane makes rare alerts dominate it.
        self.errors.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        errors_slot_layout.addWidget(self.errors)
        self.errors_slot.hide()
        # Keep errors attached to the sidebar, so the footer below the file
        # panels remains available for the panel status information.
        self.places_layout.addWidget(self.errors_slot)
        self.activity_message_label = QLabel()
        self.activity_message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_message_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.activity_message_label.hide()
        self.places_layout.addWidget(self.activity_message_label)
        self.activity_message_timer = QTimer(self)
        self.activity_message_timer.setSingleShot(True)
        self.activity_message_timer.timeout.connect(self.clear_activity_message)
        self.places_layout.addWidget(self.bar)
        self.create_job_footer(self.places_layout)
        self.create_transfer_footer(self.places_layout)
        self.resume_button = QPushButton(tr('Reprendre les tâches interrompues'))
        self.resume_button.setIcon(themed_icon(tr('media-playback-start'), self, QStyle.StandardPixmap.SP_MediaPlay))
        self.resume_button.clicked.connect(self.resume_operations)
        self.resume_button.hide()
        self.resume_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.places_layout.addWidget(self.resume_button)
        self.resume_action = operations_menu.addAction(tr('Reprendre les tâches interrompues'), self.resume_operations)
        set_themed_action_icon(self.resume_action, tr('media-playback-start'))
        self.clear_pending_action = operations_menu.addAction(tr('Supprimer les tâches en attente de reprise'), self.discard_pending)
        set_themed_action_icon(self.clear_pending_action, tr('edit-clear-list'))
        self.jobs_action = operations_menu.addAction(tr('Opérations en cours et historique'), self.show_jobs)
        set_themed_action_icon(self.jobs_action, tr('view-list-details'))
        self.open_action = file_menu.addAction(tr('Ouvrir…'), lambda: self.open_selected() if self.selected_indexes() else self.pick())
        set_themed_action_icon(self.open_action, tr('document-open'))
        self.new_window_action = file_menu.addAction(tr('Nouvelle fenêtre'),
            lambda: self.open_place_in_new_window(self.folder or str(Path.home())))
        self.new_window_action.setShortcut(QKeySequence.StandardKey.New)
        set_themed_action_icon(self.new_window_action, 'window-new')
        self.new_folder_action = file_menu.addAction(tr('Nouveau dossier…'), self.create_folder)
        set_themed_action_icon(self.new_folder_action, tr('folder-new'))
        self.new_folder_action.setShortcut(QKeySequence(tr('Ctrl+Shift+N')))
        file_menu.aboutToShow.connect(lambda: self.new_folder_action.setEnabled(bool(self.folder) and not self.scanning and not self.is_trash_view() and not self.is_archive_view()))
        self.rename_action = file_menu.addAction(tr('Renommer'), self.rename_f2)
        set_themed_action_icon(self.rename_action, tr('edit-rename'))
        self.rename_action.setShortcut(QKeySequence(tr('F2')))
        self.properties_action = file_menu.addAction(tr('Propriétés'), self.basic_properties)
        set_themed_action_icon(self.properties_action, tr('document-properties'))
        self.properties_action.setShortcut(QKeySequence(tr('Alt+Return')))
        self.copy_folder_name_action = edit_menu.addAction(
            tr('Copier le nom du dossier actif'), self.copy_current_folder_name)
        self.load_library()
        self.choose.clicked.connect(self.pick)
        self.refresh.triggered.connect(self.refresh_current_view)
        self.refresh.setShortcut(QKeySequence(tr('F5')))
        self.stop.triggered.connect(self.cancel)
        self.table.activated.connect(self.open_video)
        self.table.customContextMenuRequested.connect(self.context_menu)
        self.errors.clicked.connect(self.show_errors)
        self.sync_activity_progress_visibility()
        self.disk_timer = QTimer(self)
        self.disk_timer.timeout.connect(self.update_disk_space)
        self.disk_timer.start(15000)
        self.menu_visibility = MenuVisibility(self, self.navigation_bar, navigation, view_menu)
        QTimer.singleShot(0, self.refresh_symbolic_icons)
        QApplication.instance().paletteChanged.connect(self.refresh_symbolic_icons)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(tr('Mirivue — Your Media, Clearly Organised'))
        tray_menu = QMenu(self)
        tray_menu.addAction(tr('Afficher Mirivue'), self.restore_window)
        tray_menu.addSeparator()
        tray_menu.addAction(tr('Quitter Mirivue'), self.request_quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.quit_action = file_menu.addAction(tr('Quitter Mirivue'), self.request_quit)
        self.quit_action.setShortcut(QKeySequence(services.shortcut(tr('Ctrl+Q'))))
        self.tray_watch = QTimer(self)
        self.tray_watch.setInterval(3000)
        self.tray_watch.timeout.connect(self.check_tray_available)
        self.tray_watch.start()
        self.init_panes(navigation, view_menu)
        self.init_tabs(file_menu)
        self.init_terminal_panel(view_menu)
        self.init_transfers(edit_menu)
        self.init_extra_actions(organize_menu, operations_menu)
        self.init_media(view_menu, settings_menu, organize_menu, navigation)
        self.install_dolphin_shortcuts(file_menu, edit_menu, view_menu, go_menu)
        self.init_shortcut_configuration(settings_menu)
        self.refresh_toolbar_overflow()
        self.init_organization(file_menu, organize_menu, view_menu, operations_menu)
        self.init_desktop(navigation, settings_menu)
        self.rebuild_main_menus()
        self.startup_split_action = QAction(tr('Toujours démarrer en mode scindé'), self)
        self.startup_split_action.setCheckable(True)
        self.startup_split_action.setChecked(self.settings.value('startup/split', False, type=bool))
        self.startup_split_action.toggled.connect(lambda enabled: self.settings.setValue('startup/split', enabled))

    def set_theme(self, mode):
        # The platform theme owns the palette and active/inactive colour sets.
        # Replacing QApplication's palette here prevents GNOME sessions from
        # painting the same KDE widgets as Dolphin.
        self.settings.setValue('theme', tr('auto'))
        self.refresh_symbolic_icons()
        if hasattr(self, tr('desktop_watcher')):
            self.follow_desktop(force=True)

    def show_activity_message(self, message, timeout=0):
        """Show feedback in Places or temporarily in the existing pane footer."""
        if not hasattr(self, 'activity_message_label'):
            return
        message = str(message or '')
        self.activity_message_label.setText(message)
        self.activity_message_label.setToolTip(message)
        self.activity_message_label.setVisible(bool(message) and self.places_panel.isVisible())
        self.sync_feedback_in_pane_footers()
        self.activity_message_timer.stop()
        if message and timeout:
            self.activity_message_timer.start(timeout)
        self.update_activity_entry_points()

    def clear_activity_message(self):
        if not hasattr(self, 'activity_message_label'):
            return
        self.activity_message_label.clear()
        self.activity_message_label.hide()
        self.sync_feedback_in_pane_footers()
        self.update_activity_entry_points()

    def sync_feedback_in_pane_footers(self):
        """Replace one existing footer label without changing the view height."""
        message = (self.activity_message_label.text() if not self.places_panel.isVisible() else '')
        for pane in getattr(self, 'panes', ()):
            summary = getattr(pane, '_normal_summary_text', pane.summary_label._full_text)
            displayed = message if message and pane is self.bound_pane else summary
            pane.summary_label.set_full_text(displayed, Qt.TextElideMode.ElideRight)
            pane.summary_label.setToolTip(displayed)

    def folder_loads_active(self):
        """Return whether a pane is listing a folder, excluding searches."""
        return any(
            pane.scanning and isinstance(pane.worker, (Scanner, KioScanner))
            for pane in getattr(self, 'panes', ())
        )

    def searches_active(self):
        return any(
            pane.scanning and isinstance(pane.worker, RecursiveSearchWorker)
            for pane in getattr(self, 'panes', ())
        )

    def schedule_folder_progress(self):
        """Reveal folder-loading progress only when the work lasts long enough."""
        if self.folder_load_progress_visible or self.searches_active():
            return
        if self.folder_loads_active() and not self.folder_load_progress_timer.isActive():
            self.folder_load_progress_timer.start()

    def show_delayed_folder_progress(self):
        if not self.folder_loads_active() or self.searches_active():
            return
        self.folder_load_progress_visible = True
        self.bar.show()
        self.sync_activity_progress_visibility()

    def refresh_scan_progress_visibility(self):
        """Keep one coherent indicator across both panes."""
        if self.searches_active():
            self.folder_load_progress_timer.stop()
            self.folder_load_progress_visible = False
            self.bar.show()
        elif self.folder_loads_active():
            self.schedule_folder_progress()
        else:
            self.folder_load_progress_timer.stop()
            self.folder_load_progress_visible = False
            self.bar.hide()
        self.sync_activity_progress_visibility()

    def sync_activity_progress_visibility(self):
        """Display one priority progression: foreground, transfer, then task."""
        if not hasattr(self, 'bar'):
            return
        foreground = self.bar.isVisible()
        transfer = any(not job.get('native') for job in self.pending_transfers()) if hasattr(self, 'transfer_history') else False
        task = self.jobs_busy() if hasattr(self, 'job_queue') else False
        if hasattr(self, 'transfer_label'):
            self.transfer_label.setVisible(transfer and not foreground)
            self.transfer_bar.setVisible(transfer and not foreground)
        if hasattr(self, 'job_label'):
            show_task = task and not foreground and not transfer
            self.job_label.setVisible(show_task)
            self.job_progress.setVisible(show_task)
        self.update_activity_entry_points()

    def update_activity_entry_points(self):
        if not hasattr(self, 'job_button'):
            return
        analysis_running = self.jobs_busy() if hasattr(self, 'job_queue') else False
        transfer_running = bool(self.pending_transfers()) if hasattr(self, 'transfer_history') else False
        live = analysis_running or transfer_running
        available = bool(
            self.job_history
            or getattr(self, 'transfer_history', [])
            or self.runtime_tasks.descriptions()
        )
        native_jobs = [job for job in self.pending_transfers() if job.get('native')]
        tooltip = (trf('\x1f0\x1f opération(s) de fichiers en cours — détails et arrêt dans Opérations ou Plasma.', len(native_jobs)) if native_jobs
                   else self.transfer_label.text() if transfer_running and hasattr(self, 'transfer_label')
                   else self.job_label.text() if analysis_running and hasattr(self, 'job_label')
                   else tr('Opérations en cours'))
        self.job_button.setToolTip(tooltip)
        self.job_button.setVisible(live and not self.sidebar.isHidden())
        self.operations_sidebar_slot.setVisible(live and not self.sidebar.isHidden())
        if hasattr(self, 'jobs_action'):
            self.jobs_action.setEnabled(available)
        if hasattr(self, 'activity_fallback_button'):
            self.activity_fallback_button.setToolTip(tooltip)
            self.activity_fallback_button.setVisible(live and self.sidebar.isHidden())

    def style_crumb(self, button):
        # Dolphin leaves breadcrumb colours and hover painting to Plasma.
        button.setFlat(True)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setMinimumWidth(0)
        button.setContentsMargins(6, 0, 6, 0)

    def refresh_symbolic_icons(self, *args):
        tr('Use the active platform icon theme, including for native KIO widgets.')
        panes = ([p for tab in self._tabs for p in tab.panes] if hasattr(self, '_tabs')
                 else getattr(self, 'panes', ()))
        for pane in panes:
            pane.model.invalidate_style()
        button_names = (tr('home'), tr('back'), tr('forward'), tr('up'), tr('refresh_button'), tr('address_toggle'), tr('hidden'), tr('details_button'), tr('icons_button'), tr('compact_button'), tr('preview_button'), tr('preview_panel_button'), tr('incomplete_button'), tr('menu_button'), tr('search_button'), tr('split_button'))
        if hasattr(self, tr('apply_chrome_background')):
            self.apply_chrome_background()
        if hasattr(self, tr('style_pane_path_bars')):
            self.style_pane_path_bars()
        # Plasma draws the application chrome and all its interaction states.
        # Avoid QSS even when its values came from QPalette: QSS bypasses parts
        # of the native Breeze/Plasma style and creates visible colour bands.
        self.menuBar().setStyleSheet('')
        if hasattr(self, tr('crumb_scroll')):
            self.crumb_scroll.setStyleSheet('')
            self.address.setStyleSheet('')
            self.crumbs.setAutoFillBackground(False)
        if hasattr(self, tr('crumbs')):
            for button in self.crumbs.findChildren(QPushButton):
                self.style_crumb(button)
        theme_names = {tr('home'): tr('go-home'), tr('back'): tr('go-previous'), tr('forward'): tr('go-next'), tr('up'): tr('go-up'), tr('refresh_button'): tr('view-refresh'), tr('address_toggle'): tr('document-edit'), tr('hidden'): tr('view-hidden'), tr('details_button'): tr('view-list-tree'), tr('icons_button'): tr('view-list-icons'), tr('compact_button'): tr('view-list-details'), tr('preview_button'): tr('view-preview'), tr('preview_panel_button'): tr('sidebar-expand-right'), tr('incomplete_button'): tr('document-properties'), tr('search_button'): tr('edit-find'), tr('split_button'): tr('view-split-left-right'), tr('menu_button'): tr('application-menu')}
        standard_fallbacks = {tr('home'): QStyle.StandardPixmap.SP_DirHomeIcon, tr('back'): QStyle.StandardPixmap.SP_ArrowBack, tr('forward'): QStyle.StandardPixmap.SP_ArrowForward, tr('up'): QStyle.StandardPixmap.SP_ArrowUp, tr('refresh_button'): QStyle.StandardPixmap.SP_BrowserReload, tr('address_toggle'): QStyle.StandardPixmap.SP_FileDialogInfoView, tr('hidden'): QStyle.StandardPixmap.SP_FileDialogInfoView, tr('details_button'): QStyle.StandardPixmap.SP_FileDialogDetailedView, tr('icons_button'): QStyle.StandardPixmap.SP_FileDialogContentsView, tr('compact_button'): QStyle.StandardPixmap.SP_FileDialogContentsView, tr('preview_button'): QStyle.StandardPixmap.SP_FileIcon, tr('preview_panel_button'): QStyle.StandardPixmap.SP_FileDialogInfoView, tr('incomplete_button'): QStyle.StandardPixmap.SP_MessageBoxInformation, tr('search_button'): QStyle.StandardPixmap.SP_FileDialogContentsView, tr('split_button'): QStyle.StandardPixmap.SP_FileDialogContentsView, tr('menu_button'): QStyle.StandardPixmap.SP_TitleBarMenuButton}
        for name, theme in theme_names.items():
            button = getattr(self, name, None)
            if button is not None:
                button.setIcon(themed_icon(theme, self, standard_fallbacks.get(name)))
        for name in button_names:
            button = getattr(self, name, None)
            if button is not None:
                button.setIconSize(self.navigation_bar.iconSize())
                button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                button.setStyleSheet('')
                if isinstance(button, QPushButton):
                    button.setFlat(True)
        overflow = getattr(self, tr('toolbar_overflow'), None)
        if overflow is not None:
            overflow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            # Keep the native Plasma rendering.  Besides being visually more
            # consistent, this avoids reintroducing QSS during theme refreshes.
            overflow.setStyleSheet('')

    def search_dialog(self):
        self.search_panel.show()
        self.close_search_action.setEnabled(True)
        self.search.setFocus()
        self.search.selectAll()
        self.search_button.setChecked(True)

    def clear_all_search(self):
        self.close_search()

    def reset_search_view(self):
        """Restore a pane's ordinary directory view after recursive search."""
        self.search_active = False
        self.search_root = ''
        self.search_criteria = {}
        self.proxy.setFilterFixedString('')
        self.proxy.media_query = {}
        self.proxy.state_filter = tr('Tous')
        self.proxy.search_mode = False
        self.proxy.invalidateFilter()
        self.search_duplicates_manage.hide()
        self.table.setColumnHidden(10, True)
        self.table.setColumnHidden(12, True)
        self.search_start.setEnabled(True)
        self.search_scope.setEnabled(True)
        self.search_kind.setEnabled(True)
        self.state_filter.setEnabled(True)
        self.search_more.setEnabled(True)
        if hasattr(self, 'update_search_more_label'):
            self.update_search_more_label()

    def show_quick_filter(self):
        self.filter_panel.show()
        self.quick_filter.setFocus()
        self.quick_filter.selectAll()

    def close_quick_filter(self):
        self.quick_filter.clear()
        self.filter_panel.hide()
        self.active_view().setFocus()

    def apply_quick_filter(self, value):
        if hasattr(self, 'proxy'):
            self.proxy.set_name_filter(value)

    def schedule_live_search(self, *_args):
        if self.search_panel.isHidden() or not hasattr(self, 'bound_pane'):
            return
        self._live_search_pane = self.bound_pane
        self.live_search_timer.start()

    def start_live_search(self):
        if (self.search_panel.isHidden() or self.bound_pane is not getattr(self, '_live_search_pane', None)):
            return
        if not self.search.text().strip():
            if self.search_active:
                self.close_search()
                self.search_dialog()
            return
        self.start_unified_search()

    def start_unified_search(self):
        """Search local or KIO locations, optionally recursively."""
        self.live_search_timer.stop()
        if not self.folder:
            QMessageBox.information(
                self, tr('Recherche impossible'),
                tr('Choisissez un dossier avant de lancer la recherche.'),
            )
            return
        is_remote = Location.from_value(self.folder).is_uri
        if is_remote and self.search_content.isChecked():
            QMessageBox.information(self, tr('Recherche'), tr('La recherche dans le contenu est disponible uniquement pour les fichiers locaux.'))
            return
        query = self.search.text().strip()
        if self.search_content.isChecked() and not query:
            QMessageBox.information(self, tr('Recherche'), tr('Saisissez un texte à trouver dans les fichiers.'))
            return
        kind = str(self.search_kind.currentData() or 'all')
        state = self.state_filter.currentText()
        if state == tr('Informations techniques manquantes'):
            state = tr('Médias incomplets')
        duplicate_search = state == tr('Doublons exacts')
        media_query = dict(getattr(self.proxy, tr('media_query'), {}))
        legacy_kind = media_query.pop('kind', '')
        if legacy_kind and kind == 'all':
            kind = legacy_kind
            self.search_kind.blockSignals(True)
            self.search_kind.setCurrentIndex(max(0, self.search_kind.findData(kind)))
            self.search_kind.blockSignals(False)
        self.proxy.media_query = media_query
        has_media_criteria = any(media_query.values())
        if not query and kind == 'all' and state == tr('Tous les états') and not has_media_criteria:
            QMessageBox.information(
                self, tr('Recherche'),
                tr('Saisissez un nom ou choisissez au moins un filtre.'),
            )
            self.search.setFocus()
            return
        if self.scanning:
            self.bound_pane.pending_live_search = True
            if self.worker is not None and hasattr(self.worker, 'cancel'):
                self.worker.cancel()
            return
        self.bound_pane.pending_live_search = False
        self.scan_queued = False
        self.cancel_duration_lookups(self.bound_pane)
        self.stop_thumbnails()
        if self.folder_size_worker:
            self.folder_size_worker.cancel()
            # Its finished handler owns deleteLater(); cancellation alone does
            # not mean that the QThread has stopped yet.
            self.folder_size_worker = None
        self.model.clear()
        self.model.pending_preliminary = []
        self.model.pending_resolved = []
        self.model.preliminary_draining = False
        self.model.resolved_draining = False
        self.notices = []
        self.search_active = True
        self.search_root = self.folder
        self.search_criteria = {
            'query': query,
            'content': self.search_content.isChecked(),
            'recursive': self.search_scope.currentData() == 'recursive',
            'kind': kind,
            'state': state,
            'media': media_query,
            'duplicates': duplicate_search,
        }
        self.proxy.setFilterFixedString('')
        self.proxy.state_filter = tr('Tous') if state == tr('Tous les états') or duplicate_search else state
        self.proxy.search_mode = True
        self.proxy.invalidateFilter()
        self.search_duplicates_manage.hide()
        self.table.setColumnHidden(12, False)
        self.table.setColumnWidth(12, max(180, self.table.columnWidth(12)))
        self.search_panel.show()
        self.search_button.setChecked(True)
        self.search_start.setEnabled(False)
        self.search_scope.setEnabled(False)
        self.search_kind.setEnabled(False)
        self.state_filter.setEnabled(False)
        self.search_more.setEnabled(False)
        self.bar.setRange(0, 0)
        self.bar.setFormat(tr('Recherche en cours…'))
        self.bar.show()
        self.choose.setEnabled(False)
        self.refresh.setEnabled(False)
        self.recursive.setEnabled(False)
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter la recherche'))
        if self.worker:
            self.worker.deleteLater()
        worker_class = KioRemoteSearchWorker if is_remote else RecursiveSearchWorker
        self.worker = worker_class(
            self.folder, query,
            recursive=self.search_criteria['recursive'],
            show_hidden=self.hidden.isChecked(),
            kind=kind,
            content=self.search_criteria['content'],
        )
        pane = self.bound_pane
        self.worker.listed.connect(lambda rows, p=pane: self.queue_preliminary(p, rows))
        self.worker.progress.connect(self.pane_callback(self.search_progress))
        self.worker.notice.connect(self.notices.append)
        self.worker.finished.connect(self.pane_callback(self.finished))
        self.scanning = True
        self.update_empty_state()
        self.update_summary()
        self.start_runtime_worker(self.worker, tr('Recherche de fichiers'))

    def start_search_duplicate_analysis(self):
        if not self.search_active or not self.search_criteria.get('duplicates'):
            return
        self.search_criteria['duplicates'] = False
        paths = [
            self.row(self.proxy.index(index, 0)).path
            for index in range(self.proxy.rowCount())
            if not self.row(self.proxy.index(index, 0)).is_dir
        ]
        if len(paths) < 2:
            self.proxy.state_filter = tr('Doublons exacts')
            self.proxy.invalidateFilter()
            self.search_duplicates_manage.hide()
            self.update_summary()
            self.show_activity_message(tr('Aucun doublon exact : moins de deux fichiers correspondent à la recherche.'), 7000)
            return
        self.show_activity_message(trf('Inventaire terminé : analyse du contenu de \x1f0\x1f fichier(s) dans Opérations.', len(paths)), 7000)
        self.enqueue_analysis(tr('duplicates'), paths)

    def search_progress(self, scanned, found, folder):
        self.bar.setRange(0, 0)
        self.bar.setFormat(trf('\x1f0\x1f élément(s) examiné(s) • \x1f1\x1f résultat(s)', scanned, self.proxy.rowCount()))

    def close_search(self):
        self.live_search_timer.stop()
        self.bound_pane.pending_live_search = False
        self.search.clear()
        self.search_panel.hide()
        self.close_search_action.setEnabled(False)
        self.search_button.setChecked(False)
        was_active = self.search_active
        self.reset_search_view()
        if isinstance(self.worker, RecursiveSearchWorker) and self.scanning:
            self.pending_navigation = (self.folder, self.history_position)
            self.cancel()
        elif was_active and self.folder:
            self.scan()
        self.active_view().setFocus()

    def toggle_search(self):
        if self.search_panel.isVisible():
            self.close_search()
        else:
            self.search_dialog()

    def change_state_filter(self, text):
        self.proxy.state_filter = tr('Médias incomplets') if text == tr('Informations techniques manquantes') else text
        self.proxy.invalidateFilter()
        self.update_summary()

    def show_incomplete_media(self):
        self.search_dialog()
        index = self.state_filter.findText(tr('Informations techniques manquantes'))
        if index >= 0:
            self.state_filter.setCurrentIndex(index)
            self.start_unified_search()

    def update_disk_space(self):
        if self.model.rows:
            self.model.dataChanged.emit(self.model.index(0, 14), self.model.index(len(self.model.rows) - 1, 14))
        for pane in getattr(self, tr('panes'), ()):
            self.update_pane_footer(pane)

    def update_pane_footer(self, pane):
        """Refresh Dolphin-style item counts and free space below one pane."""
        folder = self.folder if pane is getattr(self, tr('bound_pane'), None) else pane.folder
        rows = pane.model.rows
        errors = sum(bool(row.error or row.bitrate_error or row.validation_error) for row in rows)
        # Counts and total bytes do not depend on sort order. When no entries
        # are filtered out, skip one Qt proxy-index conversion per file.
        visible_rows = rows if pane.proxy is not None and pane.proxy.rowCount() == len(rows) else []
        if pane.proxy is not None and visible_rows is not rows:
            for proxy_row in range(pane.proxy.rowCount()):
                source = pane.proxy.mapToSource(pane.proxy.index(proxy_row, 0))
                if source.isValid() and 0 <= source.row() < len(rows):
                    visible_rows.append(rows[source.row()])
        summary = summarize_items(
            visible_rows,
            tr,
            lambda size: quantity(size, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024),
        )
        if errors:
            error_text = trf('\x1f0\x1f erreur', errors) if errors == 1 else trf('\x1f0\x1f erreurs', errors)
            summary += tr(' • ') + error_text
        pane._normal_summary_text = summary
        feedback = (self.activity_message_label.text() if hasattr(self, 'activity_message_label')
                    and not self.places_panel.isVisible() and pane is self.bound_pane else '')
        pane.summary_label.set_full_text(feedback or summary, Qt.TextElideMode.ElideRight)
        pane.summary_label.setToolTip(feedback or summary)
        if not folder:
            pane.disk_label.set_full_text('')
            pane.disk_label.setToolTip('')
            return
        try:
            free = shutil.disk_usage(folder).free
            volume = QStorageInfo(folder)
            label = volume.name() or volume.rootPath() or folder
            disk_text = label + tr(' — ') + quantity(free, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024) + tr(' libres')
            pane.disk_label.set_full_text(disk_text, Qt.TextElideMode.ElideLeft)
            pane.disk_label.setToolTip(tr('Disque contenant ') + folder + tr(' • ') + disk_text)
        except (OSError, ValueError):
            disk_text = tr('Espace libre : indisponible')
            pane.disk_label.set_full_text(disk_text, Qt.TextElideMode.ElideLeft)
            pane.disk_label.setToolTip(folder)

    def set_folder_sizes(self, results, mode):
        """Publish a completed folder calculation without progressive repainting."""
        by_path = {path: (value, complete) for path, value, complete in results}
        first = None
        last = None
        for i, row in enumerate(self.model.rows):
            result = by_path.get(row.path)
            if result is None:
                continue
            value, complete = result
            suffix = '' if complete else tr(' (partiel)')
            if mode == 'count':
                row.values[1] = (tr('1 élément') if value == 1 else trf('\x1f0\x1f éléments', value)) + suffix
                row.folder_size_note = (tr('Élément directement contenu dans ce dossier.') if value == 1 else trf('\x1f0\x1f éléments directement contenus dans ce dossier.', value))
            else:
                row.values[1] = quantity(value, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024) + suffix
                row.folder_size_note = trf('Taille totale du dossier et de ses sous-dossiers : \x1f0\x1f octets.', format(int(value), ','))
            if not complete:
                row.folder_size_note += tr(' Le résultat est partiel car certains éléments ne sont pas accessibles.')
            row.sort_values[1] = value
            first = i if first is None else min(first, i)
            last = i if last is None else max(last, i)
        if first is not None:
            self.model.dataChanged.emit(self.model.index(first, 1), self.model.index(last, 1))

    def set_folder_size_display(self, mode):
        """Apply the configured folder meaning of the Size column to both panes."""
        mode = mode if mode in ('count', 'size') else 'count'
        current = str(self.settings.value('view/folder-size-display', 'count'))
        self.settings.setValue('view/folder-size-display', mode)
        if current == mode:
            return
        for pane in self.panes:
            if pane.folder and not pane.scanning:
                self.run_in_pane(pane, self.start_folder_sizes)

    def set_date_format(self, mode):
        """Apply a date presentation choice without changing timestamp sorting."""
        mode = normalized_date_format(mode)
        self.settings.setValue('view/date-format', mode)
        for pane in self.panes:
            pane.model.date_format = mode
            if pane.model.rows:
                pane.model.dataChanged.emit(
                    pane.model.index(0, 14),
                    pane.model.index(len(pane.model.rows) - 1, 14),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
                )
                pane.model.dataChanged.emit(
                    pane.model.index(0, 38), pane.model.index(len(pane.model.rows) - 1, 39),
                    [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        self.settings.sync()

    def active_view(self):
        return self.content_stack.currentWidget() if hasattr(self, tr('content_stack')) else self.table

    def selected_indexes(self):
        view = self.active_view()
        if view is self.table:
            return view.selectionModel().selectedRows()
        return [i for i in view.selectionModel().selectedIndexes() if i.column() == 0]

    def change_view(self, mode, remember=True):
        button = self.view_buttons.button(mode)
        if button is not None:
            button.setChecked(True)
        if hasattr(self, 'details_view_action'):
            (self.details_view_action if mode == 0 else
             self.icons_view_action if mode == 1 else
             self.compact_view_action).setChecked(True)
        indexes = self.selected_indexes()
        self.content_stack.setCurrentIndex(mode)
        selection = self.active_view().selectionModel()
        selection.clearSelection()
        for index in indexes:
            selection.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        if remember:
            if not per_folder_views(self.settings) and not special_view(self.settings, self.folder):
                self.settings.setValue('view/mode', mode)
            pane = getattr(self, 'bound_pane', None)
            if pane is not None:
                pane.view_mode = mode
                if self.folder and per_folder_views(self.settings):
                    pane.folder_views[self.folder] = mode
                    modes = getattr(self, 'folder_view_modes', None)
                    if modes is None:
                        modes = self.settings.value('view/folder-modes-v1', {})
                        modes = dict(modes) if isinstance(modes, dict) else {}
                        self.folder_view_modes = modes
                    modes[self.folder] = mode
                    self.settings.setValue('view/folder-modes-v1', modes)
        if remember:
            self.remember_folder_display(self.folder, 'mode', mode)
        self.start_thumbnails()
        self.update_delete_button()

    def install_dolphin_shortcuts(self, file_menu, edit_menu, view_menu, go_menu):
        """Register Dolphin-compatible commands that have no menu action.

        Actions that already exist keep their shortcut on the QAction so that
        it is visible in the menu.  This small group is for navigation and
        pane operations, which Dolphin exposes from the keyboard as well.
        """
        self.places_panel_action = QAction(tr('Emplacements'), self)
        set_themed_action_icon(self.places_panel_action, tr('folder-open'))
        self.places_panel_action.setCheckable(True)
        self.places_panel_action.setChecked(True)
        self.places_panel_action.setShortcut(QKeySequence(tr('F9')))
        self.places_panel_action.toggled.connect(self.set_places_panel_visible)
        view_menu.addAction(self.places_panel_action)
        self.folders_panel_action = QAction(tr('Panneau Dossiers'), self)
        set_themed_action_icon(self.folders_panel_action, tr('folder'))
        self.folders_panel_action.setCheckable(True)
        self.folders_panel_action.setShortcut(QKeySequence(tr('F7')))
        self.folders_panel_action.toggled.connect(self.set_folders_panel_visible)
        view_menu.addAction(self.folders_panel_action)

        self.dolphin_shortcuts = {}
        self.dolphin_shortcut_info = {}

        def add_menu_action(identifier, title, sequence, callback, menu, icon=''):
            action = QAction(title, self)
            action.setShortcut(QKeySequence(sequence))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.triggered.connect(callback)
            if icon:
                set_themed_action_icon(action, tr(icon))
            menu.addAction(action)
            self.dolphin_shortcuts[identifier] = action
            self.dolphin_shortcut_info[identifier] = (title, sequence)
            return action

        add_menu_action('back', tr('Précédent'), tr('Alt+Left'), lambda: self.navigate_history(-1), go_menu, 'go-previous')
        add_menu_action('forward', tr('Suivant'), tr('Alt+Right'), lambda: self.navigate_history(1), go_menu, 'go-next')
        add_menu_action('parent', tr('Dossier parent'), tr('Alt+Up'), self.navigate_parent, go_menu, 'go-up')
        add_menu_action('home', tr('Dossier personnel'), tr('Alt+Home'), lambda: self.navigate(str(Path.home())), go_menu, 'go-home')
        self.location_menu_action = add_menu_action('edit-location', tr('Modifier ou parcourir l’emplacement'), tr('F6'), self.toggle_active_pane_path_mode, go_menu, 'document-edit')
        self.select_all_action = add_menu_action('select-all', tr('Tout sélectionner'), tr('Ctrl+A'), self.select_all_active_files, edit_menu, 'edit-select-all')
        # Keep Ctrl+A active when the menu bar is hidden. Text editors retain
        # their native ShortcutOverride handling and their own Select All.
        self.addAction(self.select_all_action)
        self.invert_selection_action = add_menu_action('invert-selection', tr('Inverser la sélection'), tr('Ctrl+Shift+A'), self.invert_active_selection, edit_menu, 'edit-select-invert')
        self.quick_filter_action = add_menu_action('filter', tr('Filtrer le dossier affiché'), tr('Ctrl+I'), self.show_quick_filter, edit_menu, 'view-filter')
        self.permanent_delete_action = add_menu_action('delete-permanent', tr('Supprimer définitivement…'), tr('Shift+Delete'), lambda: self.delete_selected(tr('permanent')), file_menu, 'edit-delete')
        self.zoom_in_action = add_menu_action('zoom-in', tr('Agrandir'), tr('Ctrl++'), lambda: self.zoom_active_view(1), view_menu, 'zoom-in')
        self.zoom_out_action = add_menu_action('zoom-out', tr('Réduire'), tr('Ctrl+-'), lambda: self.zoom_active_view(-1), view_menu, 'zoom-out')
        self.zoom_reset_action = add_menu_action('zoom-reset', tr('Réinitialiser la taille'), tr('Ctrl+0'), self.reset_active_view_zoom, view_menu, 'zoom-original')
        self.copy_to_inactive_action = add_menu_action('copy-to-inactive', tr('Copier vers l’autre panneau'), tr('Shift+F5'), lambda: self.transfer_to_inactive_pane(copy_only=True), edit_menu, 'edit-copy')
        self.move_to_inactive_action = add_menu_action('move-to-inactive', tr('Déplacer vers l’autre panneau'), tr('Shift+F6'), lambda: self.transfer_to_inactive_pane(copy_only=False), edit_menu, 'edit-move')

        self.open_terminal_action = add_menu_action(
            'terminal', tr('Ouvrir dans le terminal'), tr('Shift+F4'),
            self.open_terminal_here, self.main_menus['tools'], 'utilities-terminal'
        )
        self.open_terminal_action.setToolTip(tr('Ouvre un terminal dans le dossier affiché dans le panneau actif.'))

    def init_shortcut_configuration(self, settings_menu):
        """Collect configurable actions after every UI surface is created."""
        self.shortcut_bindings = []

        def add(identifier, title, default, *targets):
            self.shortcut_bindings.append(dict(
                id=identifier,
                title=title,
                default=services.shortcut(default),
                sequence=services.shortcut(default),
                targets=targets,
            ))

        add('new-window', tr('Nouvelle fenêtre'), tr('Ctrl+N'), self.new_window_action)
        add('new-folder', tr('Nouveau dossier'), tr('Ctrl+Shift+N'), self.new_folder_action)
        add('rename', tr('Renommer'), tr('F2'), self.rename_action)
        add('properties', tr('Propriétés'), tr('Alt+Return'), self.properties_action)
        add('delete', tr('Mettre à la corbeille'), tr('Delete'), self.delete_button)
        add('undo', tr('Annuler'), tr('Ctrl+Z'), self.kio_undo_action)
        add('redo', tr('Rétablir'), tr('Ctrl+Shift+Z'), self.kio_redo_action)
        add('refresh', tr('Actualiser'), tr('F5'), self.refresh)
        add('search', tr('Rechercher'), tr('Ctrl+F'), self.search_action)
        add('location', tr('Saisir un emplacement'), tr('Ctrl+L'), self.path_shortcut)
        add('hidden', tr('Afficher les éléments cachés'), tr('Ctrl+H'), self.hidden_shortcut)
        add('details', tr('Vue détaillée'), tr('Ctrl+3'), self.details_view_action)
        add('icons', tr('Vue en icônes'), tr('Ctrl+1'), self.icons_view_action)
        add('compact', tr('Vue compacte'), tr('Ctrl+2'), self.compact_view_action)
        add('split', tr('Vue scindée'), tr('F3'), self.split_action)
        add('places', tr('Emplacements'), tr('F9'), self.places_panel_action)
        add('folders-panel', tr('Panneau Dossiers'), tr('F7'), self.folders_panel_action)
        add('terminal-panel', tr('Panneau Terminal'), tr('F4'), self.terminal_panel_action)
        add('preview-panel', tr('Panneau d’aperçu'), tr('F11'), self.preview_panel_action)
        add('menus', tr('Ouvrir les menus'), tr('F10'), self.menu_visibility.open_action)
        add('menubar', tr('Afficher la barre de menus'), tr('Ctrl+M'), self.menu_visibility.action)
        add('quit', tr('Quitter Mirivue'), tr('Ctrl+Q'), self.quit_action)
        for identifier, shortcut in self.dolphin_shortcuts.items():
            title, default = self.dolphin_shortcut_info[identifier]
            add(identifier, title, default, shortcut)
        from .keyboard import extend_bindings
        extend_bindings(self, add)
        self.apply_shortcut_bindings()
        self.configure_shortcuts_action = settings_menu.addAction(tr('Configurer les raccourcis clavier…'), self.show_shortcut_configuration)
        set_themed_action_icon(self.configure_shortcuts_action, tr('configure-shortcuts'))

    def apply_shortcut_bindings(self, values=None):
        from .keyboard import apply_bindings
        apply_bindings(self, values)

    def show_shortcut_configuration(self):
        from .configuration import show_shortcut_configuration
        show_shortcut_configuration(self)

    def set_places_panel_visible(self, visible):
        if not visible and not self.browser.isVisible() and self._sidebar_width_save_timer.isActive():
            self._sidebar_width_save_timer.stop()
            self.save_sidebar_width()
        self.places_panel.setVisible(visible)
        for pane in self.panes:
            self.sync_native_navigator_state(pane)
        self.sidebar.setVisible(visible or self.browser.isVisible())
        if self.sidebar.isVisible() and not self._sidebar_width_restored:
            QTimer.singleShot(0, self.restore_sidebar_width)
        QTimer.singleShot(0, self.sync_path_toolbar_alignment)
        if self.places_panel_action.isChecked() != visible:
            self.places_panel_action.blockSignals(True)
            self.places_panel_action.setChecked(visible)
            self.places_panel_action.blockSignals(False)
        if hasattr(self, 'activity_message_label'):
            message = self.activity_message_label.text()
            self.activity_message_label.setVisible(bool(visible and message))
            self.sync_feedback_in_pane_footers()
        self.update_activity_entry_points()

    def set_folders_panel_visible(self, visible):
        if not visible and not self.places_panel.isVisible() and self._sidebar_width_save_timer.isActive():
            self._sidebar_width_save_timer.stop()
            self.save_sidebar_width()
        self.browser.setVisible(visible)
        self.sidebar.setVisible(visible or self.places_panel.isVisible())
        if self.sidebar.isVisible() and not self._sidebar_width_restored:
            QTimer.singleShot(0, self.restore_sidebar_width)

    def init_terminal_panel(self, view_menu):
        self.terminal_dock = QDockWidget(tr('Terminal'), self)
        self.terminal_dock.setObjectName('mirivueTerminalDock')
        self.terminal_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.terminal_dock.setMinimumHeight(100)
        self.native_terminal = None
        try:
            from .native_places_view import NativeTerminal
            self.native_terminal = NativeTerminal(self.terminal_dock, self.terminal_changed_directory)
            self.terminal_dock.setWidget(self.native_terminal.widget)
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.terminal_dock.setWidget(QLabel(tr('KonsolePart est indisponible : ') + str(error)))
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.terminal_dock)
        self.terminal_panel_action = QAction(tr('Panneau Terminal'), self)
        self.terminal_panel_action.setCheckable(True)
        self.terminal_panel_action.setShortcut(QKeySequence(tr('F4')))
        self.terminal_panel_action.toggled.connect(self.terminal_dock.setVisible)
        self.terminal_dock.visibilityChanged.connect(self.terminal_visibility_changed)
        view_menu.addAction(self.terminal_panel_action)
        self.terminal_dock.hide()

    def terminal_visibility_changed(self, visible):
        self.terminal_panel_action.blockSignals(True)
        self.terminal_panel_action.setChecked(visible)
        self.terminal_panel_action.blockSignals(False)
        if visible and self.native_terminal is not None:
            self.sync_terminal_directory()
            self.native_terminal.focus()

    def sync_terminal_directory(self):
        if (self.native_terminal is not None and self.terminal_dock.isVisible()
                and self.folder and self.current_folder_is_local()):
            self.native_terminal.set_directory(self.folder)

    def terminal_changed_directory(self, path):
        if (self.terminal_dock.isVisible() and path and os.path.isdir(path)
                and (not self.current_folder_is_local() or os.path.realpath(path) != os.path.realpath(self.folder))):
            self.navigate(path)

    def navigate_parent(self):
        if self.folder:
            self.navigate(parent_location(self.folder))

    def active_file_view_has_focus(self):
        focus = QApplication.focusWidget()
        for pane in getattr(self, tr('panes'), ()):
            for view in (pane.table, pane.icons, pane.compact):
                if focus is view or view.isAncestorOf(focus):
                    return True
        return False

    def select_all_active_files(self):
        if self.active_file_view_has_focus():
            self.active_view().selectAll()

    def invert_active_selection(self):
        if not self.active_file_view_has_focus():
            return
        selection = self.active_view().selectionModel()
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            flags = QItemSelectionModel.SelectionFlag.Deselect if selection.isSelected(index) else QItemSelectionModel.SelectionFlag.Select
            selection.select(index, flags | QItemSelectionModel.SelectionFlag.Rows)

    def zoom_active_view(self, direction):
        if self.active_view() is self.table:
            self.zoom_details(direction)
        elif self.active_view() is self.compact:
            self.zoom_compact(direction)
        else:
            self.zoom_icons(direction)

    def reset_active_view_zoom(self):
        if self.active_view() is self.table:
            self.settings.setValue('view/details-icon-size', 22)
            self.apply_details_zoom()
            return
        if self.active_view() is self.compact:
            self.settings.remove('view/compact-icon-size')
            self.apply_compact_zoom()
            return
        key = tr('view/preview-size') if self.model.show_thumbnails else tr('view/icon-size')
        self.settings.setValue(key, 192 if self.model.show_thumbnails else 64)
        self.apply_icon_zoom()

    def transfer_to_inactive_pane(self, copy_only):
        if not getattr(self, tr('split_enabled'), False) or len(self.panes) < 2:
            return
        destination_pane = next((pane for pane in self.panes if pane is not self.bound_pane), None)
        paths = self.selected_entries()
        if not paths or destination_pane is None or not destination_pane.folder:
            return
        self.move_entries(paths, destination_pane.folder, copy_only=copy_only)

    def apply_details_zoom(self):
        size = max(16, min(128, self.settings.value('view/details-icon-size', 22, type=int)))
        self.table.setIconSize(QSize(size, size))
        self.table.verticalHeader().setDefaultSectionSize(max(size + 6, self.table.fontMetrics().height() + 8))

    def zoom_details(self, delta):
        if not delta:
            return
        sizes = (16, 22, 32, 48, 64, 96, 128)
        current = self.table.iconSize().width()
        size = next((n for n in sizes if n > current), 128) if delta > 0 else next((n for n in reversed(sizes) if n < current), 16)
        self.settings.setValue('view/details-icon-size', size)
        self.apply_details_zoom()

    def apply_icon_zoom(self):
        preview = self.model.show_thumbnails
        key = tr('view/preview-size') if preview else tr('view/icon-size')
        size = max(32, min(256, self.settings.value(key, 192 if preview else 64, type=int)))
        self.icons.setIconSize(QSize(size, max(20, round(size * 0.625))) if preview else QSize(size, size))
        extra_lines = len(getattr(self.bound_pane, 'extra_columns', ())) if getattr(self, 'bound_pane', None) else 0
        height = self.icons.iconSize().height() + self.fontMetrics().height() * (2 + extra_lines) + 12
        self.icons.setGridSize(QSize(max(96, size + 20), height))

    def zoom_icons(self, delta):
        if not delta:
            return
        key = tr('view/preview-size') if self.model.show_thumbnails else tr('view/icon-size')
        size = self.icons.iconSize().width()
        self.settings.setValue(key, max(32, min(256, size + (16 if delta > 0 else -16))))
        self.apply_icon_zoom()

    def apply_compact_zoom(self):
        native_size = self.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize, None, self.compact)
        size = max(16, min(128, self.settings.value('view/compact-icon-size', native_size, type=int)))
        self.compact.setIconSize(QSize(size, size))

    def zoom_compact(self, delta):
        if not delta:
            return
        sizes = (16, 22, 32, 48, 64, 96, 128)
        current = self.compact.iconSize().width()
        size = next((n for n in sizes if n > current), 128) if delta > 0 else next((n for n in reversed(sizes) if n < current), 16)
        self.settings.setValue('view/compact-icon-size', size)
        self.apply_compact_zoom()

    def startup_location_or(self, value, fallback):
        """Keep restorable KIO locations; reject absent local mount points."""
        value = str(value or '')
        location = Location.from_value(value)
        if location.is_uri:
            return location.uri
        if value:
            path = Path(os.path.abspath(os.path.expanduser(value)))
            if path.is_dir():
                return str(path)
        return fallback

    def remember_pane_folder(self, folder):
        pane = getattr(self, 'bound_pane', None)
        if pane is not None:
            self.settings.setValue(f'panes/{pane.column_slot}-folder', folder)

    def prime_startup_pane(self, pane, folder):
        """Install a pane location without starting I/O or changing layout."""
        def prime():
            self.restore_folder_view(folder)
            if self.settings.value('view/hide-hidden-on-startup', False, type=bool):
                pane.hidden_state = False
                self.hidden.blockSignals(True)
                self.hidden.setChecked(False)
                self.hidden.blockSignals(False)
                self.hidden_action.blockSignals(True)
                self.hidden_action.setChecked(False)
                self.hidden_action.blockSignals(False)
                self.apply_hidden_filter()
            self.folder = folder
            self.history = [folder]
            self.history_position = 0
            self.pending_navigation = None
            self.parent_selection = None
            self.address.setText(folder)
            self.location.setText(folder)
            self.update_pane_path_bar(self.bound_pane)
            self.update_navigation()
            self.update_pane_titles()
        self.run_in_pane_silent(pane, prime)
        if pane is self.bound_pane:
            self.capture_pane()

    def prepare_startup_browsing(self, explicit=None):
        """Build the final one- or two-pane layout before the window is shown."""
        if explicit is None and self.restore_tab_session():
            return
        primary = self.startup_folder(explicit)
        location_mode = self.settings.value('startup/location', tr('home'))
        if explicit or location_mode != tr('last'):
            secondary = primary
        else:
            secondary = self.startup_location_or(
                self.settings.value('panes/right-folder', ''), primary
            )
        self.prime_startup_pane(self.panes[0], primary)
        if self.startup_split_action.isChecked():
            self.set_split_view(True, navigate_new=False)
            self.prime_startup_pane(self.panes[1], secondary)
            self.bind_pane(self.panes[0])
        self.sync_pane_path_bars()
        self.sync_pane_controls()
        self._startup_browsing_prepared = True

    def start_browsing(self, explicit=None):
        if not getattr(self, '_startup_browsing_prepared', False):
            self.prepare_startup_browsing(explicit)
        for pane in tuple(self.panes):
            if pane.folder and not pane.scanning:
                pane._session_listing_pending = False
                self.run_in_pane(pane, self.scan)

    def show_first_use_help(self):
        if self.settings.value('help/first-use-seen', False, type=bool):
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr('Premiers pas avec Mirivue'))
        box.setText(tr('Les fonctions principales sont accessibles directement dans la barre d’outils.'))
        box.setInformativeText(tr('Vue scindée : F3\nEmplacements : F9\nPanneau d’aperçu : F11\nRecherche dans le dossier actif et ses sous-dossiers : Ctrl+F\nÉléments cachés : Ctrl+H\nRenommer : F2\n\nMirivue affiche rapidement les informations essentielles des médias. Pour lire les détails des nouveaux fichiers du dossier actif, utilisez Outils → Métadonnées → Lire les informations détaillées des médias du dossier. La recherche permet aussi de limiter les résultats aux médias dont les informations techniques sont manquantes.'))
        box.exec()
        self.settings.setValue('help/first-use-seen', True)

    def startup_folder(self, explicit=None):
        if explicit:
            requested = parse_launch_arguments([explicit]).folder
            if requested:
                return requested
        location = self.settings.value('startup/location', tr('home'))
        if location == tr('path'):
            chosen = self.settings.value('startup/path', '')
            if chosen and Path(chosen).is_dir():
                return str(Path(chosen).absolute())
        if location == tr('last'):
            last = self.settings.value('panes/left-folder', self.settings.value('folder', ''))
            if last:
                requested = parse_launch_arguments([last]).folder
                if requested:
                    return requested
        return str(Path.home())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, tr('update_toolbar_responsiveness')):
            self.update_toolbar_responsiveness()
        if hasattr(self, tr('resize_preview_fullscreen_overlay')):
            self.resize_preview_fullscreen_overlay()
        # QSplitter does not emit splitterMoved when the complete window is
        # resized.  Re-align the independent toolbar location bars after Qt
        # has finished that layout pass.
        if hasattr(self, tr('sync_path_toolbar_alignment')):
            QTimer.singleShot(0, self.sync_path_toolbar_alignment)

    def update_toolbar_responsiveness(self):
        """Keep navigation and paths visible when the toolbar gets narrow."""
        if not hasattr(self, tr('toolbar_overflow')):
            return
        current_compact = self.toolbar_overflow.isVisible()
        path_widths = [pane.path_bar.width() for pane in getattr(self, tr('panes'), []) if pane.path_bar.isVisible()]
        minimum_path_width = 140 if getattr(self, tr('split_enabled'), False) else 220
        if current_compact:
            # Keep the compact state until there is a comfortable margin;
            # this avoids oscillating around the threshold while resizing.
            compact = self.navigation_bar.width() < 1040
        else:
            compact = bool(path_widths) and min(path_widths) < minimum_path_width
        hidden = getattr(self, tr('_toolbar_hidden_names'), set())
        for name, widget in getattr(self, tr('_toolbar_overflow_widgets'), []):
            widget.setVisible(not compact and name not in hidden)
        self.toolbar_overflow.setVisible(compact)
        self.toolbar_overflow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        # The Plasma style already paints this native tool button and all its
        # interaction states.  A QSS palette() expression here was rejected by
        # Qt 6.11 and produced a warning on every resize/smoke test.
        self.toolbar_overflow.setStyleSheet('')
        if compact != current_compact:
            QTimer.singleShot(0, self.sync_path_toolbar_alignment)

    def refresh_toolbar_overflow(self):
        """Refresh secondary commands after optional media controls exist."""
        if not hasattr(self, tr('toolbar_overflow_menu')):
            return
        self.toolbar_overflow_menu.clear()
        self._toolbar_overflow_widgets = []
        for name, title in ((tr('hidden'), tr('Éléments cachés')), (tr('preview_button'), tr('Miniatures')), (tr('preview_panel_button'), tr('Panneau d’aperçu'))):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            action = self.toolbar_overflow_menu.addAction(title)
            action.setCheckable(hasattr(widget, tr('isCheckable')) and widget.isCheckable())
            if action.isCheckable():
                action.setChecked(widget.isChecked())
                widget.toggled.connect(action.setChecked)
                action.triggered.connect(lambda checked=False, target=widget: target.click())
            elif hasattr(widget, tr('showPopup')):
                action.triggered.connect(widget.showPopup)
            self._toolbar_overflow_widgets.append((name, widget))

    def schedule_sidebar_width_save(self, *_args):
        if self.sidebar.isVisible() and self._sidebar_width_restored:
            self._sidebar_width_save_timer.start()

    def save_sidebar_width(self):
        if self.sidebar.isVisible():
            width = self.main_splitter.sizes()[0]
            if width > 0:
                self.settings.setValue('panes/sidebar-width-v1', width)

    def restore_sidebar_width(self):
        if self._sidebar_width_restored or not self.sidebar.isVisible():
            return
        available = self.main_splitter.width() - self.main_splitter.handleWidth()
        if available <= 120:
            return
        try:
            saved = int(self.settings.value('panes/sidebar-width-v1', 240))
        except (TypeError, ValueError):
            saved = 240
        # Leave room for the active file view even after restoring on a
        # smaller screen; Qt applies the widgets' own minimum sizes too.
        width = min(max(1, saved), max(1, available - 120))
        self.main_splitter.setSizes([width, max(1, available - width)])
        self._sidebar_width_restored = True

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'main_splitter') and not self._sidebar_width_restored:
            self.restore_sidebar_width()
            if not self._sidebar_width_restored:
                QTimer.singleShot(0, self.restore_sidebar_width)
        if hasattr(self, tr('sync_path_toolbar_alignment')):
            QTimer.singleShot(0, self.sync_path_toolbar_alignment)

    def eventFilter(self, watched, event):
        event_type = event.type()
        if watched is self and event_type in (QEvent.Type.ApplicationFontChange, QEvent.Type.ThemeChange):
            self.refresh_symbolic_icons()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            # Keep track of an actual header-handle drag.  QHeaderView also
            # emits sectionResized for layout changes, so the resize handler
            # must not interpret a window resize as a user customization.
            self._column_resize_pane = None
            for pane in getattr(self, tr('panes'), ()):
                header = pane.table.horizontalHeader()
                if watched not in (header, header.viewport()):
                    continue
                point = event.position().toPoint()
                if watched is header.viewport():
                    point = header.viewport().mapTo(header, point)
                x = point.x()
                near_handle = any(
                    abs(x - (header.sectionPosition(column) + header.sectionSize(column))) <= 4
                    for column in range(header.count())
                )
                if near_handle:
                    self._column_resize_pane = pane
                break
        elif event_type == QEvent.Type.MouseButtonRelease and watched in tuple(
                widget
                for pane in getattr(self, tr('panes'), ())
                for widget in (pane.table.horizontalHeader(), pane.table.horizontalHeader().viewport())):
            QTimer.singleShot(0, lambda: setattr(self, '_column_resize_pane', None))
        if (event_type in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)
                and event.key() == Qt.Key.Key_Shift):
            pressed = event_type == QEvent.Type.KeyPress
            for action in tuple(getattr(self, tr('_dynamic_trash_actions'), ())):
                menu = action.parent()
                if menu is not None and menu.isVisible() and hasattr(action, tr('_mirivue_set_mode')):
                    action._mirivue_set_mode(pressed)
        if (event_type == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton):
            # On Wayland and on some Qt styles the later QContextMenuEvent no
            # longer carries the modifier state.  Remember Shift at the
            # initiating press so Dolphin's Shift+right-click action remains
            # available when the permanent-delete preference is disabled.
            self._context_menu_shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if event_type == QEvent.Type.ContextMenu:
            # QContextMenuEvent carries the modifier state reliably.  By the
            # time customContextMenuRequested is emitted, QApplication's
            # global keyboard state may already have lost Shift.
            self._context_menu_shift = bool(
                getattr(self, tr('_context_menu_shift'), False)
                or event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )
        if event_type in (QEvent.Type.FocusIn, QEvent.Type.Wheel, QEvent.Type.ContextMenu, QEvent.Type.MouseButtonPress):
            self.activate_event_pane(watched, event)
        elif event_type not in (QEvent.Type.Resize, QEvent.Type.KeyPress, QEvent.Type.MouseMove,
                                QEvent.Type.Enter, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            return super().eventFilter(watched, event)
        # Scrollbar policies are set on view creation, mode changes and theme
        # changes. Rechecking all three views of both panes for every resize
        # queued hundreds of callbacks while the details splitter was dragged.
        if event_type == QEvent.Type.Resize and watched is getattr(self, tr('preview_dock'), None) and hasattr(self, tr('sync_path_toolbar_alignment')):
            # The dock can be resized independently of the main window.
            QTimer.singleShot(0, self.sync_path_toolbar_alignment)
        if event_type == QEvent.Type.Resize and watched is getattr(self, tr('media_image'), None) and is_pdf(getattr(self, tr('_preview_pending'), None)):
            QTimer.singleShot(0, self._render_pdf_page)
        if event_type == QEvent.Type.Resize and getattr(self, tr('_preview_fullscreen'), False) and (watched is getattr(self, tr('_fullscreen_content_widget'), None)):
            QTimer.singleShot(0, self.position_fullscreen_content)
        if event_type in (QEvent.Type.MouseMove, QEvent.Type.Enter) and getattr(self, tr('_preview_fullscreen'), False) and (watched in (getattr(self, tr('_preview_fullscreen_overlay'), None), getattr(self, tr('media_image'), None), getattr(self, tr('media_video'), None), getattr(self, tr('_fullscreen_controls'), None), getattr(self, tr('_fullscreen_reveal_zone'), None))):
            self.show_fullscreen_controls()
        if event_type == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape and getattr(self, tr('_preview_fullscreen'), False):
            self.toggle_preview_fullscreen()
            event.accept()
            return True
        if event_type == QEvent.Type.KeyPress and getattr(self, tr('_preview_fullscreen'), False) and (getattr(self, tr('_preview_pending'), None) is not None) and (getattr(self, tr('_preview_pending')).media_type == tr('image') or getattr(self, tr('_preview_document_image'), False)) and (event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right)):
            self.play_adjacent_media(-1 if event.key() == Qt.Key.Key_Left else 1)
            event.accept()
            return True
        if event_type == QEvent.Type.Wheel:
            if watched is getattr(self, tr('media_volume_button'), None) and self.adjust_media_volume(event.angleDelta().y() or event.pixelDelta().y()):
                event.accept()
                return True
            preview_widgets = (getattr(self, tr('preview_stack'), None), getattr(self, tr('media_image'), None), getattr(self, tr('media_video'), None))
            if watched in preview_widgets and self.preview_wheel(event):
                event.accept()
                return True
        if event_type == QEvent.Type.Wheel and watched in (self.icons.viewport(), self.table.viewport(), self.compact.viewport()) and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            pixel = event.pixelDelta().y()
            # Qt may send several fractions of a notch, or several notches in
            # one event. Keep the partial rotation on the viewport concerned.
            source = 'angle' if angle else 'pixel'
            if watched.property('_mirivue_zoom_wheel_source') != source:
                watched.setProperty('_mirivue_zoom_wheel_source', source)
                watched.setProperty('_mirivue_zoom_wheel_remainder', 0)
            steps, remainder = wheel_zoom_steps(
                angle if angle else pixel,
                watched.property('_mirivue_zoom_wheel_remainder') or 0,
            )
            watched.setProperty('_mirivue_zoom_wheel_remainder', remainder)
            if watched is self.table.viewport():
                zoom = self.zoom_details
            elif watched is self.compact.viewport():
                zoom = self.zoom_compact
            else:
                zoom = self.zoom_icons
            for _ in range(abs(steps)):
                zoom(steps)
            event.accept()
            return True
        if event_type == QEvent.Type.ContextMenu and watched in (getattr(self, tr('preview_stack'), None), getattr(self, tr('media_image'), None), getattr(self, tr('media_video'), None)):
            self.show_preview_context()
            event.accept()
            return True
        if event_type == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton and watched in (getattr(self, tr('media_image'), None), getattr(self, tr('media_video'), None)):
            row = getattr(self, tr('_preview_pending'), None)
            if row is not None and row.is_dir:
                self.navigate(str(row.path))
                event.accept()
                return True
            if is_openable_document(row):
                self.open_url(row.path)
                event.accept()
                return True
            if self.toggle_preview_fullscreen():
                event.accept()
                return True
        if event_type == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
            view = self.active_view()
            if watched is view.viewport() and view.is_view_background(event.position().toPoint()):
                if self.folder and self.settings.value('navigation/empty-double-click-up', False, type=bool):
                    self.navigate(parent_location(self.folder))
                    return True
        return super().eventFilter(watched, event)

    def toggle_previews(self, enabled):
        if not per_folder_views(self.settings) and not special_view(self.settings, self.folder):
            self.settings.setValue('view/previews', enabled)
        self.remember_folder_display(self.folder, 'previews', enabled)
        self.model.show_thumbnails = enabled
        self.apply_icon_zoom()
        self.icons.viewport().update()
        self.compact.viewport().update()
        self.table.viewport().update()
        self.start_thumbnails()

    def stop_thumbnails(self):
        if self.thumbnail_worker:
            self.thumbnail_worker.requestInterruption()
            self.thumbnail_worker.wait()
            self.thumbnail_worker.deleteLater()
            self.thumbnail_worker = None

    def start_thumbnails(self, force_paths=()):
        self.stop_thumbnails()
        if self.closing or not hasattr(self, tr('preview_action')) or (not self.model.show_thumbnails) or self.scanning:
            return
        # Ask KIO about every regular file: the configured KDE preview plugins
        # also cover PDFs, SVGs, office files and other document types. The
        # fallback worker itself remains limited to Mirivue's media formats.
        paths = [r.path for r in self.model.rows if (not r.is_dir) and (not r.error) and (r.path not in self.model.thumbnails)]
        self.thumbnail_worker = ThumbnailWorker(paths, force_paths)
        pane = self.bound_pane
        self.thumbnail_worker.ready.connect(lambda path, signature, data, p=pane:
            self.run_in_pane_silent(p, self.thumbnail_ready, path, signature, data))
        self.start_runtime_worker(self.thumbnail_worker, tr('Création des miniatures'))

    def regenerate_previews(self):
        paths = [self.row(i).path for i in self.selected_indexes() if self.row(i).is_video]
        self.stop_thumbnails()
        for path in paths:
            self.model.thumbnails.pop(path, None)
        if not self.preview_action.isChecked():
            self.preview_action.blockSignals(True)
            self.preview_action.setChecked(True)
            self.preview_action.blockSignals(False)
            self.preview_button.setChecked(True)
            self.model.show_thumbnails = True
            self.settings.setValue('view/previews', True)
            self.apply_icon_zoom()
        self.table.viewport().update()
        self.icons.viewport().update()
        self.compact.viewport().update()
        if self.model.rows:
            self.model.dataChanged.emit(self.model.index(0, 0),
                                       self.model.index(len(self.model.rows)-1, 0),
                                       [Qt.ItemDataRole.DecorationRole])
        self.start_thumbnails(paths)

    def thumbnail_ready(self, path, signature, data):
        try:
            if fingerprint(path) != signature or not self.model.positions_for_path(path):
                return
        except OSError:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.model.thumbnails[path] = QIcon(pixmap)
            for i in self.model.positions_for_path(path):
                index = self.model.index(i, 0)
                self.model.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    def set_address_mode(self, mode):
        self.address_stack.setCurrentIndex(mode)
        self.address_toggle.setText('')
        theme = tr('edit-clear-locationbar-ltr') if mode else tr('document-edit')
        fallback = QStyle.StandardPixmap.SP_LineEditClearButton if mode else QStyle.StandardPixmap.SP_FileDialogInfoView
        self.address_toggle.setIcon(themed_icon(theme, self, fallback))
        self.address_toggle.setToolTip(tr('Afficher les boutons du chemin') if mode else tr('Saisir le chemin (Ctrl+L)'))
        self.address_toggle.setAccessibleName(self.address_toggle.toolTip())
        self.settings.setValue('address/mode', mode)
        if mode:
            self.address.setFocus()
            self.address.selectAll()

    def update_crumbs(self):
        while self.crumb_layout.count():
            item = self.crumb_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        path = Path(self.folder)
        parts = [*reversed(path.parents), path]
        home = Path.home()
        if home in parts:
            parts = parts[parts.index(home):]
        for position, part in enumerate(parts):
            if position:
                separator = QLabel(tr('›'))
                separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.crumb_layout.addWidget(separator)
            button = QPushButton(tr('Dossier personnel') if part == home else part.name or tr('/'))
            if part == path:
                font = button.font()
                font.setBold(True)
                button.setFont(font)
            self.style_crumb(button)
            button.setToolTip(str(part))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(lambda pos, b=button, p=part: self.path_menu(b, p, pos))
            button.clicked.connect(lambda checked=False, target=str(part): self.navigate(target))
            self.crumb_layout.addWidget(button)
        self.crumb_layout.addStretch()
        QTimer.singleShot(0, lambda: self.crumb_scroll.horizontalScrollBar().setValue(self.crumb_scroll.horizontalScrollBar().maximum()))

    def apply_hidden_filter(self):
        flags = QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot
        if self.hidden.isChecked():
            flags |= QDir.Filter.Hidden
        self.filesystem.setFilter(flags)

    def change_hidden(self, checked):
        if getattr(self, 'bound_pane', None) is not None:
            self.bound_pane.hidden_state = checked
            self.sync_native_navigator_state(self.bound_pane)
        self.remember_folder_display(self.folder, 'hidden', checked)
        self.apply_hidden_filter()
        if self.folder:
            self.refresh_current_view()

    def refresh_current_view(self):
        if self.search_active:
            self.start_unified_search()
        else:
            self.scan()

    def set_column_visible(self, column, visible):
        if column == 0:
            self.table.setColumnHidden(0, False)
            self.sync_columns_menu()
            return
        if column in (10, 12, 13, 15, 16, 36):
            self.table.setColumnHidden(column, True)
            return
        if not visible and sum((not self.table.isColumnHidden(c) for c in range(len(HEADERS)))) == 1:
            self.sync_columns_menu()
            return
        self.table.setColumnHidden(column, not visible)
        self.schedule_pane_column_save(self.bound_pane)

    def set_icon_extra_information(self, column, enabled):
        pane = self.bound_pane
        columns = set(pane.extra_columns)
        if enabled:
            columns.add(column)
        else:
            columns.discard(column)
        pane.extra_columns = tuple(sorted(columns))
        self.remember_folder_display(self.folder, 'extra_columns', list(pane.extra_columns))
        self.update_pane_extra_information(pane)

    def sync_icon_extra_information(self):
        for column, action in self.extra_info_actions.items():
            action.blockSignals(True)
            action.setChecked(column in self.bound_pane.extra_columns)
            action.blockSignals(False)

    def rebuild_main_menus(self):
        """Arrange global actions like Dolphin while keeping Mirivue tools distinct."""
        menus = self.main_menus

        def action(title, callback, icon=''):
            created = QAction(title, self)
            created.triggered.connect(callback)
            if icon:
                set_themed_action_icon(created, tr(icon))
            return created

        self.move_to_folder_action = action(tr('Déplacer vers un nouveau dossier…'), self.group_selected, 'folder-new')
        self.create_archive_action = action(tr('Créer une archive…'), self.create_archive, 'package-x-generic')
        self.batch_rename_action = action(tr('Renommage avancé…'), self.rename_advanced, 'edit-rename')
        self.external_renamer_action = action(tr('Renommer avec un logiciel externe…'), lambda: self.launch_renamer(), 'system-run')
        self.metadata_rename_action = action(tr('Renommer à partir des métadonnées…'), self.rename_from_metadata, 'document-edit')
        self.extensions_action = action(tr('Corriger les extensions de la sélection…'), self.rename_extensions, 'edit-rename')
        self.organize_folders_action = action(tr('Organiser en sous-dossiers…'), self.organize_media, 'folder-new')
        self.read_unloaded_metadata_action = action(tr('Lire les informations détaillées des médias du dossier'),
                                                    self.read_unloaded_metadata, 'document-properties')

        self.view_mode_menu = QMenu(tr('Mode d’affichage'), self)
        self.view_mode_menu.addAction(self.icons_view_action)
        self.view_mode_menu.addAction(self.compact_view_action)
        self.view_mode_menu.addAction(self.details_view_action)
        self.zoom_menu = QMenu(tr('Taille de l’affichage'), self)
        self.zoom_menu.addActions([self.zoom_in_action, self.zoom_out_action, self.zoom_reset_action])
        self.extra_info_menu = QMenu(tr('Informations sous les icônes'), self)
        self.extra_info_actions = {}
        for column in (1, 14, 2, 3, 4, 19, 20):
            item = self.extra_info_menu.addAction(HEADERS[column])
            item.setCheckable(True)
            item.toggled.connect(lambda checked, c=column: self.set_icon_extra_information(c, checked))
            self.extra_info_actions[column] = item
        self.extra_info_menu.aboutToShow.connect(self.sync_icon_extra_information)
        self.panels_menu = QMenu(tr('Panneaux'), self)
        self.places_panel_action.setText(tr('Panneau Emplacements'))
        self.panels_menu.addAction(self.places_panel_action)
        self.panels_menu.addAction(self.folders_panel_action)
        self.panels_menu.addAction(self.preview_panel_action)
        self.panels_menu.addAction(self.terminal_panel_action)
        self.columns_menu.setTitle(tr('Colonnes de la vue détaillée'))
        self.media_profile_menu.setTitle(tr('Configurations de colonnes'))

        self.rename_menu = QMenu(tr('Renommer et organiser'), self)
        for current in (self.batch_rename_action, self.metadata_rename_action, self.extensions_action,
                        self.organize_folders_action, self.external_renamer_action, self.move_to_folder_action,
                        self.create_archive_action):
            self.rename_menu.addAction(current)
        def reset(menu):
            for existing in list(menu.actions()):
                menu.removeAction(existing)

        def populate(menu, entries):
            reset(menu)
            for entry in entries:
                if entry is None:
                    menu.addSeparator()
                elif isinstance(entry, QMenu):
                    menu.addMenu(entry)
                else:
                    menu.addAction(entry)

        populate(menus['file'], [
            self.new_window_action, self.new_tab_action, self.close_tab_action, self.reopen_tab_action,
            self.recently_closed_tabs_menu, None,
            self.open_action, self.new_folder_action, self.recent_menu, None,
            self.rename_action, self.delete_button, self.permanent_delete_action,
            self.properties_action, None, self.quit_action,
        ])
        transfers = self.transfer_actions
        populate(menus['edit'], [
            self.kio_undo_action, self.kio_redo_action, None,
            transfers[tr('Couper')], transfers[tr('Copier')], transfers[tr('Coller')], transfers[tr('Dupliquer')],
            self.copy_folder_name_action, self.copy_paths_action, None,
            self.copy_to_inactive_action, self.move_to_inactive_action, None,
            self.select_all_action, self.invert_selection_action, None,
            self.search_action, self.close_search_action, self.quick_filter_action,
        ])
        populate(menus['view'], [
            self.view_mode_menu, self.zoom_menu, self.sort_menu,
            self.extra_info_menu, self.columns_menu, self.media_profile_menu, None,
            self.hidden_action, self.preview_action, None,
            self.split_action, self.panels_menu, self.folder_summary_action, None,
            self.refresh, self.stop,
        ])
        populate(menus['go'], [
            self.dolphin_shortcuts['parent'], self.dolphin_shortcuts['back'],
            self.dolphin_shortcuts['forward'], self.dolphin_shortcuts['home'], None,
            self.location_menu_action, self.focus_other_pane_action,
        ])
        populate(menus['tools'], [
            self.open_terminal_action, self.terminal_selection_action, self.focus_terminal_action, None,
            self.rename_menu, menus['organize'], self.folder_duration_action, self.collections_menu, menus['operations'],
        ])
        populate(menus['organize'], [
            self.metadata_action, self.read_unloaded_metadata_action,
        ])
        populate(menus['operations'], [
            self.jobs_action, None, self.resume_action, self.clear_pending_action,
            self.stop_all_analyses_action,
        ])
        populate(menus['settings'], [
            self.menu_visibility.action, None,
            self.configure_shortcuts_action, self.toolbar_action, None,
            self.configure_action,
        ])
        populate(menus['help'], [
            self.guide_action, self.shortcuts_help_action, self.analysis_help_action, None,
            self.diagnostics_action, None, self.about_action,
        ])
        for menu in [*menus.values(), self.rename_menu]:
            menu.setToolTipsVisible(True)
            menu.aboutToShow.connect(self.update_main_menu_states)
        self.update_main_menu_states()

    def selection_block_reason(self, paths):
        if not paths:
            return tr('Sélectionnez au moins un élément.')
        if self.scanning:
            return tr('Attendez la fin du chargement du dossier.')
        if self.is_archive_view():
            return tr('Cette commande n’est pas disponible pendant la consultation d’une archive.')
        if self.movement_locked(paths):
            return tr('Un fichier sélectionné est utilisé par une opération en cours.')
        return ''

    def selection_writable(self, paths):
        return (bool(paths) and not self.scanning and not self.is_archive_view()
                and not self.movement_locked(paths))

    def can_create_archive(self, paths):
        return (self.selection_writable(paths) and self.current_folder_is_local()
                and all(isinstance(path, Path) for path in paths))

    def update_main_menu_states(self, refresh_details=True):
        rows = [self.row(index) for index in self.selected_indexes()]
        selected = bool(rows)
        paths = [row.path for row in rows]
        writable = self.selection_writable(paths)
        reason = self.selection_block_reason(paths)
        self.open_action.setText(tr('Ouvrir') if selected else tr('Ouvrir un dossier…'))
        self.close_search_action.setEnabled(self.search_active or self.search_panel.isVisible())
        set_action_enabled(self.delete_button, writable, reason)
        set_action_enabled(self.permanent_delete_action, writable, reason)
        self.select_all_action.setEnabled(self.proxy.rowCount() > 0)
        self.invert_selection_action.setEnabled(self.proxy.rowCount() > 0)
        set_action_enabled(self.focus_other_pane_action, self.split_enabled, tr('Activez la vue scindée pour utiliser l’autre panneau.'))
        set_action_enabled(self.copy_paths_action, selected, reason)
        set_action_enabled(self.copy_to_inactive_action, self.split_enabled and writable, reason or tr('Activez la vue scindée pour utiliser l’autre panneau.'))
        set_action_enabled(self.move_to_inactive_action, self.split_enabled and writable, reason or tr('Activez la vue scindée pour utiliser l’autre panneau.'))
        set_action_enabled(self.move_to_folder_action, writable, reason)
        set_action_enabled(self.create_archive_action, self.can_create_archive(paths), reason or tr('La création d’archive nécessite une sélection dans un dossier local.'))
        self.folder_duration_action.setEnabled(
            not self.scanning and bool(rows) and all(row.is_dir for row in rows)
        )
        set_action_enabled(self.batch_rename_action, writable, reason)
        set_action_enabled(self.external_renamer_action, writable, reason)
        media = any(row.media_type in ('video', 'audio', 'image') and not row.is_dir for row in rows)
        set_action_enabled(self.metadata_rename_action, writable and media, reason or tr('Sélectionnez une vidéo, un fichier audio ou une image.'))
        set_action_enabled(self.extensions_action, writable and any(not row.is_dir for row in rows), reason or tr('Sélectionnez au moins un fichier.'))
        set_action_enabled(self.organize_folders_action, writable and media, reason or tr('Sélectionnez une vidéo, un fichier audio ou une image.'))
        self.metadata_action.setText(tr('Modifier les métadonnées…'))
        set_action_enabled(self.metadata_action, writable and media, reason or tr('Sélectionnez une vidéo, un fichier audio ou une image.'))
        self.properties_action.setEnabled(selected)
        self.transfer_actions[tr('Copier')].setEnabled(selected)
        set_action_enabled(self.transfer_actions[tr('Couper')], writable, reason)
        set_action_enabled(self.transfer_actions[tr('Dupliquer')], writable, reason)
        self.clear_pending_action.setEnabled(bool(self.resume_data))
        self.stop_all_analyses_action.setEnabled(self.jobs_busy())
        details = self.content_stack.currentIndex() == 0
        self.extra_info_menu.menuAction().setVisible(not details)
        self.columns_menu.menuAction().setVisible(details)
        self.media_profile_menu.menuAction().setVisible(details)
        self.external_renamer_action.setText(self.external_renamer_label())
        if refresh_details:
            unread_count = len(self.unloaded_media_paths())
            self.read_unloaded_metadata_action.setText(
                trf('Lire les informations détaillées des médias du dossier (\x1f0\x1f)', unread_count))
            self.read_unloaded_metadata_action.setEnabled(
                bool(unread_count) and not self.scanning and not self._visible_workers
                and not self.is_trash_view() and not self.is_archive_view())

    def start_runtime_worker(self, worker, name, cancellable=True):
        """Register and start a worker through the single shutdown registry."""
        pane = getattr(self, 'bound_pane', None)
        if pane is not None and worker is self.worker:
            # Watchers and tab commands consult the pane before queued results
            # have a chance to capture the live fields held by Window.
            pane.worker = worker
            pane.scanning = self.scanning
        return self.runtime_tasks.start(worker, name, cancellable)

    def show_header_menu(self, header, pos):
        menu = self.build_header_menu(header)
        menu.exec(header.mapToGlobal(pos))

    def add_grouped_column_actions(self, menu):
        """Dolphin's general entries and media submenus, using Mirivue fields."""
        for column in PRIMARY_COLUMNS:
            menu.addAction(self.column_actions[column])
        for label, columns in MEDIA_COLUMNS:
            submenu = menu.addMenu(tr(label))
            for column in columns:
                submenu.addAction(self.column_actions[column])

    def build_header_menu(self, header):
        pane = next((p for p in self.panes if p.table.horizontalHeader() is header), None)
        if pane is not None and pane is not self.bound_pane:
            self.activate_pane(pane)
        pane = pane or self.bound_pane
        self.sync_columns_menu()
        menu = QMenu(self)
        self.add_grouped_column_actions(menu)
        menu.addSeparator()
        profiles = menu.addMenu(tr('Configurations de colonnes'))
        for name in self.profile_names():
            profiles.addAction(name, lambda checked=False, n=name: self.apply_media_profile(n))
        fill_width = menu.addAction(tr('Étendre les colonnes à la largeur du panneau'))
        fill_width.setCheckable(True)
        fill_width.setChecked(pane.fill_view_width)
        fill_width.triggered.connect(lambda checked=False, p=pane: self.set_pane_fill_view_width(p, checked))
        width_modes = QActionGroup(menu)
        width_modes.setExclusive(True)
        automatic = menu.addAction(tr('Largeurs de colonnes automatiques'))
        automatic.setCheckable(True)
        automatic.setChecked(pane.column_width_mode == 'auto')
        custom = menu.addAction(tr('Largeurs de colonnes personnalisées'))
        custom.setCheckable(True)
        custom.setChecked(pane.column_width_mode == 'custom')
        width_modes.addAction(automatic)
        width_modes.addAction(custom)
        automatic.triggered.connect(lambda _checked=False, p=pane: self.set_pane_column_width_mode(p, 'auto'))
        custom.triggered.connect(lambda _checked=False, p=pane: self.set_pane_column_width_mode(p, 'custom'))
        self.reserve_submenu_tree(menu)
        return menu

    def show_configuration(self):
        from .configuration import show_configuration
        show_configuration(self)

    def sync_columns_menu(self):
        for column, action in enumerate(self.column_actions):
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(not self.table.isColumnHidden(column))
            action.blockSignals(False)

    def reset_columns(self):
        self.set_pane_column_width_mode(self.bound_pane, 'custom')
        self.set_pane_fill_view_width(self.bound_pane, False)
        header = self.table.horizontalHeader()
        widths = [240, 85, 85, 110, 90, 65, 160, 125, 100, 65, 125, 175, 125, 150, 175]
        for column in range(len(HEADERS)):
            header.moveSection(header.visualIndex(column), column)
            self.table.setColumnHidden(column, column not in (0, 1, 2, 14))
            self.table.setColumnWidth(column, widths[column] if column < len(widths) else 120)
        header.moveSection(header.visualIndex(14), header.visualIndex(1) + 1)
        header.setSectionsMovable(True)
        header.setFirstSectionMovable(False)
        header.setStretchLastSection(False)
        if header.visualIndex(0) != 0:
            header.moveSection(header.visualIndex(0), 0)
        self.sync_columns_menu()
        self.schedule_pane_column_save(self.bound_pane)

    def update_navigation(self):
        self.back.setEnabled(self.history_position > 0)
        self.forward.setEnabled(self.history_position < len(self.history) - 1)
        self.up.setEnabled(bool(self.folder and parent_location(self.folder) != self.folder))
        if hasattr(self, 'terminal_dock'):
            self.sync_terminal_directory()

    def navigate_history(self, offset):
        position = self.history_position + offset
        if 0 <= position < len(self.history):
            self.navigate(self.history[position], position)

    def populate_navigation_history(self, menu, direction):
        """Offer the active pane's back or forward history from the arrow menu."""
        menu.clear()
        positions = (range(self.history_position - 1, -1, -1) if direction < 0
                     else range(self.history_position + 1, len(self.history)))
        for position in list(positions)[:20]:
            location = self.history[position]
            action = menu.addAction(self.tab_title(location))
            action.setToolTip(str(location))
            action.triggered.connect(lambda checked=False, index=position:
                                     self.navigate(self.history[index], index))

    def navigate(self, folder, history_position=None):
        location = Location.from_value(folder)
        if location.is_uri:
            folder = location.uri
            if self.scanning:
                self.pending_navigation = (folder, history_position)
                self.cancel()
                return
            if self.search_active:
                self.reset_search_view()
                self.search_panel.hide()
                self.search_button.setChecked(False)
            if history_position is None:
                if folder != self.folder or self.history_position < 0:
                    self.history = self.history[:self.history_position + 1] + [folder]
                    self.history_position = len(self.history) - 1
            else:
                self.history_position = history_position
            self.parent_selection = None
            self.restore_folder_view(folder)
            self.folder = folder
            self.address.setText(folder)
            self.location.setText(folder)
            if hasattr(self, tr('bound_pane')) and self.bound_pane is not None:
                self.update_pane_path_bar(self.bound_pane)
            self.update_navigation()
            self.settings.setValue('folder', folder)
            self.remember_pane_folder(folder)
            self.scan()
            self.update_pane_titles()
            return
        path = Path(os.path.abspath(os.path.expanduser(folder)))
        if not path.is_dir():
            QMessageBox.warning(self, tr('Dossier introuvable'), tr('Ce dossier n’est pas accessible.'))
            return
        folder = str(path)
        if self.scanning:
            self.pending_navigation = (folder, history_position)
            self.cancel()
            return
        if self.search_active:
            self.reset_search_view()
            self.search_panel.hide()
            self.search_button.setChecked(False)
        if (hasattr(self, tr('bound_pane'))
                and self.settings.value('sorting/remember-per-folder', False, type=bool)):
            sorts = self.bound_pane.folder_sorts
            current = (self.table.horizontalHeader().sortIndicatorSection(), self.table.horizontalHeader().sortIndicatorOrder())
            if self.folder:
                sorts[self.folder] = current
            column, order = sorts.get(folder, current)
            self._restoring_folder_display = True
            try:
                self.table.sortByColumn(column, order)
            finally:
                self._restoring_folder_display = False
        self.restore_folder_view(folder)
        self.parent_selection = None
        if self.folder and path in Path(self.folder).parents:
            child = Path(self.folder).relative_to(path).parts[0]
            self.parent_selection = path / child
        if history_position is None:
            if folder != self.folder or self.history_position < 0:
                self.history = self.history[:self.history_position + 1] + [folder]
                self.history_position = len(self.history) - 1
        else:
            self.history_position = history_position
        if folder != self.folder:
            self.search.clear()
        self.folder = folder
        self.address.setText(folder)
        self.update_crumbs()
        if hasattr(self, tr('bound_pane')) and self.bound_pane is not None:
            self.update_pane_path_bar(self.bound_pane)
        self.update_disk_space()
        self.settings.setValue('folder', folder)
        index = self.filesystem.index(folder)
        self.browser.setCurrentIndex(index)
        self.browser.scrollTo(index)
        self.update_navigation()
        self.remember_pane_folder(folder)
        if hasattr(self, tr('media_profiles')):
            self.restore_media_profile(folder)
        self.scan()
        self.update_pane_titles()
        self.watch_visible_directories()

    def restore_parent_selection(self):
        target = self.parent_selection
        self.parent_selection = None
        if target is None:
            return
        for i, row in enumerate(self.model.rows):
            if row.path == target:
                index = map_file_index(self.proxy, self.model.index(i, 0))
                if index.isValid():
                    for view in (self.table, self.icons, self.compact):
                        view.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
                        view.scrollTo(index)
                break

    def selected_paths(self):
        return list(dict.fromkeys((self.row(index).path for index in self.selected_indexes() if not self.row(index).is_dir)))

    def refresh_delete_availability(self):
        """Update the shared Delete action before a pane can open its menu."""
        rows = [self.row(index) for index in self.selected_indexes()]
        self.delete_button.setEnabled(
            not self.scanning and not self.is_archive_view() and bool(rows)
            and not self.movement_locked([row.path for row in rows]))

    def update_delete_button(self, *args):
        busy = self.scanning
        read_only_archive = self.is_archive_view()
        rows = [self.row(i) for i in self.selected_indexes()]
        self.update_selection_info(rows)
        if hasattr(self, 'batch_rename_action'):
            self.update_main_menu_states(refresh_details=False)
        if hasattr(self, tr('incomplete_media_action')):
            count = self.model.incomplete_count
            self.incomplete_media_action.setText(trf('Médias incomplets (\x1f0\x1f)', count))
        if hasattr(self, tr('media_preview_timer')):
            self.schedule_media_preview()
        self.duplicate_action.setEnabled(not busy and len(self.model.rows) > 1)
        self.keep_one_action.setEnabled(not busy and bool(self.duplicate_groups))
        self.refresh_delete_availability()
        if hasattr(self, 'permanent_delete_action'):
            self.permanent_delete_action.setEnabled(self.delete_button.isEnabled())
        if hasattr(self, tr('rename_action')):
            self.rename_action.setEnabled(not busy and not read_only_archive and bool(rows))

    def current_place_entries(self):
        return list(getattr(self, '_current_places', ()))

    def add_place(self, path, label=None):
        url = QUrl.fromUserInput(str(path))
        if not url.isValid() or url.isEmpty():
            return False
        if url.isLocalFile():
            local_path = Path(url.toLocalFile())
            if not local_path.is_dir():
                return False
            label = label or local_path.name or tr('/')
        else:
            label = label or url.toDisplayString()
        ok, error = services.change_place('add', str(label), url.toString(QUrl.ComponentFormattingOption.FullyEncoded), 'folder-favorites')
        if ok:
            self.reload_places()
            self.show_activity_message(tr('Dossier ajouté aux emplacements.'), 4000)
        else:
            self.show_activity_message(error, 6000)
        return ok

    def is_trash_view(self):
        return bool(self.folder and QUrl(str(self.folder)).scheme().casefold() == 'trash')

    def restore_selected_from_trash(self):
        if not self.is_trash_view() or self.scanning:
            return
        sources = [str(self.row(index).path) for index in self.selected_indexes()]
        if sources:
            self.start_kio_transfer(
                sources, 'trash:/', operation='restore',
                on_success=self.reload_places,
            )

    def delete_selected_from_trash(self):
        """Permanently delete Trash URLs through KIO after confirmation."""
        if not self.is_trash_view() or self.scanning:
            return
        sources = [str(self.row(index).path) for index in self.selected_indexes()]
        if not sources or self.confirm_delete(sources, tr('permanent')) is None:
            return
        self.start_kio_transfer(
            sources, 'trash:/', operation='delete',
            on_success=self.reload_places,
        )

    def reload_places(self):
        # KFilePlacesView maintains its own live model. This snapshot is for
        # breadcrumb labels and relocation of bookmarks after a file move.
        places = services.list_places()
        if places is not None and not self.settings.value('migration/favorites-to-shared-places', False, type=bool):
            legacy = self.settings.value('favorites/paths', [])
            if isinstance(legacy, str):
                legacy = [legacy]
            try:
                labels = json.loads(self.settings.value('favorites/labels', tr('{}')))
            except (TypeError, ValueError):
                labels = {}
            migrated = True
            for raw in legacy or []:
                path = Path(str(raw)).expanduser()
                if not path.is_dir():
                    continue
                url = QUrl.fromLocalFile(str(path.resolve())).toString(QUrl.ComponentFormattingOption.FullyEncoded)
                ok, _error = services.change_place('add', str(labels.get(str(raw), path.name or tr('/'))), url, tr('folder-favorites'))
                migrated = migrated and ok
            if migrated:
                self.settings.setValue('migration/favorites-to-shared-places', True)
                self.settings.remove('favorites/paths')
                self.settings.remove('favorites/labels')
                self.settings.sync()
                places = services.list_places()
        if places is None:
            places = [dict(name=title, url=QUrl.fromLocalFile(str(Path(path))).toString(QUrl.ComponentFormattingOption.FullyEncoded), icon=icon, group=0)
                      for _group, title, path, icon in local_places()]
        else:
            data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
            bookmarks = kde_places_bookmarks(Path(data) / tr('user-places.xbel')) if data else []
            places = merge_kde_places(places, bookmarks)
        self._current_places = places
        if hasattr(self, 'panes'):
            for pane in self.panes:
                self.update_pane_path_bar(pane, force=True)
        if not hasattr(self, 'places_watcher'):
            self.places_watcher = QFileSystemWatcher(self)
            self.places_refresh_timer = QTimer(self)
            self.places_refresh_timer.setSingleShot(True)
            self.places_refresh_timer.setInterval(180)
            self.places_refresh_timer.timeout.connect(self.reload_places)
            self.places_watcher.directoryChanged.connect(lambda *_: self.places_refresh_timer.start())
            self.places_watcher.fileChanged.connect(lambda *_: self.places_refresh_timer.start())
        data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
        if data:
            bookmark_file = Path(data) / tr('user-places.xbel')
            if bookmark_file.parent.is_dir() and str(bookmark_file.parent) not in self.places_watcher.directories():
                self.places_watcher.addPath(str(bookmark_file.parent))
            if bookmark_file.is_file() and str(bookmark_file) not in self.places_watcher.files():
                self.places_watcher.addPath(str(bookmark_file))

    def clear_duplicates(self):
        if not self.duplicate_groups:
            return
        self.duplicate_groups = []
        library.write(self.settings, tr('duplicates'), [])
        for row in self.result_rows():
            row.duplicate_group = 0
        if self.model.rows:
            self.model.dataChanged.emit(self.model.index(0, 0), self.model.index(len(self.model.rows) - 1, len(HEADERS) - 1))

    def run_duplicate_worker(self, worker):
        self.stop_thumbnails()
        if self.worker:
            self.worker.deleteLater()
        self.worker = worker
        worker.current.connect(self.show_activity_message)
        worker.cleanup_warning.connect(self.notices.append)
        worker.finished.connect(self.pane_callback(self.finished))
        self.scanning = True
        self.choose.setEnabled(False)
        self.refresh.setEnabled(False)
        self.recursive.setEnabled(False)
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter le chargement du dossier'))
        self.bar.setRange(0, 0)
        self.bar.show()
        self.update_delete_button()
        self.start_runtime_worker(worker, tr('Recherche des doublons'))

    def start_duplicate_scan(self):
        if self.scanning:
            return
        paths = [self.row(self.proxy.index(i, 0)).path for i in range(self.proxy.rowCount()) if not self.row(self.proxy.index(i, 0)).is_dir]
        self.enqueue_analysis(tr('duplicates'), paths)

    def duplicates_found(self, groups):
        self.duplicate_groups = groups
        library.write(self.settings, tr('duplicates'), [{tr('digest'): g[tr('digest')], tr('files'): [(str(p), sig) for p, sig in g[tr('files')]]} for g in groups])
        membership = {p: number for number, group in enumerate(groups, 1) for p, sig in group[tr('files')]}
        rows = iter(self.result_rows())
        self._applying_results = True

        def apply_batch():
            deadline = time.monotonic() + 0.006
            self._receiving_result = True
            try:
                while time.monotonic() < deadline:
                    try:
                        row = next(rows)
                    except StopIteration:
                        self._applying_results = False
                        self.schedule_checkpoint()
                        if self.model.rows:
                            self.model.dataChanged.emit(
                                self.model.index(0, 0),
                                self.model.index(len(self.model.rows) - 1, len(HEADERS) - 1),
                            )
                        if self.search_active and self.search_criteria.get('state') == tr('Doublons exacts'):
                            self.proxy.state_filter = tr('Doublons exacts')
                            self.proxy.invalidateFilter()
                            self.search_duplicates_manage.setVisible(bool(groups))
                            self.update_summary()
                            if groups:
                                self.show_activity_message(
                                    trf('Recherche terminée : \x1f0\x1f groupe(s) de doublons exacts.', len(groups)),
                                    8000,
                                )
                            else:
                                self.show_activity_message(tr('Recherche terminée : aucun doublon exact.'), 8000)
                        return
                    previous = row.duplicate_group
                    row.duplicate_group = membership.get(row.path, 0)
                    if previous or row.duplicate_group:
                        self.save_result(row)
                        self._dirty_paths.add(row.path)
                        if self.active_job and row.path in self.active_job[tr('paths')]:
                            self.active_job.setdefault(tr('_encoded'), {})[row.path] = self.saved_results[str(row.path)]
            finally:
                self._receiving_result = False
                self.update_job_footer()
            QTimer.singleShot(1, apply_batch)
        apply_batch()

    def choose_duplicate_keeper(self):
        if self.scanning or not self.duplicate_groups:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Doublons : conserver un seul fichier'))
        dialog.resize(800, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(tr('Choisissez un groupe, puis le fichier à conserver. Les autres seront mis à la corbeille.')))
        groups = QComboBox()
        for i, g in enumerate(self.duplicate_groups, 1):
            groups.addItem(trf('Groupe \x1f0\x1f — \x1f1\x1f fichiers — ', i, len(g['files'])) + quantity((len(g[tr('files')]) - 1) * g[tr('files')][0][1][2], [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024) + tr(' récupérables'))
        layout.addWidget(groups)
        listing = QTreeWidget()
        listing.setHeaderLabels([tr('Fichiers du groupe'), tr('Taille')])
        listing.setColumnWidth(0, 600)
        layout.addWidget(listing)
        layout.addWidget(QLabel(tr('Conserver ce fichier :')))
        keeper = QComboBox()
        layout.addWidget(keeper)

        def populate(index):
            listing.clear()
            keeper.clear()
            for path, sig in self.duplicate_groups[index][tr('files')]:
                QTreeWidgetItem(listing, [str(path), quantity(sig[2], [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024)])
                keeper.addItem(str(path), path)
        groups.currentIndexChanged.connect(populate)
        populate(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        confirm = buttons.addButton(tr('Mettre les autres à la corbeille'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        group = self.duplicate_groups[groups.currentIndex()]
        if self.paths_locked([p for p, sig in group[tr('files')]]):
            QMessageBox.information(self, tr('Opérations en cours'), tr('Ce groupe est utilisé par une opération. Attendez sa fin.'))
            return
        selected_keeper = keeper.currentData()
        worker = DuplicateCleaner(group, selected_keeper)
        worker.verified.connect(self.pane_callback(
            lambda removed: self.trash_verified_duplicates(group, selected_keeper, removed)))
        self.run_duplicate_worker(worker)

    def trash_verified_duplicates(self, group, keeper, paths):
        """Use KDE confirmation and a single undoable trash job after hashing."""
        expected = dict(group[tr('files')])
        try:
            if (not paths or fingerprint(Path(keeper)) != expected[Path(keeper)]
                    or any(fingerprint(path) != expected[path] for path in paths)):
                raise OSError(tr('Un fichier a changé depuis la vérification.'))
        except (OSError, KeyError):
            QMessageBox.warning(self, tr('Doublons modifiés'), tr('Actualisez la recherche avant de mettre ces fichiers à la corbeille.'))
            return
        self.start_kio_transfer(
            [QUrl.fromLocalFile(str(path)).toString() for path in paths],
            'trash:/', operation='trash',
            on_success=self.pane_callback(lambda: self.duplicates_cleaned(paths)),
        )

    def duplicates_cleaned(self, removed):
        removed = set(removed)
        remaining = []
        for group in self.duplicate_groups:
            files = [(p, sig) for p, sig in group[tr('files')] if p not in removed]
            if len(files) > 1:
                remaining.append(dict(digest=group[tr('digest')], files=files))
        self.model.beginResetModel()
        self.model.rows = [r for r in self.model.rows if r.path not in removed]
        self.model.endResetModel()
        self.duplicates_found(remaining)

    def show_file_error(self, row):
        errors = [text for text in (row.error, row.bitrate_error, row.validation_error) if text]
        box = QMessageBox(self)
        box.setWindowTitle(tr('Erreur — ') + row.path.name)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(tr('\n\n').join(dict.fromkeys((explain_error(error) for error in errors))))
        box.setDetailedText(tr('\n\n').join(errors))
        copy = box.addButton(tr('Créer une copie MKV compatible, sans réencodage…'), QMessageBox.ButtonRole.ActionRole) if row.is_video and getattr(row, tr('mkv_copy_recommended'), False) else None
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if copy is not None and box.clickedButton() is copy:
            self.offer_mkv_copy(row)

    def deep_result(self, path, result):
        bitrate, seconds, packets, clock = result
        for index, row in self.result_entries(path):
            if row.path == path:
                row.bitrate_result = tuple(result)
                preserve = (self.active_job or {}).get(tr('preserve'), self.settings.value('embed/preserve', True, type=bool))
                if preserve and row.original_bitrate and (row.original_bitrate > 0):
                    row.bitrate_error = ''
                    row.bitrate_note = tr('Débit du fichier conservé. Le débit calculé reste consultable dans les détails techniques.')
                    self.repaint_panes()
                    break
                row.bitrate_saved = False
                row.sort_values[6] = bitrate
                row.values[6] = quantity(bitrate, [tr('bit/s'), tr('kbit/s'), tr('Mbit/s'), tr('Gbit/s')], 1000) + tr(' (calculé)')
                row.values[10] = row.sort_values[10] = tr('Débit calculé')
                row.bitrate_error = ''
                row.mkv_copy_recommended = False
                row.bitrate_note = trf('Débit moyen de la première piste vidéo : \x1f0\x1f paquets / \x1f1\x1f s (\x1f2\x1f). Audio et conteneur exclus.', packets, format(seconds, '.6f'), clock)
                self._dirty_paths.add(path)
                self.update_job_footer()
                break
        self.update_summary()

    def deep_stored(self, path, backup):
        from .backup_policy import legacy_backups
        self.clear_duplicates()
        for index, row in self.result_entries(path):
            if row.path == path:
                row.bitrate_saved = True
                row.original_bitrate = row.bitrate_result[0] if row.bitrate_result else row.sort_values[6]
                row.sort_values[6] = row.original_bitrate
                row.bitrate_error = ''
                row.mkv_copy_recommended = False
                row.values[6] = quantity(row.sort_values[6], [tr('bit/s'), tr('kbit/s'), tr('Mbit/s'), tr('Gbit/s')], 1000)
                row.values[10] = row.sort_values[10] = tr('Débit enregistré')
                row.bitrate_note += trf(' Métadonnées intégrées. Original : \x1f0\x1f', backup) if backup else tr(' Métadonnées intégrées.')
                row.bitrate_note += tr(' Anciennes sauvegardes conservées à côté du fichier.') if legacy_backups(path) else ''
                try:
                    row.file_signature = fingerprint(path)
                    update_modification(row)
                    row.sort_values[1] = path.stat().st_size
                    row.values[1] = quantity(row.sort_values[1], [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024)
                except OSError:
                    row.file_signature = None
                self._dirty_paths.add(path)
                self.update_job_footer()
                break
        self.update_summary()

    def deep_storage_failure(self, path, error):
        for index, row in self.result_entries(path):
            if row.path == path:
                row.bitrate_error = tr('Enregistrement impossible : ') + error
                row.mkv_copy_recommended = self.mkv_copy_is_relevant(error)
                row.values[10] = row.sort_values[10] = tr('Calculé, non enregistré')
                self._dirty_paths.add(path)
                self.update_job_footer()
                break
        self.update_summary()

    def deep_failure(self, path, error):
        for index, row in self.result_entries(path):
            if row.path == path:
                row.bitrate_error = error
                row.values[10] = row.sort_values[10] = tr('Débit non calculé')
                self._dirty_paths.add(path)
                self.update_job_footer()
                break
        self.update_summary()

    def confirm_delete(self, paths, requested_mode=None):
        # DeleteOrTrashJob applies KDE's independent Trash/Delete confirmation
        # settings in its native dialog, after the preflight checks below.
        return tr('permanent') if requested_mode == tr('permanent') else tr('trash')

    def delete_selected(self, requested_mode=None):
        if self.is_archive_view():
            return
        paths = self.selected_entries()
        if not paths or self.scanning:
            return
        paths = self.choose_associated_entries(paths, tr('suppression'), include_xmp=True)
        if paths is None:
            return
        if selected_mount_points(paths):
            QMessageBox.warning(self, tr('Suppression impossible'), tr('Impossible de supprimer la racine d’une partition.'))
            return False
        if self.movement_locked(paths):
            QMessageBox.information(self, tr('Opérations en cours'), tr('Un élément sélectionné ou un fichier de ce dossier est utilisé par une opération. Attendez sa fin ou annulez-la.'))
            return False
        try:
            signatures = {p: fingerprint(p) for p in paths}
        except OSError:
            QMessageBox.warning(self, tr('Sélection modifiée'), tr('Un élément n’est plus accessible. Actualisez la vue avant de recommencer.'))
            return
        mode = self.confirm_delete(paths, requested_mode)
        if mode is None:
            return
        if self.movement_locked(paths):
            return False
        try:
            if any((fingerprint(p) != sig for p, sig in signatures.items())):
                raise OSError(tr('La sélection a changé pendant la confirmation.'))
        except OSError:
            QMessageBox.warning(self, tr('Sélection modifiée'), tr('La sélection a changé. Actualisez la vue puis recommencez.'))
            return
        return self.start_kio_transfer(
            [QUrl.fromLocalFile(str(path)).toString() for path in paths],
            tr('trash:/'), operation=tr('trash') if mode == tr('trash') else tr('delete'),
            on_success=self.reload_places,
        )

    def pick(self):
        folder = QFileDialog.getExistingDirectory(self, tr('Ouvrir un dossier'), self.settings.value('folder', str(Path.home())))
        if folder:
            self.navigate(folder)

    def scan(self):
        if not self.folder or self.scanning:
            return
        if Location.from_value(self.folder).is_uri:
            return self.scan_kio()
        self.scan_queued = False
        self.cancel_duration_lookups(self.bound_pane)
        self.stop_thumbnails()
        if self.folder_size_worker:
            self.folder_size_worker.cancel()
            # Keep the worker alive until its finished handler can remove it.
            self.folder_size_worker = None
        self.model.clear()
        self.model.pending_preliminary = []
        self.model.pending_resolved = []
        self.model.preliminary_draining = False
        self.model.resolved_draining = False
        header = self.table.horizontalHeader()
        # Keep the proxy sorted while entries arrive.  Disabling dynamic
        # sorting here used to expose the scanner's enumeration order, then
        # move the whole directory at once when the scan finished.  Dolphin's
        # item model maintains the selected sort as entries are inserted.
        self.proxy.setDynamicSortFilter(True)
        self.proxy.sort(header.sortIndicatorSection(), header.sortIndicatorOrder())
        self.model.other_rows = {r.path: r for p in self.panes if p.model is not self.model for r in p.model.rows if r.path not in p.model.preliminary and r.metadata_loaded}
        self.update_delete_button()
        self.notices = []
        self.location.setText(self.folder)
        self.bar.setRange(0, 0)
        self.choose.setEnabled(False)
        self.refresh.setEnabled(False)
        self.recursive.setEnabled(False)
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter le chargement du dossier'))
        if self.worker:
            self.worker.deleteLater()
        self.worker = Scanner(self.folder, self.recursive.isChecked(), self.hidden.isChecked())
        pane = self.bound_pane
        self.worker.initial.connect(lambda rows, p=pane: self.run_in_pane_silent(p, self.set_initial_listing, rows))
        self.worker.listed.connect(lambda rows, p=pane: self.queue_preliminary(p, rows))
        self.worker.resolved.connect(lambda rows, p=pane: self.queue_resolved(p, rows))
        self.worker.progress.connect(self.pane_callback(self.progress))
        self.worker.notice.connect(self.notices.append)
        self.worker.finished.connect(self.pane_callback(self.finished))
        self.scanning = True
        self.schedule_folder_progress()
        self.update_empty_state()
        self.start_runtime_worker(self.worker, tr('Chargement du dossier'))
        self.update_delete_button()
        self.update_summary()

    def queue_pane_rescan(self, pane):
        """Refresh a transfer destination after any listing already in flight."""
        if pane.scanning:
            if isinstance(pane.worker, (Scanner, KioScanner)):
                pane.scan_queued = True
        else:
            self.run_in_pane(pane, self.scan)

    def restore_transfer_selection(self):
        """Select arrivals only after the destination's final KIO refresh."""
        pane = self.bound_pane
        pending = getattr(pane, 'pending_transfer_selection', None)
        pane.pending_transfer_selection = None
        if not pending or pending[0] != self.folder:
            return
        wanted = pending[1]
        selected = []
        for row_number, row in enumerate(self.model.rows):
            name = row.path.name if isinstance(row.path, Path) else QUrl(str(row.path)).path().rstrip('/').rsplit('/', 1)[-1]
            if name in wanted:
                index = map_file_index(self.proxy, self.model.index(row_number, 0))
                if index.isValid():
                    selected.append(index)
        for view in (self.table, self.icons, self.compact):
            selection = view.selectionModel()
            selection.clearSelection()
            for index in selected:
                selection.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            if selected:
                selection.setCurrentIndex(selected[0], QItemSelectionModel.SelectionFlag.NoUpdate)
        if selected:
            self.active_view().scrollTo(selected[0])

    def scan_kio(self):
        """List a remote URI through the native KIO bridge."""
        if self.scanning:
            return
        self.cancel_duration_lookups(self.bound_pane)
        self.stop_thumbnails()
        self.model.clear()
        self.model.pending_preliminary = []
        self.model.pending_resolved = []
        self.model.preliminary_draining = False
        self.model.resolved_draining = False
        self.notices = []
        self.location.setText(self.folder)
        self.bar.setRange(0, 0)
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter le chargement du dossier'))
        self.choose.setEnabled(False)
        self.refresh.setEnabled(False)
        self.recursive.setEnabled(False)
        if self.worker:
            self.worker.deleteLater()
        self.worker = KioScanner(self.folder, self.hidden.isChecked())
        pane = self.bound_pane
        self.worker.listed.connect(lambda rows, p=pane, w=self.worker: self.accept_kio_listing(p, w, rows))
        self.worker.notice.connect(self.notices.append)
        self.worker.finished.connect(self.pane_callback(self.finished))
        self.scanning = True
        self.schedule_folder_progress()
        self.update_empty_state()
        self.start_runtime_worker(self.worker, tr('Chargement KIO'))
        self.update_delete_button()
        self.update_summary()

    def update_empty_state(self):
        if self.scanning and isinstance(self.worker, RecursiveSearchWorker):
            message = tr('Recherche en cours…')
        elif self.scanning:
            message = tr('Chargement du dossier…')
        elif self.model.rows:
            message = ''
        elif self.search_active:
            message = tr('Aucun résultat dans ce dossier et ses sous-dossiers.')
        else:
            message = tr('Ce dossier est vide.\nVous pouvez y déposer des fichiers ou des dossiers.')
        for view in (self.table, self.icons, self.compact):
            view.empty_message = message
            view.viewport().update()

    def add_preliminary(self, rows):
        tr('Throttle model inserts: Qt must get time to repaint and cancel.')
        model = self.model
        model.pending_preliminary.extend(rows)
        if model.preliminary_draining:
            return
        model.preliminary_draining = True
        pane = self.bound_pane

        def drain():
            if self.closing or getattr(pane, '_closed', False):
                return

            def apply():
                chunk = model.pending_preliminary[:256]
                del model.pending_preliminary[:256]
                for row in chunk:
                    if row.media_type in (tr('video'), tr('audio'), tr('image')):
                        row.duplicate_group = next((i for i, group in enumerate(self.duplicate_groups, 1) if any((path == row.path and signature == row.file_signature for path, signature in group[tr('files')]))), 0)
                        self.apply_personal_label(row)
                model.add_preliminary(chunk)
                self.update_empty_state()
                self.schedule_scan_summary()
            self.run_in_pane_silent(pane, apply)
            if model.pending_preliminary:
                QTimer.singleShot(1, drain)
            else:
                model.preliminary_draining = False
        QTimer.singleShot(0, drain)

    def set_initial_listing(self, rows):
        """Publish a stable, sorted directory inventory in a single paint."""
        model = self.model
        prepared = list(rows)
        for row in prepared:
            if row.media_type in (tr('video'), tr('audio'), tr('image')):
                row.duplicate_group = next((i for i, group in enumerate(self.duplicate_groups, 1)
                                            if any((path == row.path and signature == row.file_signature
                                                    for path, signature in group[tr('files')]))), 0)
                self.apply_personal_label(row)
        model.beginResetModel()
        model.rows = prepared
        model.preliminary = {
            row.path: index for index, row in enumerate(prepared)
            if row.values[10] == tr('Lecture des informations…')
        }
        model.thumbnails.clear()
        model.endResetModel()
        self.update_empty_state()
        self.update_summary()

    def add_resolved(self, rows):
        tr('Apply metadata in modest batches so two panels stay responsive.')
        model = self.model
        model.pending_resolved.extend(rows)
        if model.resolved_draining:
            return
        model.resolved_draining = True
        pane = self.bound_pane

        def drain():
            if self.closing or getattr(pane, '_closed', False):
                return
            if model.pending_preliminary or model.preliminary_draining:
                QTimer.singleShot(1, drain)
                return

            def apply():
                chunk = model.pending_resolved[:16]
                del model.pending_resolved[:16]
                for row in chunk:
                    self.add(row)
            self.run_in_pane_silent(pane, apply)
            if model.pending_resolved:
                QTimer.singleShot(1, drain)
            else:
                model.resolved_draining = False
        QTimer.singleShot(0, drain)

    def queue_preliminary(self, pane, rows):
        self.run_in_pane_silent(pane, self.add_preliminary, rows)

    def queue_resolved(self, pane, rows):
        self.run_in_pane_silent(pane, self.add_resolved, rows)

    def cancel_duration_lookups(self, pane=None):
        pane_id = id(pane) if pane is not None else None
        for worker in tuple(self._duration_workers):
            if pane_id is None or worker.pane_id == pane_id:
                worker.requestInterruption()

    def visible_duration_paths(self, pane, candidates):
        """Sample the actual viewport, so the first results appear where the user looks."""
        view = pane.content_stack.currentWidget()
        viewport = view.viewport()
        rect = viewport.rect()
        if not view.isVisible() or rect.isEmpty():
            return ()
        wanted = set(candidates)
        visible = set()
        for y in range(rect.top() + 1, rect.bottom() + 1, 40):
            for x in range(rect.left() + 1, rect.right() + 1, 80):
                index = view.indexAt(QPoint(x, y))
                if index.isValid():
                    row = pane.proxy.mapToSource(index).row()
                    if 0 <= row < len(pane.model.rows):
                        path = pane.model.rows[row].path
                        if path in wanted:
                            visible.add(path)
        return visible

    def start_duration_lookup(self, pane, paths):
        from .media import AUDIO_EXT, IMAGE_EXT
        from .metadata import EXTENSIONS
        supported = EXTENSIONS | AUDIO_EXT | IMAGE_EXT
        candidates = tuple(dict.fromkeys(Path(path) for path in paths
                                         if Path(path).is_file() and Path(path).suffix.casefold() in supported))
        if not candidates or self.closing:
            return
        visible = self.visible_duration_paths(pane, candidates)
        for worker in tuple(self._duration_workers):
            if worker.pane_id == id(pane) and not worker.isInterruptionRequested():
                worker.queue.add(candidates, visible)
                if len(candidates) > 8:
                    worker.avoid_baloo = True
                return
        worker = DurationLookupWorker(candidates, id(pane), visible, self)
        self._duration_workers.append(worker)
        worker.found.connect(lambda path, signature, values, p=pane: self.run_in_pane_silent(p, self.apply_quick_metadata, path, signature, values))

        def finished():
            if worker in self._duration_workers:
                self._duration_workers.remove(worker)
            # An arrival can be queued just as run() observes an empty queue.
            remaining = worker.queue.drain()
            if remaining and not getattr(pane, '_closed', False) and not worker.isInterruptionRequested() and not self.closing:
                self.start_duration_lookup(pane, remaining)
            worker.deleteLater()
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Lecture rapide des métadonnées'))

    def apply_quick_metadata(self, path, signature, values):
        try:
            if fingerprint(path) != tuple(signature):
                return
        except OSError:
            return
        for index in self.model.positions_for_path(path):
            row = self.model.rows[index]
            if row.is_dir:
                continue
            from .metadata import duration, quantity
            changed = []
            seconds = values.get('duration')
            if seconds and seconds > 0 and row.sort_values[2] < 0:
                row.sort_values[2], row.values[2] = seconds, duration(seconds)
                changed.append(2)
            width, height = values.get('width'), values.get('height')
            if width and height and row.sort_values[3] < 0:
                row.sort_values[3] = width * height
                row.values[3] = f'{int(width)} × {int(height)}'
                changed.append(3)
            for column, key in ((4, 'video_codec'), (8, 'audio_codec')):
                if values.get(key) and not row.values[column]:
                    row.values[column] = str(values[key])
                    row.sort_values[column] = str(values[key]).casefold()
                    changed.append(column)
            for column, key in ((5, 'fps'), (9, 'channels'), (24, 'sample_rate')):
                value = values.get(key)
                if value and row.sort_values[column] < 0:
                    row.sort_values[column] = value
                    row.values[column] = str(int(value)) if column != 5 else f'{value:g}'
                    changed.append(column)
            for column, key in ((6, 'video_bitrate'), (25, 'audio_bitrate')):
                value = values.get(key)
                if value and row.sort_values[column] < 0:
                    row.sort_values[column] = value
                    row.values[column] = quantity(value, ['bit/s', 'kbit/s', 'Mbit/s', 'Gbit/s'], 1000)
                    changed.append(column)
            if changed:
                self.model.dataChanged.emit(self.model.index(index, min(changed)), self.model.index(index, max(changed)), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole])
            break

    def schedule_scan_summary(self):
        pane = self.bound_pane
        if getattr(pane, tr('summary_pending'), False):
            return
        pane.summary_pending = True

        def update():
            pane.summary_pending = False
            if not self.closing:
                self.run_in_pane(pane, self.update_summary)
        QTimer.singleShot(150, self, update)

    def add(self, video):
        from .media import kind
        media_kind = kind(video)
        hidden_state = video.is_hidden
        tags = dict(video.media_tags)
        technical = dict(video.media_technical)
        native_rate = video.original_bitrate
        native_label = video.values[6]
        if str(video.path) in self.saved_results:
            try:
                saved = library.decode_row(self.saved_results[str(video.path)])
                if saved.is_video == video.is_video and saved.is_dir == video.is_dir and (kind(saved) == kind(video)) and (saved.companion_signature == video.companion_signature) and (saved.file_signature is not None) and (saved.file_signature == video.file_signature):
                    video = saved
            except (ValueError, TypeError, KeyError):
                pass
        cached = self.result_cache.get(video.path)
        if cached is None and hasattr(self, tr('panes')):
            cached = getattr(self.model, tr('other_rows'), {}).get(video.path)
        if cached is not None and cached.is_video == video.is_video and (cached.is_dir == video.is_dir) and (kind(cached) == kind(video)) and (cached.companion_signature == video.companion_signature) and (video.file_signature is not None) and (cached.file_signature == video.file_signature):
            video = cached
        video.is_hidden = hidden_state
        video.media_type = media_kind
        video.media_tags = tags
        video.media_technical = technical
        video.original_bitrate = native_rate
        if native_rate and native_rate > 0 and self.settings.value('embed/preserve', True, type=bool):
            video.values[6] = native_label
            video.sort_values[6] = native_rate
        video.duplicate_group = next((i for i, g in enumerate(self.duplicate_groups, 1) if any((p == video.path and sig == video.file_signature for p, sig in g[tr('files')]))), 0)
        self.apply_personal_label(video)
        self.model.add(video)
        if self.scanning:
            self.schedule_scan_summary()
        else:
            self.update_summary()

    def progress(self, done, total):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(done)
        self.bar.setFormat(trf('\x1f0\x1f / \x1f1\x1f fichiers analysés', done, total))

    def update_summary(self):
        if self._receiving_result:
            return
        for i, row in enumerate(self.model.rows):
            base = row.values[10].split(tr(' • '))[0]
            state = base + (tr(' • ') + row.validation_status if row.validation_status else '') + (trf(' • Doublon groupe \x1f0\x1f', row.duplicate_group) if row.duplicate_group else '') + (trf(' • \x1f0\x1f', row.personal_label) if row.personal_label else '')
            if state != row.values[10]:
                row.values[10] = row.sort_values[10] = state
                self.model.dataChanged.emit(self.model.index(i, 10), self.model.index(i, 10))
        errors = sum((bool(row.error or row.bitrate_error or row.validation_error) for row in self.model.rows))
        self.summary.setText(trf('\x1f0\x1f affichée(s) / \x1f1\x1f élément(s) • \x1f2\x1f erreur(s)', self.proxy.rowCount(), len(self.model.rows), errors))
        if self.duplicate_groups:
            self.summary.setText(self.summary.text() + trf(' • \x1f0\x1f groupe(s) de doublons', len(self.duplicate_groups)))
        if self.search.text():
            self.summary.setText(self.summary.text() + tr(' • Recherche : ') + self.search.text())
        has_errors = bool(errors or self.notices)
        self.errors.setEnabled(has_errors)
        self.errors.setVisible(has_errors)
        self.errors_slot.setVisible(has_errors)
        self.update_activity_entry_points()
        for pane in getattr(self, tr('panes'), ()):
            self.update_pane_footer(pane)
        self.update_delete_button()

    def cancel(self):
        archive_worker = getattr(self, 'archive_extract_worker', None)
        if archive_worker is not None:
            archive_worker.requestInterruption()
            self.stop.setEnabled(False)
            self.stop.setText(tr('Annulation…'))
            self.show_activity_message(tr('Annulation de l’extraction…'))
            return
        if self.worker:
            self.worker.cancel()
            self.stop.setEnabled(False)
            self.stop.setText(tr('Annulation…'))

    def finished(self):
        if getattr(self.model, tr('preliminary_draining'), False) or getattr(self.model, tr('resolved_draining'), False):
            QTimer.singleShot(5, self.pane_callback(self.finished))
            return
        self.scanning = False
        self.update_empty_state()
        self.update_pane_titles()
        cancelled = self.worker.cancelled
        if isinstance(self.worker, Scanner):
            for index in self.model.preliminary.values():
                row = self.model.rows[index]
                if row.is_video:
                    row.values[10] = row.sort_values[10] = tr('Informations détaillées non lues')
            self.model.preliminary.clear()
            self.model.other_rows = {}
            if self.model.rows:
                self.model.dataChanged.emit(self.model.index(0, 10), self.model.index(len(self.model.rows) - 1, 10))
        self.choose.setEnabled(True)
        self.refresh.setEnabled(True)
        self.recursive.setEnabled(True)
        self.stop.setEnabled(False)
        self.stop.setText(tr('Arrêter le chargement du dossier'))
        self.search_start.setEnabled(True)
        self.search_scope.setEnabled(True)
        self.search_kind.setEnabled(True)
        self.state_filter.setEnabled(True)
        self.search_more.setEnabled(True)
        self.refresh_scan_progress_visibility()
        self.update_summary()
        has_errors = bool(self.notices or any((r.error or r.bitrate_error or r.validation_error for r in self.model.rows)))
        if isinstance(self.worker, RecursiveSearchWorker):
            result_count = self.proxy.rowCount()
            if cancelled:
                self.show_activity_message(
                    trf('Recherche interrompue — \x1f0\x1f résultat(s) partiel(s).', result_count), 6000
                )
            elif has_errors:
                self.show_activity_message(
                    trf('Recherche terminée avec des emplacements inaccessibles : \x1f0\x1f résultat(s).', result_count),
                    8000,
                )
            else:
                self.show_activity_message(
                    trf('Recherche terminée : \x1f0\x1f résultat(s) parmi \x1f1\x1f élément(s) examiné(s).', result_count, self.worker.scanned),
                    6000,
                )
        elif cancelled:
            self.show_activity_message(tr('Analyse annulée — résultats partiels conservés.'), 6000)
        elif has_errors:
            self.show_activity_message(tr('Analyse terminée avec erreurs — voir les erreurs.'))
        elif isinstance(self.worker, Scanner):
            # A normal folder load needs no permanent commentary: the rows and
            # counters already confirm success.  Leave room for useful events.
            self.clear_activity_message()
        else:
            self.show_activity_message(tr('Analyse terminée.'), 6000)
        if (isinstance(self.worker, RecursiveSearchWorker) and not cancelled
                and self.search_criteria.get('duplicates')):
            QTimer.singleShot(0, self.pane_callback(self.start_search_duplicate_analysis))
        self.update_delete_button()
        if isinstance(self.worker, Scanner) and (not cancelled):
            self.start_duration_lookup(
                self.bound_pane,
                [row.path for row in self.model.rows
                 if not row.is_dir and row.media_type in (tr('video'), tr('audio'), tr('image'))],
            )
            self.restore_parent_selection()
            pane = self.bound_pane
            if not getattr(pane, 'external_request_pending', False) and getattr(self, 'pending_external_files', []):
                pane.external_request_pending = True
                pane.pending_external_files = self.pending_external_files
                pane.pending_external_properties = self.pending_external_properties
                self.pending_external_files = []
                self.pending_external_properties = False
            self.apply_external_selection(pane)
            QTimer.singleShot(0, self.pane_callback(self.start_folder_sizes))
        if isinstance(self.worker, KioScanner) and not cancelled:
            self.apply_external_selection(self.bound_pane)
        if self.closing:
            self.close()
        elif self.pending_navigation is not None:
            folder, position = self.pending_navigation
            self.pending_navigation = None
            self.navigate(folder, position)
        if isinstance(self.worker, DuplicateScanner) and (not cancelled):
            self.show_activity_message(trf('Recherche terminée : \x1f0\x1f groupe(s) de doublons exacts.', len(self.duplicate_groups)), 8000)
        if self.scan_queued and not self.closing and not self.scanning and not getattr(self.bound_pane, 'pending_live_search', False):
            # A transfer finished while this pane was already being listed.
            # The completed listing may predate the destination entry.
            self.scan_queued = False
            QTimer.singleShot(0, self.pane_callback(self.scan))
        else:
            if isinstance(self.worker, (Scanner, KioScanner)) and not cancelled and self.pending_navigation is None:
                self.restore_transfer_selection()
            if not isinstance(self.worker, (KioScanner, RecursiveSearchWorker)):
                QTimer.singleShot(0, self.pane_callback(self.start_thumbnails))
        if getattr(self.bound_pane, 'pending_live_search', False) and not self.closing and self.pending_navigation is None:
            self.bound_pane.pending_live_search = False
            if not self.search_panel.isHidden():
                QTimer.singleShot(0, self.pane_callback(self.start_unified_search))

    def start_folder_sizes(self):
        if self.closing or self.scanning:
            return
        folders = [row.path for row in self.model.rows if row.is_dir and isinstance(row.path, Path)]
        if not folders:
            return
        if self.folder_size_worker:
            self.folder_size_worker.cancel()
            # The previous pane's finished handler will release it safely.
        mode = str(self.settings.value('view/folder-size-display', 'count'))
        mode = mode if mode in ('count', 'size') else 'count'
        worker = FolderSizeWorker(folders, mode)
        self.folder_size_worker = worker

        def update(results, result_mode):
            if self.folder_size_worker is worker:
                self.set_folder_sizes(results, result_mode)
        worker.results_ready.connect(self.pane_callback(update))

        def complete():
            if self.folder_size_worker is worker:
                self.folder_size_worker = None
            worker.deleteLater()
        worker.finished.connect(self.pane_callback(complete))
        self.start_runtime_worker(worker, tr('Calcul des dossiers'))
        QTimer.singleShot(0, self.watch_visible_directories)

    def row(self, index):
        return self.model.rows[self.proxy.mapToSource(index).row()]

    def open_url(self, path):
        location = Location.from_value(path)
        if location.is_uri:
            if not services.open_kio_location(location.uri):
                QMessageBox.warning(self, tr('Ouverture impossible'), tr('Aucune application ne peut ouvrir cet emplacement.'))
            return
        if not path.exists():
            QMessageBox.warning(self, tr('Fichier introuvable'), tr('Ce fichier ou dossier a été déplacé ou supprimé.'))
            return
        self.remember_recent(path)
        if not services.open_default_file(path):
            QMessageBox.warning(self, tr('Ouverture impossible'), tr('Aucune application par défaut ne permet cette ouverture.'))

    def open_video(self, index):
        row = self.row(index)
        if row.is_dir:
            self.navigate(str(row.path))
        elif not self.is_archive_view() and not Location.from_value(row.path).is_uri and archive_protocol(row.path):
            self.open_archive(row.path)
        else:
            self.open_url(row.path)

    def is_archive_view(self):
        if not self.folder:
            return False
        return QUrl(str(self.folder)).scheme().casefold() in ARCHIVE_PROTOCOLS

    def open_archive(self, path):
        target = archive_url(path)
        if target and services.is_plasma:
            self.navigate(target)
        else:
            self.open_url(path)

    def start_ark(self, arguments):
        ark = services.tool_path(tr('ark'))
        if not ark:
            record_tool_failure(tr('ark'), tr('Ark est absent.'))
            QMessageBox.information(self, tr('Ark indisponible'), tr('Installez Ark pour créer ou extraire des archives avec les outils KDE.'))
            return False
        started = QProcess.startDetached(ark, list(map(str, arguments)))
        ok = started[0] if isinstance(started, tuple) else bool(started)
        if not ok:
            record_tool_failure(tr('ark'), tr('Ark n’a pas pu être démarré.'))
            QMessageBox.warning(self, tr('Ark indisponible'), tr('Ark n’a pas pu être démarré.'))
        return ok

    def create_archive(self):
        if self.scanning or not self.folder or Location.from_value(self.folder).is_uri:
            return
        paths = [self.row(index).path for index in self.selected_indexes()]
        if not paths or not all(isinstance(path, Path) and path.exists() for path in paths):
            return
        self.start_ark([tr('--add'), *paths])

    def extract_archive(self, path, destination=None, trash_after=False, create_destination=False):
        if self.scanning:
            return
        if not (isinstance(path, Path) and path.is_file() and archive_protocol(path)):
            return
        if getattr(self, 'archive_extract_worker', None) is not None or getattr(self, 'kio_transfer_worker', None) is not None:
            return
        if destination is None:
            destination = QFileDialog.getExistingDirectory(self, tr('Extraire vers…'), str(path.parent))
        if not destination:
            return
        destination = Path(destination)
        if create_destination:
            try:
                destination.mkdir(parents=False, exist_ok=True)
            except OSError as error:
                QMessageBox.warning(
                    self, tr('Extraction impossible'),
                    trf('Le dossier d’extraction n’a pas pu être créé : \x1f0\x1f', error))
                return
        if archive_protocol(path) == 'rar':
            self.start_rar_extraction(path, destination, trash_after)
            return
        source = archive_url(path)
        if not source:
            return

        worker = ArchiveEntriesWorker(source, self)
        self.archive_extract_worker = worker
        self._archive_extract_stop_state = (self.stop.isEnabled(), self.stop.text())
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter l’extraction'))
        self.bar.setRange(0, 0)
        self.bar.setFormat(tr('Préparation de l’extraction…'))
        self.bar.show()

        def finish_preparation():
            if self.archive_extract_worker is not worker:
                return False
            self.archive_extract_worker = None
            self.bar.hide()
            previous = getattr(self, '_archive_extract_stop_state', None)
            if previous is not None:
                self.stop.setEnabled(previous[0])
                self.stop.setText(previous[1])
            self._archive_extract_stop_state = None
            return True

        def complete(entries, error):
            if not finish_preparation():
                return
            if worker.isInterruptionRequested():
                self.show_activity_message(tr('Extraction annulée.'), 5000)
                return
            if error:
                QMessageBox.warning(self, tr('Extraction impossible'), error)
                return
            sources = []
            for entry in entries:
                name = str(entry.get('name') or '')
                if not safe_archive_entry_name(name):
                    continue
                url = str(entry.get('url') or '')
                if not url:
                    child = QUrl(source)
                    child.setPath(child.path().rstrip('/') + '/' + name)
                    url = child.toString()
                if url not in sources:
                    sources.append(url)
            if not sources:
                QMessageBox.information(self, tr('Archive vide'), tr('Cette archive ne contient aucun élément à extraire.'))
                return
            target = QUrl.fromLocalFile(str(destination.absolute())).toString()
            after = None
            if trash_after:
                archive_url_value = QUrl.fromLocalFile(str(path.absolute())).toString()
                after = lambda: self.start_kio_transfer(
                    [archive_url_value], tr('trash:/'), operation=tr('trash'))
            self.start_kio_transfer(
                sources, target, move=False, operation=tr('extract'),
                on_success=after)

        worker.completed.connect(complete)
        worker.finished.connect(finish_preparation)
        worker.finished.connect(worker.deleteLater)
        self.start_runtime_worker(worker, tr('Préparation de l’extraction'))

    def start_rar_extraction(self, path, destination, trash_after=False):
        worker = RarExtractWorker(path, destination, self)
        self.archive_extract_worker = worker
        self._archive_extract_stop_state = (self.stop.isEnabled(), self.stop.text())
        self.stop.setEnabled(True)
        self.stop.setText(tr('Arrêter l’extraction'))
        self.bar.setRange(0, 0)
        self.bar.setFormat(tr('Extraction RAR avec Ark…'))
        self.bar.show()

        def update(value, message):
            if value >= 100:
                self.bar.setRange(0, 100)
                self.bar.setValue(100)
            self.bar.setFormat(message)

        def complete(ok, error):
            if self.archive_extract_worker is not worker:
                return
            self.archive_extract_worker = None
            self.bar.hide()
            previous = getattr(self, '_archive_extract_stop_state', None)
            if previous is not None:
                self.stop.setEnabled(previous[0])
                self.stop.setText(previous[1])
            self._archive_extract_stop_state = None
            if not ok:
                if worker.isInterruptionRequested():
                    self.show_activity_message(tr('Extraction annulée.'), 5000)
                else:
                    QMessageBox.warning(self, tr('Extraction impossible'), error or tr('L’extraction RAR a échoué.'))
                return
            self.show_activity_message(tr('Extraction terminée.'), 5000)
            if trash_after:
                source = QUrl.fromLocalFile(str(Path(path).absolute())).toString()
                self.start_kio_transfer([source], tr('trash:/'), operation=tr('trash'))

        worker.progress.connect(update)
        worker.completed.connect(complete)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(
            lambda: setattr(self, 'archive_extract_worker', None)
            if self.archive_extract_worker is worker else None)
        self.start_runtime_worker(worker, tr('Extraction RAR'))

    def extract_current_archive(self, destination=None, trash_after=False):
        archive = archive_source_path(self.folder or '')
        if archive:
            self.extract_archive(archive, destination, trash_after)

    def add_archive_extract_menu(self, menu, path):
        """Add Dolphin's three archive extraction choices."""
        extract_menu = menu.addMenu(tr('Extraire'))
        set_themed_action_icon(extract_menu.menuAction(), tr('archive-extract'))
        here = extract_menu.addAction(
            tr('Extraire ici'),
            lambda target=path: self.extract_archive(target, target.parent))
        set_themed_action_icon(here, tr('archive-extract'))
        here_and_trash = extract_menu.addAction(
            tr('Extraire ici et déplacer l’archive dans la corbeille'),
            lambda target=path: self.extract_archive(
                target, target.parent / archive_subfolder_name(target),
                trash_after=True, create_destination=True))
        set_themed_action_icon(here_and_trash, tr('archive-remove'))
        towards = extract_menu.addAction(
            tr('Extraire vers…'),
            lambda target=path: self.extract_archive(target))
        set_themed_action_icon(towards, tr('archive-extract'))
        return extract_menu

    def extract_selected_archive_entries(self):
        paths = [self.row(index).path for index in self.selected_indexes()]
        paths = [str(path) for path in paths if Location.from_value(path).is_uri]
        if not paths:
            return
        destination = QFileDialog.getExistingDirectory(self, tr('Extraire la sélection vers…'), str(Path.home()))
        if destination:
            target = QUrl.fromLocalFile(str(Path(destination).absolute())).toString()
            self.start_kio_transfer(paths, target, move=False, operation=tr('extract'))

    def open_selected(self):
        indexes = self.selected_indexes()
        if len(indexes) == 1:
            self.open_video(indexes[0])
        else:
            rows = [self.row(i) for i in indexes]
            folders = [row.path for row in rows if row.is_dir]
            files = [row.path for row in rows if not row.is_dir]
            for path in files:
                if not Location.from_value(path).is_uri:
                    self.remember_recent(path)
            local_files = [path for path in files if not Location.from_value(path).is_uri]
            remote_files = [path for path in files if Location.from_value(path).is_uri]
            if local_files and services.name == tr('linux'):
                for path in local_files:
                    if not services.open_default_file(path):
                        QMessageBox.warning(self, tr('Ouverture impossible'), tr('L’application par défaut n’a pas pu être lancée.'))
            else:
                for path in local_files:
                    self.open_url(path)
            for path in remote_files:
                self.open_url(path)
            for folder in folders:
                self.open_url(folder)

    def basic_properties(self):
        rows = [self.row(index) for index in self.selected_indexes()]
        if not rows:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Propriétés'))
        dialog.resize(620, 430)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget(dialog)
        general_page = QWidget(tabs)
        form = QFormLayout(general_page)
        tabs.addTab(general_page, tr('Général'))
        layout.addWidget(tabs)
        permission_path = None
        original_mode = None
        requested_mode = [None]
        if len(rows) > 1:
            form.addRow(tr('Éléments sélectionnés'), QLabel(str(len(rows))))
            form.addRow(tr('Dossiers'), QLabel(str(sum((row.is_dir for row in rows)))))
            form.addRow(tr('Fichiers'), QLabel(str(sum((not row.is_dir for row in rows)))))
            form.addRow(tr('Emplacement'), QLabel(str(Path(self.folder or ''))))
        else:
            row = rows[0]
            path = row.path
            if Location.from_value(path).is_uri:
                form.addRow(tr('Nom'), QLabel(str(row.values[0])))
                form.addRow(tr('Type'), QLabel(str(row.values[10])))
                form.addRow(tr('Emplacement'), QLabel(str(path)))
                if not row.is_dir:
                    form.addRow(tr('Taille'), QLabel(str(row.values[1])))
                buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
                buttons.rejected.connect(dialog.reject)
                buttons.accepted.connect(dialog.accept)
                layout.addWidget(buttons)
                dialog.exec()
                dialog.deleteLater()
                return
            else:
                permission_path = path
            try:
                info = path.lstat()
                size = quantity(info.st_size, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024)
                original_mode = stat_module.S_IMODE(info.st_mode)
                requested_mode[0] = original_mode
            except OSError:
                size = tr('Indisponible')
                info = None
            mime = QMimeDatabase().mimeTypeForFile(str(path)).comment() if not row.is_dir else tr('Dossier')
            form.addRow(tr('Nom'), QLabel(path.name or str(path)))
            form.addRow(tr('Type'), QLabel(mime))
            form.addRow(tr('Taille'), QLabel(size if not row.is_dir else row.values[1]))
            form.addRow(tr('Modifié'), QLabel(modification_text(row.modified_ns, mode=self.model.date_format) if row.modified_ns is not None else tr('Indisponible')))
            location = QLineEdit(str(path))
            location.setReadOnly(True)
            form.addRow(tr('Emplacement'), location)

            if permission_path is not None and info is not None:
                add_permissions_tab(tabs, dialog, info, requested_mode, tr, trf)

        standards = (QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
                     if permission_path is not None and original_mode is not None
                     else QDialogButtonBox.StandardButton.Close)
        buttons = QDialogButtonBox(standards)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and permission_path is not None \
                and original_mode is not None and requested_mode[0] != original_mode:
            try:
                apply_permissions(permission_path, requested_mode[0])
                self.show_activity_message(tr('Droits d’accès modifiés.'), 4000)
                self.refresh_current_view()
            except OSError as error:
                QMessageBox.critical(self, tr('Modification impossible'), str(error))
        dialog.deleteLater()

    def open_terminal_here(self):
        if not self.folder:
            return
        if not services.start_terminal(self.folder):
            QMessageBox.warning(self, tr('Terminal indisponible'), tr('Aucun terminal compatible n’a pu être lancé dans ce dossier.'))

    def run_file_in_konsole(self, path):
        if not services.run_in_konsole(path):
            QMessageBox.warning(
                self,
                tr('Konsole indisponible'),
                tr('Le fichier n’a pas pu être lancé dans Konsole.'),
            )

    def run_executable_file(self, path):
        if not services.run_executable(path):
            QMessageBox.warning(
                self,
                tr('Exécution impossible'),
                tr('Le fichier exécutable n’a pas pu être lancé.'),
            )

    def select_all_files(self):
        from PySide6.QtCore import QItemSelection
        selection = QItemSelection()
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            if not self.row(index).is_dir:
                selection.select(index, self.proxy.index(row, self.proxy.columnCount() - 1))
        self.active_view().selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

    def select_all_items(self):
        """Select every visible entry, as Dolphin's “Select All” does."""
        self.active_view().selectAll()

    def trash_context_menu(self):
        """Return the reduced set of actions that is meaningful in Trash."""
        menu = QMenu(self)
        restore = menu.addAction(tr('Restaurer à l’emplacement d’origine'), self.restore_selected_from_trash)
        set_themed_action_icon(restore, tr('edit-undo'))
        open_action = menu.addAction(tr('Ouvrir'), self.open_selected)
        set_themed_action_icon(open_action, tr('document-open'))
        menu.addSeparator()
        delete_action = add_destructive_action(menu, tr('Supprimer définitivement…'), self.delete_selected_from_trash, tr('edit-delete'))
        delete_action.setEnabled(self.delete_button.isEnabled())
        menu.addSeparator()
        properties = menu.addAction(tr('Propriétés'), self.basic_properties)
        properties.setProperty('_mirivue_context_properties', True)
        set_themed_action_icon(properties, tr('document-properties'))
        return menu

    def context_menu(self, position, shift=False):
        self._context_menu_shift = bool(getattr(self, tr('_context_menu_shift'), False) or shift)
        view = self.active_view()
        index = view.indexAt(position)
        if not index.isValid():
            menu = QMenu(self)
            if self.is_archive_view():
                archive = archive_source_path(self.folder or '')
                if archive and service_enabled('extractfileitemaction'):
                    self.add_archive_extract_menu(menu, archive)
                select_all = menu.addAction(tr('Tout sélectionner'), self.select_all_items)
                set_themed_action_icon(select_all, tr('edit-select-all'))
                menu.exec(view.viewport().mapToGlobal(position))
                self._context_menu_shift = False
                return
            if self.is_trash_view():
                empty = menu.addAction(tr('Vider la corbeille…'), self.empty_trash)
                set_themed_action_icon(empty, tr('trash-empty'))
                empty.setEnabled(bool(self.model.rows) and not self.scanning)
                select_all = menu.addAction(tr('Tout sélectionner'), self.select_all_items)
                set_themed_action_icon(select_all, tr('edit-select-all'))
                select_all.setEnabled(bool(self.model.rows))
                menu.exec(view.viewport().mapToGlobal(position))
                self._context_menu_shift = False
                return
            can_create = bool(self.folder) and not self.scanning and not self.is_trash_view() and not self.is_archive_view()
            self.new_folder_action.setEnabled(can_create)
            create_menu = menu.addMenu(tr('Créer un nouveau'))
            set_themed_action_icon(create_menu.menuAction(), tr('list-add'))
            create_menu.addAction(self.new_folder_action)
            text_action = create_menu.addAction(tr('Fichier texte…'), self.create_text_file)
            set_themed_action_icon(text_action, tr('text-x-generic'))
            text_action.setEnabled(can_create and self.current_folder_is_local())
            menu.addSeparator()
            self.add_transfer_menu(menu, False, self.folder)
            if view is self.icons:
                # The icon view has no clickable header. Expose the same sort
                # actions as Affichage > Trier par in its background menu.
                mark_entry(menu.addMenu(self.sort_menu), 'sort')
            if self.folder and not self.is_trash_view() and not self.is_archive_view():
                add_place = menu.addAction(tr('Ajouter le dossier courant aux emplacements'), lambda: self.add_place(self.folder))
                set_themed_action_icon(add_place, tr('bookmark-new'))
                mark_entry(add_place, 'add_to_places')
                menu.addSeparator()
            select_all = menu.addAction(tr('Tout sélectionner'), self.select_all_items)
            set_themed_action_icon(select_all, tr('edit-select-all'))
            hidden = menu.addAction(tr('Afficher les éléments cachés'))
            set_themed_action_icon(hidden, tr('view-hidden'))
            hidden.setCheckable(True)
            hidden.setChecked(self.hidden.isChecked())
            hidden.toggled.connect(self.hidden.setChecked)
            mark_entry(hidden, 'hidden')
            menu.addAction(self.terminal_selection_action)
            mark_entry(self.terminal_selection_action, 'open_terminal_here')
            menu.addSeparator()
            view_modes = QActionGroup(menu)
            view_modes.setExclusive(True)
            for mode, label, icon_name in (
                (1, tr('Vue en icônes'), 'view-list-icons'),
                (2, tr('Vue compacte'), 'view-list-details'),
                (0, tr('Vue détaillée'), 'view-list-tree'),
            ):
                action = menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(self.content_stack.currentIndex() == mode)
                set_themed_action_icon(action, icon_name)
                view_modes.addAction(action)
                mark_entry(action, 'view_mode')
                action.triggered.connect(lambda checked=False, target=mode: self.change_view(target))
            if hasattr(self, 'menu_visibility'):
                self.menu_visibility.add_to_context_menu(menu)
            self.filter_context_menu(menu)
            self.reserve_submenu_tree(menu)
            menu.exec(view.viewport().mapToGlobal(position))
            self._context_menu_shift = False
            return
        if index.siblingAtColumn(0) not in self.selected_indexes():
            view.selectionModel().select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        # Selection updates are normally deferred to the next event-loop turn.
        # The menu is built in this same turn, often immediately after changing
        # panes, so the shared action must reflect the current pane right now.
        self.refresh_delete_availability()
        if self.is_archive_view():
            menu = QMenu(self)
            menu.addAction(tr('Ouvrir'), self.open_selected)
            menu.addAction(tr('Extraire la sélection vers…'), self.extract_selected_archive_entries).setEnabled(bool(self.selected_indexes()))
            if hasattr(self, 'menu_visibility'):
                self.menu_visibility.add_to_context_menu(menu)
            menu.exec(view.viewport().mapToGlobal(position))
            return
        menu = self.trash_context_menu() if self.is_trash_view() else self.file_context_menu(self.row(index))
        if not self.is_trash_view():
            from .native_places_view import create_native_service_menu
            selected = [str(self.row(item).path) for item in self.selected_indexes()]
            kde_menu = create_native_service_menu(menu, self, selected)
            self.merge_kde_context_menu(menu, kde_menu)
        if hasattr(self, 'menu_visibility'):
            self.menu_visibility.add_to_context_menu(menu)
        self.filter_context_menu(menu)
        self.reserve_submenu_tree(menu)
        menu.exec(view.viewport().mapToGlobal(position))
        self._context_menu_shift = False

    def unloaded_media_paths(self):
        """Return direct media children in the active local folder that need full details."""
        if not self.folder or not self.current_folder_is_local():
            return []
        folder = Path(self.folder)
        return [row.path for row in self.model.rows
                if row.path.parent == folder and not row.is_dir
                and row.media_type in (tr('video'), tr('audio'), tr('image'))
                and not row.metadata_loaded]

    def read_unloaded_metadata(self):
        """Read metadata only for uncached or changed media in the active folder."""
        paths = [path for path in self.unloaded_media_paths() if path.exists()]
        if not paths or self.scanning or self._visible_workers:
            return
        self.show_activity_message(trf('Lecture des métadonnées : \x1f0\x1f fichier(s)…', len(paths)))
        self.inspect_visible_entries(paths, finished_callback=lambda: self.show_activity_message(tr('Lecture des métadonnées terminée.'), 6000), show_progress=True)

    def create_folder(self):
        if not self.folder or self.is_trash_view() or self.is_archive_view() or self.scanning:
            return
        name, accepted = QInputDialog.getText(self, tr('Nouveau dossier'), tr('Nom du dossier :'))
        if not accepted:
            return
        if (reason := services.validate_portable_name(name)):
            QMessageBox.warning(self, tr('Nom de dossier invalide'), reason)
            return
        self.create_kio_folder(name)

    def current_folder_is_local(self):
        location = Location.from_value(self.folder or '')
        return bool(self.folder) and not location.is_uri

    def create_text_file(self):
        """Create an empty UTF-8 text file without ever replacing a file."""
        if not self.current_folder_is_local() or self.is_trash_view() or self.is_archive_view() or self.scanning:
            return
        name, accepted = QInputDialog.getText(
            self,
            tr('Nouveau fichier texte'),
            tr('Nom du fichier :'),
            text=tr('Nouveau fichier texte.txt'),
        )
        if not accepted:
            return
        if (reason := services.validate_portable_name(name)):
            QMessageBox.warning(self, tr('Nom de fichier invalide'), reason)
            return
        target = Path(self.folder) / name
        try:
            descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(descriptor)
        except FileExistsError:
            QMessageBox.warning(self, tr('Nom déjà utilisé'), trf('« \x1f0\x1f » existe déjà.', name))
            return
        except OSError as error:
            QMessageBox.warning(self, tr('Création impossible'), trf('Le fichier n’a pas pu être créé.\n\n\x1f0\x1f', str(error)))
            return
        self.show_activity_message(trf('Fichier « \x1f0\x1f » créé.', name), 5000)
        self.scan()

    @staticmethod
    def reserve_submenu_clearance(menu):
        tr('Leave a theme-scaled visual gap before submenu arrows.')
        if menu.property(tr('_mirivue_submenu_clearance')) or not any((action.menu() is not None for action in menu.actions())):
            return
        extra_gap = max(16, round(menu.fontMetrics().height() * 1.25))
        menu.setMinimumWidth(menu.sizeHint().width() + extra_gap)
        menu.setProperty(tr('_mirivue_submenu_clearance'), True)

    @classmethod
    def reserve_submenu_tree(cls, menu):
        cls.reserve_submenu_clearance(menu)
        for action in menu.actions():
            child = action.menu()
            if child is not None:
                cls.reserve_submenu_tree(child)

    def file_context_menu(self, row):
        tr('Keep the first level short; specialised actions live in clear groups.')
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        indexes = self.selected_indexes()
        selected = [self.row(i) for i in indexes]
        paths = [r.path for r in selected]
        count = len(paths)
        has_videos = any((r.is_video for r in selected))
        has_media = any((r.is_video or r.media_type in (tr('audio'), tr('image')) for r in selected))
        incomplete_count = sum((1 for r in selected if FileSortProxy.media_is_incomplete(r)))
        native_open_with = False
        if count > 1 and all(not candidate.is_dir for candidate in selected):
            from .open_with import add_native_open_with
            native_open_with = add_native_open_with(self, menu, paths)
        executable_text = False
        if count == 1 and isinstance(paths[0], Path) and not row.is_dir:
            mime_type = QMimeDatabase().mimeTypeForFile(
                str(paths[0]), QMimeDatabase.MatchMode.MatchContent
            )
            executable_text = is_executable_text_file(paths[0], mime_type)
        if executable_text:
            open_action = menu.addAction(
                tr('Exécuter le fichier'),
                lambda target=paths[0]: self.run_executable_file(target),
            )
            set_themed_action_icon(open_action, tr('system-run'))
        elif not native_open_with:
            open_action = menu.addAction(tr('Ouvrir') if count == 1 else trf('Ouvrir les \x1f0\x1f éléments sélectionnés', count), self.open_selected)
            set_themed_action_icon(open_action, tr('document-open'))
        if count == 1 and isinstance(paths[0], Path) and archive_protocol(paths[0]):
            browse_archive = menu.addAction(tr('Parcourir l’archive'), lambda target=paths[0]: self.open_archive(target))
            set_themed_action_icon(browse_archive, tr('document-open-folder'))
            browse_archive.setEnabled(services.is_plasma)
            if service_enabled('extractfileitemaction'):
                self.add_archive_extract_menu(menu, paths[0]).menuAction().setProperty('_mirivue_archive_extract', True)
        self.add_context_folder_actions(menu, selected)
        if not native_open_with:
            opening = menu.addMenu(tr('Ouvrir avec…'))
            opening.addAction(tr('Choisir une application…')).setEnabled(False)

            def populate():
                if opening.property(tr('loaded')):
                    return
                opening.setProperty(tr('loaded'), True)
                opening.clear()
                from .open_with import populate_menu
                populate_menu(self, opening, paths)
            opening.aboutToShow.connect(populate)
        if executable_text and services.tool_path(tr('konsole')):
            run_in_konsole = menu.addAction(
                tr('Lancer dans Konsole'),
                lambda target=paths[0]: self.run_file_in_konsole(target),
            )
            set_themed_action_icon(run_in_konsole, tr('utilities-terminal'))
            mark_entry(run_in_konsole, 'run_in_konsole')
        if count == 1 and not row.is_dir and str(row.path.parent) != str(self.folder):
            show_in_folder = menu.addAction(tr('Afficher dans le dossier'), lambda: self.open_url(row.path.parent))
            set_themed_action_icon(show_in_folder, tr('document-open-folder'))
        elif count == 1 and row.is_dir:
            add_place = menu.addAction(tr('Ajouter aux emplacements'), lambda target=row.path: self.add_place(target))
            set_themed_action_icon(add_place, tr('bookmark-new'))
            mark_entry(add_place, 'add_to_places')
        menu.addSeparator()
        self.add_transfer_menu(menu, paste_destination=context_paste_destination(selected, self.folder))
        menu.addAction(self.rename_action)
        menu.addSeparator()
        show_permanent = self.settings.value('delete/show-permanent', False, type=bool)
        show_permanent = show_permanent or bool(getattr(self, tr('_context_menu_shift'), False))
        show_permanent = show_permanent or bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        show_permanent = show_permanent or bool(QGuiApplication.queryKeyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self.settings.value('delete/show-permanent', False, type=bool):
            delete_action = menu.addAction(tr('Mettre à la corbeille'), lambda: self.delete_selected(tr('trash')))
            set_themed_action_icon(delete_action, tr('trash-empty'))
            delete_action.setEnabled(self.delete_button.isEnabled())
            permanent_action = add_destructive_action(menu, tr('Supprimer définitivement…'), lambda: self.delete_selected(tr('permanent')), tr('edit-delete'))
            permanent_action.setEnabled(self.delete_button.isEnabled())
        else:
            delete_action = add_dynamic_trash_action(
                menu,
                lambda: self.delete_selected(tr('trash')),
                lambda: self.delete_selected(tr('permanent')),
                tr('Mettre à la corbeille'),
                tr('Supprimer définitivement…'),
                show_permanent,
            )
            delete_action.setEnabled(self.delete_button.isEnabled())
            dynamic_actions = getattr(self, tr('_dynamic_trash_actions'), None)
            if dynamic_actions is None:
                dynamic_actions = []
                self._dynamic_trash_actions = dynamic_actions
            dynamic_actions.append(delete_action)
            menu.aboutToHide.connect(lambda action=delete_action: dynamic_actions.remove(action) if action in dynamic_actions else None)
            delete_action.destroyed.connect(lambda _obj=None, action=delete_action: dynamic_actions.remove(action) if action in dynamic_actions else None)
        menu.addSeparator()
        organize = menu.addMenu(tr('Organiser'))
        organize.setToolTipsVisible(True)
        writable = self.selection_writable(paths)
        reason = self.selection_block_reason(paths)
        organize.menuAction().setProperty('_mirivue_extra_actions', True)
        mark_entry(organize.menuAction(), 'organize')
        set_themed_action_icon(organize.menuAction(), tr('document-edit'))
        if paths:
            organize_move = organize.addAction(tr('Déplacer vers un nouveau dossier…'), self.group_selected)
            mark_entry(organize_move, 'move_to_new_folder')
            set_action_enabled(organize_move, writable, reason)
        create_archive = organize.addAction(tr('Créer une archive…'), self.create_archive)
        mark_entry(create_archive, 'create_archive')
        set_action_enabled(create_archive, self.can_create_archive(paths), reason or tr('La création d’archive nécessite une sélection dans un dossier local.'))
        if count == 1 and row.is_dir and isinstance(row.path, Path):
            rename_contents = organize.addAction(tr('Renommer le contenu du dossier…'),
                                                 lambda checked=False, folder=row.path: self.rename_folder_contents(folder))
            set_action_enabled(rename_contents, writable, reason)
        else:
            organize.addAction(self.external_renamer_label(), lambda: self.launch_renamer()).setEnabled(
                writable)
        if has_videos:
            set_action_enabled(organize.addAction(tr('Corriger les extensions de la sélection…'), self.rename_extensions), writable, reason)
        if has_media:
            set_action_enabled(organize.addAction(tr('Renommer à partir des métadonnées…'), self.rename_from_metadata), writable, reason)
            set_action_enabled(organize.addAction(tr('Organiser en sous-dossiers…'), self.organize_media), writable, reason)
        if selected and all((candidate.is_dir for candidate in selected)):
            organize.addAction(tr('Calculer la durée totale'), self.start_folder_duration)
        related = self.associated_entries(paths)
        if related:
            companions = menu.addMenu(trf('Fichiers associés (\x1f0\x1f)', len(related)))
            mark_entry(companions.menuAction(), 'companions')
            companions.addAction(tr('Ajouter les fichiers associés à la sélection'), lambda: self.select_associated_entries(paths))
            companions.addSeparator()
            for path in related[:8]:
                action = companions.addAction(path.name)
                action.setEnabled(False)
                action.setToolTip(str(path))
            if len(related) > 8:
                action = companions.addAction(trf('… et \x1f0\x1f autre(s) fichier(s)', len(related) - 8))
                action.setEnabled(False)
        if has_media:
            media = menu.addMenu(tr('Outils multimédias'))
            media.setToolTipsVisible(True)
            mark_entry(media.menuAction(), 'media')
            self.add_media_context(media, selected)
            metadata_action = media.addAction(tr('Modifier les métadonnées…'), self.edit_metadata)
            set_themed_action_icon(metadata_action, tr('document-properties'))
            set_action_enabled(metadata_action, writable, reason)
            self.add_personal_label_menu(media, selected)
            if count == 2:
                media.addAction(tr('Comparer les deux médias'), self.compare_selected)
            if row.is_video and getattr(row, tr('mkv_copy_recommended'), False):
                media.addAction(tr('Créer une copie MKV compatible, sans réencodage…'), lambda: self.offer_mkv_copy(row))
        if has_videos:
            media.addAction(tr('Régénérer l’aperçu'), self.regenerate_previews).setEnabled(not self.scanning)
        if row.duplicate_group:
            duplicate_menu = media if has_media else organize
            duplicate_menu.addAction(tr('Doublons : choisir le fichier à conserver…'), self.choose_duplicate_keeper).setEnabled(not self.scanning)
        if row.error or row.bitrate_error or row.validation_error:
            menu.addAction(tr('Voir l’erreur de ce fichier'), lambda: self.show_file_error(row))
        menu.addSeparator()
        properties = menu.addAction(tr('Propriétés'), self.basic_properties)
        properties.setProperty('_mirivue_context_properties', True)
        set_themed_action_icon(properties, tr('document-properties'))
        return self.filter_context_menu(menu)

    def update_renamed_rows(self, renamed, reset=True):
        self.clear_duplicates()
        refreshed = []
        if reset:
            self.model.beginResetModel()
        for index, row in enumerate(self.model.rows):
            if row.path in renamed:
                self.result_cache.pop(row.path, None)
                row.path = renamed[row.path]
                if not reset:
                    self.model.reindex_row(index)
                row.is_hidden = local_is_hidden(row.path)
                refreshed.append(row.path)
                row.values[0] = row.path.name
                row.sort_values[0] = row.path.name.casefold()
                if row.container_info:
                    row.suggested_extension, row.extension_note = suggest_extension(row.container_info, row.path.suffix)
                suggested = row.suggested_extension
                row.values[11] = suggested + (tr(' (correcte)') if row.path.suffix.lower() == suggested else tr(' (à corriger)')) if suggested else tr('Indéterminée')
                row.sort_values[11] = row.values[11].casefold()
                try:
                    row.file_signature = fingerprint(row.path)
                except OSError:
                    row.file_signature = None
                self.save_result(row)
                if not reset:
                    QTimer.singleShot(0, self.pane_callback(lambda changed=row: self.notify_inline_rename(changed)))
        if reset:
            self.model.endResetModel()
        self.update_summary()
        if refreshed:
            QTimer.singleShot(0, self.pane_callback(lambda paths=tuple(refreshed): self.start_thumbnails(paths)))
        QTimer.singleShot(0, self.pane_callback(lambda: self.refresh_other_panes([*renamed, *renamed.values()])))

    def notify_inline_rename(self, row):
        for index, candidate in enumerate(self.model.rows):
            if candidate is row:
                self.model.dataChanged.emit(self.model.index(index, 0), self.model.index(index, len(HEADERS) - 1))
                self.update_summary()
                break

    def rename_f2(self):
        if self.is_archive_view():
            return
        if self.selection_locked():
            QMessageBox.information(self, tr('Opérations en cours'), tr('Un fichier sélectionné, ou un fichier de ce dossier, est utilisé par une opération. Attendez sa fin ou annulez-la.'))
            return False
        if self.scanning:
            return
        selected = self.selected_indexes()
        if not selected:
            return
        if len(selected) > 1:
            self.rename_names()
            return
        view = self.active_view()
        current = view.currentIndex().siblingAtColumn(0)
        index = current if current in selected else selected[0]
        self.table.setColumnHidden(0, False)
        view.setCurrentIndex(index)
        view.scrollTo(index)
        view.edit(index)

    def rename_inline(self, path, name):
        if self.paths_locked([path]):
            QMessageBox.information(self, tr('Opérations en cours'), tr('Un fichier sélectionné, ou un fichier de ce dossier, est utilisé par une opération. Attendez sa fin ou annulez-la.'))
            return False
        if self.scanning:
            return False
        row = next((row for row in self.model.rows if row.path == path), None)
        if row is None:
            return False
        plans = prepare_names([row], [name])
        if not plans:
            return True
        if any((p.issue for p in plans)):
            QMessageBox.warning(self, tr('Renommage impossible'), tr('\n').join((p.issue for p in plans if p.issue)))
            return False
        renamed, errors = apply_renames(plans)
        if errors:
            QMessageBox.warning(self, tr('Renommage impossible'), tr('\n').join(errors))
            return False
        self.record_local_renames(renamed)
        self.update_renamed_rows(renamed, reset=False)
        if row.is_dir:
            QTimer.singleShot(0, self.pane_callback(self.scan))
        return True

    def rename_names(self):
        rows = [self.row(index) for index in self.selected_indexes()]
        self.rename_rows_with_chosen_tool(rows)

    def rename_folder_contents(self, folder):
        """Rename only immediate children; F2 renames the folder itself."""
        if self.scanning or self.paths_locked([folder]):
            return
        try:
            rows = folder_rename_rows(folder)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr('Renommage impossible'), str(error))
            return
        if not rows:
            QMessageBox.information(self, tr('Dossier vide'), tr('Ce dossier ne contient aucun élément à renommer.'))
            return
        self.rename_rows_with_chosen_tool(rows, folder=folder)

    def rename_rows_with_chosen_tool(self, rows, folder=None):
        if str(self.settings.value('renamer/tool', 'integrated')) == 'external':
            self.launch_renamer(paths=[row.path for row in rows])
        else:
            self._rename_rows(rows, folder=folder)

    def rename_advanced(self):
        rows = [self.row(index) for index in self.selected_indexes()]
        self._rename_rows(rows)

    def external_renamer_label(self):
        program = str(self.settings.value('renamer/program', '')).strip()
        return trf('Renommer avec \x1f0\x1f…', Path(program).name) if program else tr('Renommer avec un logiciel externe…')

    def _rename_rows(self, rows, folder=None, initial_method='manual'):
        from .rename_ui import show_advanced_rename
        return show_advanced_rename(self, rows, folder, initial_method)

    def choose_renamer(self, launch=False, paths=None):
        if self.scanning:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Renommer avec…'))
        dialog.resize(620, 280)
        layout = QVBoxLayout(dialog)
        preset = QComboBox()
        preset.addItems([tr('Personnalisé'), *PRESETS])
        layout.addWidget(QLabel(tr('Logiciel de renommage :')))
        layout.addWidget(preset)
        program = QLineEdit(self.settings.value('renamer/program', ''))
        arguments = QLineEdit(self.settings.value('renamer/arguments', tr('-B')))
        path_row = QHBoxLayout()
        path_row.addWidget(program)
        browse = QPushButton(tr('Parcourir…'))
        path_row.addWidget(browse)
        layout.addLayout(path_row)
        options_row = QHBoxLayout()
        options_row.addWidget(QLabel(tr('Options du logiciel :')))
        options_row.addStretch(1)
        options_row.addWidget(context_help_button(dialog, tr('La sélection est ajoutée automatiquement. Le logiciel doit être installé et le choix sera mémorisé.')))
        layout.addLayout(options_row)
        layout.addWidget(arguments)
        arguments.setToolTip(tr('La sélection est ajoutée automatiquement à la commande.'))

        def use_preset(name):
            if name in PRESETS:
                program.setText(PRESETS[name][0])
                arguments.setText(PRESETS[name][1])
        preset.currentTextChanged.connect(use_preset)
        for name, values in PRESETS.items():
            if (program.text(), arguments.text()) == values:
                preset.setCurrentText(name)
                break

        def pick():
            path, _ = QFileDialog.getOpenFileName(dialog, tr('Choisir le programme'), str(Path.home()))
            if path:
                preset.setCurrentText(tr('Personnalisé'))
                program.setText(path)
        browse.clicked.connect(pick)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
        buttons.addButton(tr('Enregistrer et ouvrir') if launch else tr('Enregistrer'), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        import shlex
        try:
            if not program.text().strip():
                raise ValueError(tr('Choisissez un programme.'))
            shlex.split(arguments.text())
        except ValueError as error:
            QMessageBox.warning(self, tr('Options invalides'), str(error))
            return
        self.settings.setValue('renamer/program', program.text().strip())
        self.settings.setValue('renamer/arguments', arguments.text())
        if launch:
            self.launch_renamer(paths=paths)

    def launch_renamer(self, program=None, arguments=None, paths=None):
        if self.selection_locked() or (paths is not None and self.paths_locked(paths)):
            QMessageBox.information(self, tr('Opérations en cours'), tr('Un fichier sélectionné, ou un fichier de ce dossier, est utilisé par une opération. Attendez sa fin ou annulez-la.'))
            return False
        if self.scanning:
            return
        if paths is None:
            selected = list(dict.fromkeys(self.row(index).path for index in self.selected_indexes()))
            if len(selected) == 1 and selected[0].is_dir():
                try:
                    selected = [row.path for row in folder_rename_rows(selected[0])]
                except (OSError, ValueError) as error:
                    QMessageBox.warning(self, tr('Renommage impossible'), str(error))
                    return
            paths = selected
        if not paths:
            return
        if program is None:
            program = self.settings.value('renamer/program', '')
            arguments = self.settings.value('renamer/arguments', tr('-B'))
            if not str(program or '').strip():
                self.choose_renamer(launch=True, paths=paths)
                return
        try:
            if not str(program or '').strip():
                raise ValueError(tr('Choisissez un outil dans Configuration avant de l’ouvrir.'))
            executable, args = external_command(program, arguments or '', paths)
            result = QProcess.startDetached(executable, args)
            ok = result[0] if isinstance(result, tuple) else result
            if not ok:
                raise ValueError(tr('Le logiciel de renommage n’a pas pu démarrer.'))
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, tr('Ouverture impossible'), str(error))
            return
        old = self.external_watcher.directories()
        if old:
            self.external_watcher.removePaths(old)
        self.external_watcher.addPaths(list({str(path.parent) for path in paths}))
        self.external_timer.start()
        self.show_activity_message(tr('Logiciel de renommage ouvert. Les noms sont suivis dans leurs dossiers ; utilisez Actualiser si les fichiers ont été déplacés.'), 8000)

    def sync_external_names(self):
        if self.scanning:
            self.external_timer.start()
            return
        if self.move_worker is not None:
            return
        renamed = find_external_renames(self.model.rows)
        if renamed:
            self.update_renamed_rows(renamed)
            self.show_activity_message(trf('\x1f0\x1f nom(s) mis à jour après renommage externe.', len(renamed)), 6000)

    def visible_folder_snapshot(self, folder):
        tr('Return a cheap direct-child signature without reading media metadata.')
        path = Path(folder)
        result = {}
        try:
            for child in path.iterdir():
                try:
                    stat = child.stat()
                    result[child] = (child.is_dir(), stat.st_mtime_ns, stat.st_size)
                except OSError:
                    continue
        except OSError:
            return None
        return result

    def is_network_location(self, folder):
        tr('Never poll a remote mount from the GUI thread after it disappears.')
        try:
            fs = bytes(QStorageInfo(str(folder)).fileSystemType()).decode(tr('ascii'), tr('ignore')).lower()
        except (OSError, TypeError, ValueError):
            return False
        return any((token in fs for token in (tr('nfs'), tr('cifs'), tr('smb'), tr('sshfs'), tr('fuse'), tr('davfs'), tr('afp'), tr('9p'))))

    def watch_visible_directories(self):
        if self.closing or not hasattr(self, tr('visible_watcher')):
            return
        folders = set()
        for pane in getattr(self, tr('panes'), []):
            if not pane.folder or not Path(pane.folder).is_dir():
                continue
            if self.is_network_location(pane.folder):
                continue
            folders.add(str(Path(pane.folder).resolve()))
        old = self.visible_watcher.directories()
        remove = [path for path in old if path not in folders]
        if remove:
            self.visible_watcher.removePaths(remove)
        add = [path for path in folders if path not in old]
        if add:
            self.visible_watcher.addPaths(add)
        # Reconfiguring watches for one pane must not discard pending changes
        # in the other. In particular, a native KIO drop may just have removed
        # a source while its directoryChanged notification is still queued.
        previous = self._visible_snapshots
        self._visible_snapshots = {Path(path): previous[Path(path)] if Path(path) in previous
                                   else self.visible_folder_snapshot(path) for path in folders}

    def sync_visible_directories(self):
        if self.closing:
            return
        if any((p.scanning for p in getattr(self, tr('panes'), []))) or self.move_worker is not None or getattr(self, tr('_metadata_worker'), None):
            self.visible_timer.start()
            return
        changed = set()
        removed = set()
        for folder, old in list(self._visible_snapshots.items()):
            current = self.visible_folder_snapshot(folder)
            if current is None:
                continue
            self._visible_snapshots[folder] = current
            marker = folder / '.hidden'
            if old is not None and old.get(marker) != current.get(marker):
                # Re-evaluate membership incrementally, preserving selection,
                # scroll position and header widths rather than reloading.
                changed.update(path for path in current if path != marker)
            # A newly displayed file may be moved again before the directory
            # watcher has recorded its arrival. Also reconcile known rows,
            # otherwise neither snapshot contains that now-missing source.
            current_names = {path.name for path in current}
            for pane in self.panes:
                if not pane.folder or Path(pane.folder).resolve() != folder:
                    continue
                removed.update(row.path for row in pane.model.rows
                               if row.path.parent == Path(pane.folder)
                               and row.path.name not in current_names
                               and not row.path.exists() and not row.path.is_symlink())
            if old is None:
                continue
            changed.update((path for path, value in current.items() if old.get(path) != value))
            removed.update((path for path in old if path not in current))
        if removed:
            for pane in self.panes:
                if not pane.folder:
                    continue
                direct = {path for path in removed if path.parent == Path(pane.folder)}
                if direct:
                    pane.model.remove_paths(direct)
            self.update_summary()
        if not changed:
            return
        self.inspect_visible_entries(changed, read_metadata=False)

    def inspect_visible_entries(self, paths, finished_callback=None, show_progress=False, read_metadata=True):
        tr('Read only direct children that changed; metadata probes are explicit except after deliberate file operations.')
        changed = {Path(path) for path in paths if Path(path).exists()}
        if not changed:
            return
        worker = ChangedEntriesWorker(changed, read_metadata=read_metadata)
        self._visible_workers.append(worker)
        worker.found.connect(self.apply_visible_entry)
        if show_progress:
            self.bar.setRange(0, max(1, len(changed)))
            self.bar.setValue(0)
            self.bar.setFormat(tr('Actualisation des métadonnées : %v/%m'))
            self.bar.show()
            worker.progress.connect(self.progress)

        def finished():
            if worker in self._visible_workers:
                self._visible_workers.remove(worker)
            worker.deleteLater()
            if show_progress:
                self.bar.hide()
            if finished_callback is not None and not self.closing:
                finished_callback()
            # The watcher can deliver its result after a transfer has already
            # inserted a row and painted its preview. Coalesce all changed
            # entries before starting another KDE preview job.
            if not self._visible_workers and not self.closing:
                QTimer.singleShot(0, self.refresh_changed_previews)
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Actualisation des métadonnées'))

    def refresh_visible_entries(self, paths):
        tr('Synchronise supplied direct children after a Mirivue operation.')
        direct = set()
        for raw in paths:
            path = Path(raw)
            for pane in getattr(self, tr('panes'), []):
                if pane.folder and path.parent == Path(pane.folder):
                    direct.add(path)
                    snapshot = self._visible_snapshots.get(Path(pane.folder).resolve())
                    if snapshot is not None:
                        try:
                            snapshot[path] = (path.is_dir(), path.stat().st_mtime_ns, path.stat().st_size)
                        except OSError:
                            snapshot.pop(path, None)
        self.inspect_visible_entries(direct)

    def apply_visible_entry(self, row):
        tr('Replace only the rows whose filesystem signature changed.')
        row.is_hidden = local_is_hidden(row.path)
        matches = [pane for pane in self.panes if pane.folder and row.path.parent == Path(pane.folder)]
        if not matches:
            return
        original = self.bound_pane
        for pane in matches:
            if row.is_hidden and not pane.hidden_state:
                pane.model.remove_paths({row.path})
                self.run_in_pane(pane, self.update_summary)
                continue

            def replace(target=row):
                previous = next((item for item in self.model.rows if item.path == target.path), None)
                icon = self.model.thumbnails.get(target.path)
                selected_in = [view for view in (getattr(pane, 'table', None), getattr(pane, 'icons', None), getattr(pane, 'compact', None)) if view is not None
                               if any(self.model.rows[self.proxy.mapToSource(index).row()].path == target.path
                                      for index in view.selectionModel().selectedRows())]
                # A directory notification often reports the same file that
                # our transfer has just inserted. Retain its preview if the
                # on-disk signature has not changed.
                keep_icon = icon is not None and previous is not None and previous.file_signature == target.file_signature
                if (previous is not None and previous.file_signature == target.file_signature
                        and previous.sort_values[2] > 0 and target.sort_values[2] < 0):
                    target.sort_values[2], target.values[2] = previous.sort_values[2], previous.values[2]
                self.model.remove_paths({target.path})
                try:
                    copy = library.decode_row(library.encode_row(target))
                except (KeyError, TypeError, ValueError):
                    copy = target
                if keep_icon:
                    self.model.thumbnails[target.path] = icon
                self.add(copy)
                if selected_in:
                    position = next((i for i, item in enumerate(self.model.rows) if item.path == target.path), None)
                    index = map_file_index(self.proxy, self.model.index(position, 0)) if position is not None else QModelIndex()
                    if index.isValid():
                        for view in selected_in:
                            view.selectionModel().select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                if self.model.show_thumbnails and not target.is_dir and not keep_icon:
                    pane.preview_dirty = True
            self.run_in_pane(pane, replace)
            if row.media_type in (tr('video'), tr('audio'), tr('image')):
                self.start_duration_lookup(pane, [row.path])
        self.bind_pane(original)
        self.sync_pane_controls()

    def refresh_changed_previews(self):
        """Regenerate previews lost while a directory notification replaced rows."""
        if self.closing or self._visible_workers:
            return
        waiting = False
        for pane in self.panes:
            if not getattr(pane, 'preview_dirty', False):
                continue
            if pane.scanning:
                waiting = True
                continue
            pane.preview_dirty = False
            if pane.model.show_thumbnails:
                self.run_in_pane(pane, self.start_thumbnails)
        if waiting:
            QTimer.singleShot(150, self.refresh_changed_previews)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if hasattr(self, tr('panes')):
                QTimer.singleShot(0, self.update_pane_emphasis)
        elif event.type() == QEvent.Type.ActivationChange:
            # Plasma darkens both Dolphin's titlebar and its application
            # chrome when the window becomes inactive.
            if hasattr(self, tr('refresh_symbolic_icons')):
                QTimer.singleShot(0, self.refresh_symbolic_icons)
            if self.isActiveWindow() and hasattr(self, tr('external_timer')):
                if self.external_watcher.directories():
                    self.external_timer.start()

    def show_analysis_explainer(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr('Comprendre les informations techniques'))
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr('<h3>Ce que signifient les informations</h3><p><b>Données du fichier</b> : codec, durée, résolution et métadonnées lus dans le média. Mirivue affiche rapidement certaines données à l’ouverture du dossier. Pour lire les autres informations des médias du dossier actif, choisissez « Lire les informations détaillées des médias du dossier » dans Outils → Métadonnées. Une case vide après cette lecture signifie que le fichier ou son conteneur ne fournit pas cette information.</p><p><b>Débit</b> : valeur déclarée dans le média, lue rapidement sans décodage complet. Si aucune valeur fiable n’est disponible, Mirivue affiche une case vide.</p><p><b>Doublon exact</b> : fichiers dont le contenu complet est identique. Mirivue ne supprime jamais de fichier sans votre choix explicite.</p>'))
        box.setInformativeText(tr('Les traitements restent locaux. Leur progression et leur historique sont accessibles depuis Opérations.'))
        box.exec()

    def show_about(self):
        QMessageBox.about(self, tr('À propos de Mirivue'), trf('<h2>Mirivue</h2><p>Version : <b>\x1f0\x1f</b><br>Date de publication : \x1f1\x1f<br>Nom : <b>\x1f2\x1f</b></p><p>Your Media, Clearly Organised</p><p>Gestion de fichiers et lecture locale des informations de vos vidéos, sons et images sous Linux.</p><p>Python · Qt/PySide6 · MediaInfo · FFmpeg<br>Distribution combinée : GNU GPL v3 ou ultérieure.<br>Parties originales sous MIT ; composants tiers sous leurs licences propres.<br>Voir LICENSE et LICENCES-TIERS.md dans les sources.</p>', __version__, RELEASE_DATE, AUTHOR))

    def show_diagnostics(self):
        report = diagnostic_report(__version__)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr('Diagnostic de Mirivue'))
        box.setText(tr('État des composants et informations utiles au dépannage.'))
        box.setInformativeText(tr('Le rapport reste sur cet ordinateur tant que vous ne le copiez pas vous-même.'))
        box.setDetailedText(report)
        copy_button = box.addButton(tr('Copier le diagnostic'), QMessageBox.ButtonRole.ActionRole)
        folder_button = box.addButton(tr('Ouvrir le dossier des journaux'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is copy_button:
            QApplication.clipboard().setText(report)
            self.show_activity_message(tr('Diagnostic copié.'), 4000)
        elif box.clickedButton() is folder_button:
            state_directory().mkdir(parents=True, exist_ok=True)
            services.open_default_file(state_directory())

    def show_previous_unclean_shutdown(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr('Arrêt précédent incomplet'))
        box.setText(tr('Mirivue ne semble pas s’être arrêté normalement lors du lancement précédent.'))
        box.setInformativeText(tr('Vos fichiers ne sont pas modifiés par ce contrôle. Le journal peut aider à comprendre l’incident.'))
        diagnostic_button = box.addButton(tr('Afficher le diagnostic'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is diagnostic_button:
            self.show_diagnostics()

    def confirm_renames(self, plans):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Corriger les extensions'))
        dialog.resize(1000, 440)
        layout = QVBoxLayout(dialog)
        count = sum((not p.issue for p in plans))
        label = QLabel(trf('\x1f0\x1f fichier(s) à renommer. Le contenu reste inchangé ; aucun fichier existant ne sera écrasé.', count))
        label.setWordWrap(True)
        layout.addWidget(label)
        table = QTableWidget(len(plans), 3)
        table.setHorizontalHeaderLabels([tr('Nom actuel (survol : chemin complet)'), tr('Nouveau nom'), tr('Vérification')])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for index, plan in enumerate(plans):
            for column, text in enumerate([plan.source.name, plan.destination.name, plan.issue or tr('Prêt')]):
                item = QTableWidgetItem(text)
                item.setToolTip(str(plan.source) if column == 0 else text)
                table.setItem(index, column, item)
        table.setColumnWidth(0, 420)
        table.setColumnWidth(1, 260)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        layout.addWidget(QLabel(tr('Les lignes en conflit seront ignorées. Les autres fichiers du dossier (sous-titres, etc.) ne seront pas renommés.')))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
        rename = buttons.addButton(trf('Renommer \x1f0\x1f fichier(s)', count), QDialogButtonBox.ButtonRole.AcceptRole)
        rename.setEnabled(count > 0)
        rename.setAutoDefault(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def rename_extensions(self):
        if self.selection_locked():
            QMessageBox.information(self, tr('Opérations en cours'), tr('Un fichier sélectionné, ou un fichier de ce dossier, est utilisé par une opération. Attendez sa fin ou annulez-la.'))
            return False
        if self.scanning:
            return
        selected = set(self.selected_paths())
        plans = prepare_renames([row for row in self.model.rows if row.path in selected])
        if not plans:
            QMessageBox.information(self, tr('Extensions'), tr('Aucune extension à corriger dans la sélection : elle est compatible ou le conteneur est indéterminé.'))
            return
        if not self.confirm_renames(plans):
            return
        renamed, errors = apply_renames(plans)
        self.record_local_renames(renamed)
        self.update_renamed_rows(renamed)
        self.show_activity_message(trf('\x1f0\x1f fichier(s) renommé(s).', len(renamed)), 6000)
        if errors:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(tr('Rapport de renommage'))
            box.setText(trf('\x1f0\x1f fichier(s) renommé(s), \x1f1\x1f ignoré(s) ou en échec. Aucun fichier existant n’a été écrasé.', len(renamed), len(errors)))
            box.setDetailedText(tr('\n').join(errors))
            box.exec()

    def show_errors(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr('Rapport d’erreurs'))
        box.setText(tr('Les fichiers concernés restent visibles dans le tableau.'))
        box.setDetailedText(tr('\n').join(self.notices + [trf('\x1f0\x1f: \x1f1\x1f\n\x1f2\x1f', r.path, explain_error(r.error or r.bitrate_error or r.validation_error), r.error or r.bitrate_error or r.validation_error) for r in self.model.rows if r.error or r.bitrate_error or r.validation_error]))
        box.exec()

    def restore_window(self, activation_token=''):
        if self.quit_requested:
            return
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        from .window_activation import activate_window
        activate_window(self, activation_token)

    def open_external_location(self, folder, files=(), properties=False):
        """Reuse a requested folder, creating a tab only when necessary."""
        self.open_external_locations([LaunchRequest(str(folder), tuple(str(p) for p in files))],
                                     properties=properties)

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore_window()

    def check_tray_available(self):
        if not self.isVisible() and (not self.quit_requested) and self.tray.isVisible() and (not QSystemTrayIcon.isSystemTrayAvailable()):
            self.restore_window()

    def request_quit(self):
        self.quit_requested = True
        self.close()

    def closeEvent(self, event):
        if getattr(self, '_sidebar_width_save_timer', None) is not None and self._sidebar_width_save_timer.isActive():
            self._sidebar_width_save_timer.stop()
            self.save_sidebar_width()
        if getattr(self, '_pane_splitter_save_timer', None) is not None and self._pane_splitter_save_timer.isActive():
            self._pane_splitter_save_timer.stop()
            self.save_pane_splitter_sizes()
        # File operations have their own cancellation and close decision.
        # Do not cancel them while stopping folder/metadata lookup threads.
        lookups = self.runtime_tasks.request_stop_all(exclude=self.kio_transfer_workers())
        if lookups:
            QTimer.singleShot(50, self.close)
            event.ignore()
            return
        for name in (tr('trash_process'),):
            process = getattr(self, name, None)
            if process and process.state() != QProcess.ProcessState.NotRunning:
                self.show_activity_message(tr('Attendez la fin de l’opération système avant de quitter.'))
                event.ignore()
                return
        if self.move_worker is not None and self.move_worker.isRunning():
            self.move_worker.requestInterruption()
            event.ignore()
            return
        if not self.quit_requested and (not self.closing) and '--new-window' not in sys.argv[1:] and self.settings.value('window/close-to-tray', False, type=bool) and (self.tray is not None) and QSystemTrayIcon.isSystemTrayAvailable():
            self.save_pane_column_states()
            self.tray.show()
            self.hide()
            event.ignore()
            return
        if not self.closing and not getattr(self, '_confirmed_multiple_tabs_close', False):
            if not self.confirm_tab_window_close():
                self.quit_requested = False
                event.ignore()
                return
            self._confirmed_multiple_tabs_close = True
        if not self.allow_media_close():
            self._confirmed_multiple_tabs_close = False
            self.quit_requested = False
            event.ignore()
            return
        if not self.allow_transfer_close():
            self._confirmed_multiple_tabs_close = False
            self.quit_requested = False
            event.ignore()
            return
        if not self.closing:
            self.flush_checkpoint()
        self.closing = True
        self.cancel_all_jobs()
        if self.active_job is not None:
            event.ignore()
            return
        self.stop_all_pane_workers()
        self.stop_thumbnails()
        if self.scanning:
            self.closing = True
            self.cancel()
            event.ignore()
        else:
            store = getattr(self.settings, '_mirivue_store', None)
            if store and store.busy():
                store.idle = self.close
                store.flush()
                self.show_activity_message(tr('Sauvegarde des résultats…'))
                event.ignore()
                return
            if store and store.error:
                QMessageBox.warning(self, tr('Sauvegarde incomplète'), tr('Certains résultats d’analyse n’ont pas pu être mémorisés.\n') + store.error)
            self.save_tab_session()
            self.settings.setValue('window/geometry', geometry_to_save(self))
            self.save_pane_column_states()
            for dialog_name in ('_configuration_dialog', '_shortcut_configuration_dialog'):
                dialog = getattr(self, dialog_name, None)
                if dialog is not None:
                    dialog.reject()
            if self.tray is not None:
                self.tray.hide()
            self.menu_visibility.detach()
            for timer in self.findChildren(QTimer):
                timer.stop()
            for watcher in self.findChildren(QFileSystemWatcher):
                paths = watcher.files() + watcher.directories()
                if paths:
                    watcher.removePaths(paths)
            event.accept()
            if self.quit_requested:
                QApplication.instance().quit()

def prepare_audio_stream_identity():
    """Name Qt/GStreamer streams before the multimedia backend starts."""
    name = 'Mirivue KDE'
    desktop_id = 'org.pdenams.Mirivue.Qt'
    os.environ['PULSE_PROP_application.name'] = name
    os.environ['PULSE_PROP_application.icon_name'] = desktop_id
    os.environ['PULSE_PROP_application.id'] = desktop_id
    os.environ['PULSE_PROP_media.role'] = 'video'
    os.environ['PIPEWIRE_PROPS'] = (
        '{ application.name = "Mirivue KDE" '
        'application.id = "org.pdenams.Mirivue.Qt" '
        'media.name = "Aperçu Mirivue" media.role = "Video" }')
    # Qt uses GStreamer on the supported Plasma installation.  PulseAudio's
    # compatibility sink uses GLib's name; native PipeWire reads PIPEWIRE_PROPS.
    try:
        library = ctypes.util.find_library('glib-2.0') or 'libglib-2.0.so.0'
        glib = ctypes.CDLL(library)
        encoded = name.encode('utf-8')
        glib.g_set_prgname.argtypes = [ctypes.c_char_p]
        glib.g_set_application_name.argtypes = [ctypes.c_char_p]
        glib.g_set_prgname(encoded)
        glib.g_set_application_name(encoded)
    except (AttributeError, OSError):
        pass


def main():
    if '--version' in sys.argv[1:]:
        print(__version__)
        return
    activation_token = os.environ.get('XDG_ACTIVATION_TOKEN', '')
    prepare_audio_stream_identity()
    services.prepare_runtime()
    services.initialize_icon_theme()
    QApplication.setApplicationName('org.pdenams.Mirivue.Qt')
    app = QApplication(['Mirivue', *sys.argv[1:]])
    prepare_system_style(app)
    app.setApplicationDisplayName(tr('Mirivue'))
    app._mirivue_translator = load_system_translation(app)
    # This must match the installed .desktop filename exactly so Plasma groups
    # the window with Mirivue KDE instead of displaying the Python executable.
    app.setDesktopFileName('org.pdenams.Mirivue.Qt')
    app.setWindowIcon(QIcon(str(Path(__file__).parent / tr('icons/mirivue.svg'))))
    app.setApplicationVersion(__version__)
    app.aboutToQuit.connect(services.shutdown_kio_service)
    server = start_single_instance_server(app)
    if server is False:
        return
    previous_unclean = begin_session()
    app.aboutToQuit.connect(end_session)
    requests = getattr(app, '_mirivue_remaining_launches', parse_launch_requests(sys.argv[1:]))
    request = requests[0] if requests else LaunchRequest()
    window = Window()
    restore_window_geometry(window)
    window.pending_external_files = [Path(path) for path in request.files]
    window.pending_external_properties = '--show-properties' in sys.argv[1:]
    if server is not None:
        server.newConnection.connect(lambda: deliver_launches(server, window))
        app._mirivue_instance_server = server
    window.prepare_startup_browsing(request.folder or (str(Path.home()) if '--session-tab' in sys.argv[1:] else None))
    if requests:
        pane = window.panes[0]
        pane.external_request_pending = True
        pane.pending_external_files = [Path(path) for path in request.files]
        pane.pending_external_properties = '--show-properties' in sys.argv[1:]
        window.pending_external_files = []
        window.pending_external_properties = False
    from .window_instances import register_window
    register_window(app, window)
    window.show()
    from .window_activation import activate_window
    activate_window(window, activation_token)
    # show() assigns the real splitter geometry before the first paint event.
    # Align once now instead of visibly correcting it over several timers.
    window.sync_path_toolbar_alignment()
    from .filemanager1 import register_file_manager_service
    app._mirivue_filemanager1_registered = register_file_manager_service(app, window)
    QTimer.singleShot(0, window.start_browsing)
    if '--session-tab' in sys.argv[1:]:
        try:
            saved = json.loads(sys.argv[sys.argv.index('--session-tab') + 1])
            window.restore_detached_tab(saved)
        except (ValueError, IndexError, TypeError):
            window.show_activity_message('Impossible de restaurer l’onglet détaché.', 5000)
    elif '--split' in sys.argv[1:]:
        window.set_split_view(True, navigate_new=False)
        if len(requests) > 1:
            pane = window.panes[1]
            pane.external_request_pending = True
            pane.pending_external_files = [Path(path) for path in requests[1].files]
            pane.pending_external_properties = '--show-properties' in sys.argv[1:]
            window.run_in_pane(pane, window.navigate, requests[1].folder)
        if len(requests) > 2:
            QTimer.singleShot(0, lambda: window.open_external_locations(requests[2:], activate_first=False, split=True))
    elif len(requests) > 1:
        QTimer.singleShot(0, lambda: window.open_external_locations(requests[1:], activate_first=False))
    if previous_unclean:
        QTimer.singleShot(350, window.show_previous_unclean_shutdown)
    else:
        QTimer.singleShot(350, window.show_first_use_help)
    sys.exit(app.exec())
