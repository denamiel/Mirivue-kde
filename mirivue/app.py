from .i18n import tr, trf
import time
import os
import json
from pathlib import Path
import shutil
import sys
import ctypes
import ctypes.util
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
from .diagnostic_dialogs import DiagnosticDialogsMixin
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
from .metadata import HEADERS, EXTENSIONS, inspect, failed, quantity, basic_entry, is_dangling_symlink, remote_entry, update_modification, modification_text, normalized_date_format
from .locations import ARCHIVE_PROTOCOLS, Location, archive_protocol, archive_source_path, archive_subfolder_name, archive_url, parent_location
from .launch_targets import LaunchRequest, parse_launch_arguments, parse_launch_requests, is_browsable_location
from .external_locations import ExternalLocationsMixin
from .view_policy import per_folder_views, special_view, ViewPolicyMixin
from .tab_ui import DolphinTabBar
from .session_state import SessionMixin
from .folder_icons import standard_folder_icons, themed_folder_icon
from . import __version__, RELEASE_DATE, AUTHOR, BUILD_REVISION
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
                elif is_dangling_symlink(path):
                    row = basic_entry(path)
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
        from .directory_listing import local_entries
        from .media import AUDIO_EXT, IMAGE_EXT
        media_extensions = EXTENSIONS | AUDIO_EXT | IMAGE_EXT
        try:
            initial = []
            for path, is_dir, hidden in local_entries(self.folder, self.isInterruptionRequested):
                if hidden and not self.show_hidden:
                    continue
                try:
                    entry = (basic_entry(path, True, hidden=hidden) if is_dir else
                             listed_media_entry(path, self.isInterruptionRequested, hidden=hidden)
                             if path.suffix.lower() in media_extensions else basic_entry(path, hidden=hidden))
                    if is_dir:
                        entry.values[1], entry.sort_values[1] = '', -1
                    update_modification(entry)
                    initial.append(entry)
                except OSError:
                    continue
            initial.sort(key=lambda entry: natural_name_key(entry.path.name))
            if self.isInterruptionRequested():
                return
            self.initial.emit(initial)
            if not self.recursive:
                return
            # This specialised media discovery retains bounded os.walk traversal;
            # the ordinary visible root always comes from KCoreDirLister.
            listed, resolved = [], []
            for root, dirs, files in os.walk(self.folder, onerror=lambda error: self.notice.emit(str(error)), followlinks=False):
                if self.isInterruptionRequested():
                    return
                hidden = hidden_names(root)
                if not self.show_hidden:
                    dirs[:] = [name for name in dirs if not local_is_hidden(Path(root) / name, hidden)]
                    files = [name for name in files if not local_is_hidden(Path(root) / name, hidden)]
                if Path(root) == Path(self.folder):
                    continue
                for name in files:
                    if self.isInterruptionRequested():
                        return
                    path = Path(root) / name
                    if path.suffix.lower() not in media_extensions:
                        continue
                    try:
                        entry = listed_media_entry(path, self.isInterruptionRequested, hidden=local_is_hidden(path, hidden))
                        update_modification(entry)
                        if entry.metadata_loaded:
                            resolved.append(entry)
                        else:
                            listed.append(entry)
                        if len(resolved) >= 32:
                            self.resolved.emit(resolved)
                            resolved = []
                        if len(listed) >= 128:
                            self.listed.emit(listed)
                            listed = []
                    except OSError:
                        continue
            if listed:
                self.listed.emit(listed)
            if resolved:
                self.resolved.emit(resolved)
        except InterruptedError:
            return
        except Exception as error:
            if not self.isInterruptionRequested():
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
        if not super().filterAcceptsR…63965 tokens truncated…er):
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
        if getattr(self, '_directory_snapshot_worker', None) is not None:
            self._directory_snapshot_pending = True
            return
        if any(p.scanning for p in self.panes) or self.move_worker is not None or getattr(self, '_metadata_worker', None):
            self.visible_timer.start()
            return
        from .directory_listing import DirectorySnapshotWorker
        worker = DirectorySnapshotWorker(self._visible_snapshots)
        self._directory_snapshot_worker = worker
        def finished():
            self._directory_snapshot_worker = None
            if not self.closing:
                self._directory_inventory = worker.snapshots
                self.reconcile_visible_directories()
                if getattr(self, '_directory_snapshot_pending', False):
                    self._directory_snapshot_pending = False
                    self.visible_timer.start()
            worker.deleteLater()
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Actualisation des dossiers'))

    def reconcile_visible_directories(self):
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
                known = {row.path: row for pane in self.panes if pane.folder and Path(pane.folder).resolve() == folder for row in pane.model.rows}
                changed.update(path for path, value in current.items()
                               if path not in known or not known[path].file_signature
                               or known[path].file_signature[2:] != (value[2], value[1])
                               or known[path].is_hidden != value[3])
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
        # Preserve all transfer workers before any shutdown/cancellation path.
        if self.pending_transfers():
            self.save_tab_session()
            self.save_pane_column_states()
            self.allow_transfer_close()
            event.ignore()
            return
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
