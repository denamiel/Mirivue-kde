from .item_presentation import map_file_index
from .i18n import tr, trf
tr('User-facing grouping and confirmed file moves.')
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import Qt, QMimeData, QUrl, QThread, Signal, QTimer
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QMessageBox, QInputDialog, QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
from .file_moves import MoveWorker, normalize_sources, suggest_folder, valid_name, invalid_name_reason, exists
from .extensions import Rename, apply_renames, fingerprint
from . import library
from .locations import Location
from .platform_services import services

def cancelled_existing_file_conflict(sources, destination, error):
    """Recognize KIO's empty-error response to cancelling one local conflict.

    Keep genuine failures visible: this applies only to a known collision
    whose source and destination still exist after the job stopped.
    """
    if error or len(sources) != 1:
        return False
    source_url, target_url = QUrl(str(sources[0])), QUrl(str(destination))
    if not source_url.isLocalFile() or not target_url.isLocalFile():
        return False
    source = Path(source_url.toLocalFile())
    target = Path(target_url.toLocalFile()) / source.name
    return source != target and source.exists() and target.exists()

def transfer_labels(operation):
    """Use the action the user chose in progress and result messages."""
    return {
        'move': (tr('Déplacement'), tr('Le déplacement a échoué.'), tr('Déplacement terminé.')),
        'copy': (tr('Copie'), tr('La copie a échoué.'), tr('Copie terminée.')),
        'copyas': (tr('Copie'), tr('La copie a échoué.'), tr('Copie terminée.')),
        'moveas': (tr('Déplacement'), tr('Le déplacement a échoué.'), tr('Déplacement terminé.')),
        'trash': (tr('Mise à la corbeille'), tr('La mise à la corbeille a échoué.'), tr('Mise à la corbeille terminée.')),
        'link': (tr('Création de lien'), tr('La création du lien a échoué.'), tr('Lien créé.')),
        'extract': (tr('Extraction'), tr('L’extraction a échoué.'), tr('Extraction terminée.')),
        'restore': (tr('Restauration'), tr('La restauration a échoué.'), tr('Restauration terminée.')),
        'delete': (tr('Suppression définitive'), tr('La suppression définitive a échoué.'), tr('Suppression définitive terminée.')),
    }.get(operation, (tr('Transfert de fichiers'), tr('Le transfert de fichiers a échoué.'), tr('Transfert terminé.')))

def readable_transfer_error(error, fallback):
    """Do not expose internal backend names supplied by the native helper."""
    return error if error and 'KIO' not in error.upper() else fallback

class KioTransferWorker(QThread):
    progress = Signal(int)
    completed = Signal(bool, str)

    def __init__(self, sources, destination, move=False, operation=None):
        super().__init__()
        self.sources = list(sources)
        self.destination = str(destination)
        self.move = move
        self.operation = operation or (tr('move') if move else tr('copy'))
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        ok, error = services.transfer_kio(self.sources, self.destination, self.move, self.progress.emit, lambda: self.cancelled, operation=self.operation)
        self.completed.emit(ok, error)

class KioUndoWorker(QThread):
    completed = Signal(bool, str)

    def run(self):
        ok, error = services.undo_kio()
        self.completed.emit(ok, error)

class KioRedoWorker(QThread):
    completed = Signal(bool, str)

    def run(self):
        ok, error = services.redo_kio()
        self.completed.emit(ok, error)

class KioDirectoryWorker(QThread):
    completed = Signal(bool, str, str)

    def __init__(self, parent_url, name, parent=None):
        super().__init__(parent)
        self.parent_url = str(parent_url)
        self.name = str(name)

    def run(self):
        ok, error = services.create_directory(self.parent_url, self.name)
        self.completed.emit(ok, error, self.name)

class MoveDialog(QDialog):

    def __init__(self, worker, parent):
        super().__init__(parent)
        self.worker = worker

    def reject(self):
        self.worker.requestInterruption()
        self.setWindowTitle(tr('Annulation après sécurisation du fichier…'))
from .background_transfers import BackgroundTransfers

class MovementMixin(BackgroundTransfers):

    def native_drop_completed(self):
        """Reconcile both panes after a Places or breadcrumb KIO drop.

        KIO owns the operation and its choice menu. Observe the actual files
        rather than guessing whether the user chose Copy, Move or Link.
        """
        self.sync_visible_directories()
        for pane in self.panes:
            if not pane.folder:
                continue
            if Location.from_value(pane.folder).is_uri or self.is_network_location(pane.folder):
                self.queue_pane_rescan(pane)
            else:
                folder = Path(pane.folder)
                if not folder.is_dir():
                    while not folder.is_dir() and folder != folder.parent:
                        folder = folder.parent
                    self.run_in_pane(pane, self.navigate, str(folder))

    def record_local_renames(self, renamed):
        """Keep every integrated rename in the same chronological undo history."""
        if not renamed:
            return
        self.file_undo_history().append(('rename', (
            dict(renamed), {target: fingerprint(target) for target in renamed.values()}
        )))
        self._file_redo_history = []
        self.update_kio_undo_action(services._kio_undo_available, services._kio_undo_text)
        self.update_kio_redo_action(services._kio_redo_available, services._kio_redo_text)

    def file_undo_history(self):
        if not hasattr(self, '_file_undo_history'):
            self._file_undo_history = []
        return self._file_undo_history

    def file_redo_history(self):
        if not hasattr(self, '_file_redo_history'):
            self._file_redo_history = []
        return self._file_redo_history

    def record_kio_history(self):
        self.file_undo_history().append(('kio', None))
        self._file_redo_history = []
        self.update_kio_undo_action(services._kio_undo_available, services._kio_undo_text)
        self.update_kio_redo_action(services._kio_redo_available, services._kio_redo_text)

    def apply_local_rename_history(self, undo):
        source_history = self.file_undo_history() if undo else self.file_redo_history()
        if not source_history or source_history[-1][0] != 'rename':
            return False
        mapping, signatures = source_history[-1][1]
        reverse = {target: source for source, target in mapping.items()} if undo else mapping
        try:
            if any(fingerprint(source) != signatures[source] for source in reverse):
                raise OSError(tr('Un fichier a changé depuis le renommage.'))
            plans = [Rename(source, target, signatures[source]) for source, target in reverse.items()]
            completed, errors = apply_renames(plans)
            if errors or len(completed) != len(reverse):
                raise OSError(tr('\n').join(errors) or tr('Le renommage n’a pas pu être annulé.'))
            new_signatures = {target: fingerprint(target) for target in reverse.values()}
        except (OSError, ValueError, KeyError) as error:
            QMessageBox.warning(self, tr('Renommage impossible'), str(error))
            self.refresh_kio_panes()
            return False
        source_history.pop()
        (self.file_redo_history() if undo else self.file_undo_history()).append(
            ('rename', (mapping, new_signatures)))
        self.update_kio_undo_action(services._kio_undo_available, services._kio_undo_text)
        self.update_kio_redo_action(services._kio_redo_available, services._kio_redo_text)
        self.refresh_kio_panes()
        return True

    def undo_remote_transfer(self):
        if self.file_undo_history() and self.file_undo_history()[-1][0] == 'rename':
            self.apply_local_rename_history(True)
            return
        worker = getattr(self, 'kio_undo_worker', None)
        if worker is not None and worker.isRunning():
            return
        worker = KioUndoWorker(self)
        self.kio_undo_worker = worker
        self.kio_undo_action.setEnabled(False)

        def complete(ok, error):
            # Keep no reference to the QThread wrapper after its work is
            # complete; Qt deletes it below and a later undo must be able to
            # start a fresh worker safely.
            if getattr(self, 'kio_undo_worker', None) is worker:
                self.kio_undo_worker = None
            if not ok and error:
                QMessageBox.warning(self, tr('Annulation impossible'), readable_transfer_error(error, tr('La dernière opération de fichiers n’a pas pu être annulée.')))
            elif ok:
                if self.file_undo_history() and self.file_undo_history()[-1][0] == 'kio':
                    self.file_redo_history().append(self.file_undo_history().pop())
                self.refresh_kio_panes()
            self.update_kio_undo_action(services._kio_undo_available, services._kio_undo_text)
            self.update_kio_redo_action(services._kio_redo_available, services._kio_redo_text)

        worker.completed.connect(complete)
        worker.finished.connect(lambda: setattr(self, 'kio_undo_worker', None) if getattr(self, 'kio_undo_worker', None) is worker else None)
        worker.finished.connect(worker.deleteLater)
        self.start_runtime_worker(worker, tr('Annulation KIO'))

    def redo_kio_operation(self):
        if self.file_redo_history() and self.file_redo_history()[-1][0] == 'rename':
            self.apply_local_rename_history(False)
            return
        worker = getattr(self, 'kio_redo_worker', None)
        if worker is not None and worker.isRunning():
            return
        worker = KioRedoWorker(self)
        self.kio_redo_worker = worker
        self.kio_redo_action.setEnabled(False)

        def complete(ok, error):
            if getattr(self, 'kio_redo_worker', None) is worker:
                self.kio_redo_worker = None
            if not ok and error:
                QMessageBox.warning(self, tr('Rétablissement impossible'), readable_transfer_error(error, tr('La dernière opération de fichiers n’a pas pu être rétablie.')))
            elif ok:
                if self.file_redo_history() and self.file_redo_history()[-1][0] == 'kio':
                    self.file_undo_history().append(self.file_redo_history().pop())
                self.refresh_kio_panes()
            self.update_kio_undo_action(services._kio_undo_available, services._kio_undo_text)
            self.update_kio_redo_action(services._kio_redo_available, services._kio_redo_text)

        worker.completed.connect(complete)
        worker.finished.connect(lambda: setattr(self, 'kio_redo_worker', None) if getattr(self, 'kio_redo_worker', None) is worker else None)
        worker.finished.connect(worker.deleteLater)
        self.start_runtime_worker(worker, tr('Rétablissement KIO'))

    def create_kio_folder(self, name):
        if getattr(self, 'kio_directory_worker', None) is not None and self.kio_directory_worker.isRunning():
            return
        worker = KioDirectoryWorker(self.folder, name, self)
        self.kio_directory_worker = worker
        self.new_folder_action.setEnabled(False)

        def complete(ok, error, created_name):
            self.new_folder_action.setEnabled(True)
            if not ok:
                QMessageBox.warning(self, tr('Création impossible'), readable_transfer_error(error, tr('Le dossier n’a pas pu être créé.')))
                return
            self.record_kio_history()
            self.show_activity_message(trf('Dossier « \x1f0\x1f » créé.', created_name), 5000)
            self.scan()

        worker.completed.connect(complete)
        worker.finished.connect(worker.deleteLater)
        self.start_runtime_worker(worker, tr('Création de dossier'))

    def update_kio_undo_action(self, available, text=''):
        action = getattr(self, 'kio_undo_action', None)
        if action is None:
            return
        if self.file_undo_history() and self.file_undo_history()[-1][0] == 'rename':
            action.setEnabled(True)
            action.setToolTip(tr('Annuler le dernier renommage intégré.'))
            return
        action.setEnabled(bool(available) or bool(self.file_undo_history()))
        action.setToolTip(trf('Annule la dernière opération de fichiers : \x1f0\x1f', text) if available and text and 'KIO' not in text.upper() else tr('Annule la dernière opération de fichiers.'))

    def update_kio_redo_action(self, available, text=''):
        action = getattr(self, 'kio_redo_action', None)
        if action is None:
            return
        if self.file_redo_history() and self.file_redo_history()[-1][0] == 'rename':
            action.setEnabled(True)
            action.setToolTip(tr('Rétablir le dernier renommage intégré.'))
            return
        action.setEnabled(bool(available) or bool(self.file_redo_history()))
        action.setToolTip(trf('Rétablit la dernière opération de fichiers : \x1f0\x1f', text) if available and text and 'KIO' not in text.upper() else tr('Rétablit la dernière opération de fichiers.'))

    @staticmethod
    def pane_affected_by_deletion(folder, sources, operation):
        """Find listings touched by a delete/trash job, including Trash views."""
        pane_url = QUrl(str(folder))
        source_urls = [QUrl(str(source)) for source in sources]
        if pane_url.scheme().casefold() == 'trash':
            return operation == 'trash' or any(
                url.scheme().casefold() == 'trash' for url in source_urls)
        if not folder:
            return False
        if pane_url.scheme() and not pane_url.isLocalFile():
            pane_location = pane_url.path().rstrip('/') or '/'
            for url in source_urls:
                if url.scheme() != pane_url.scheme() or url.authority() != pane_url.authority():
                    continue
                source_location = url.path().rstrip('/') or '/'
                if (source_location == pane_location
                        or source_location.startswith(pane_location.rstrip('/') + '/')
                        or pane_location.startswith(source_location.rstrip('/') + '/')):
                    return True
            return False
        pane_path = Path(pane_url.toLocalFile() if pane_url.isLocalFile() else folder).absolute()
        for url in source_urls:
            if not url.isLocalFile():
                continue
            source_path = Path(url.toLocalFile()).absolute()
            if (pane_path == source_path.parent or pane_path in source_path.parents
                    or pane_path == source_path or source_path in pane_path.parents):
                return True
        return False

    def refresh_kio_panes(self, sources=None, operation=None):
        """Apply deletions to visible rows; refresh listings with unknown changes."""
        if sources is not None and operation in ('trash', 'delete'):
            self.reconcile_deleted_panes(sources, operation)
            return
        original = self.bound_pane
        for pane in self.panes:
            if not pane.folder:
                continue
            self.queue_pane_rescan(pane)
        if self.bound_pane is not original:
            self.bind_pane(original)

    def reconcile_deleted_panes(self, sources, operation):
        """Remove confirmed missing local entries without resetting either view."""
        self.capture_pane()
        local = [Path(url.toLocalFile()).absolute() for source in sources
                 if (url := QUrl(str(source))).isLocalFile()]
        for pane in self.panes:
            if not pane.folder or not self.pane_affected_by_deletion(pane.folder, sources, operation):
                continue
            location = QUrl(str(pane.folder))
            # KIO chooses Trash entry names and remote listings; only their
            # listing job can tell us exactly which rows to display.
            if (location.scheme() and not location.isLocalFile()) or pane.scanning or pane.search_active or self.recursive.isChecked():
                self.queue_pane_rescan(pane)
                continue
            folder = Path(location.toLocalFile() if location.isLocalFile() else pane.folder).absolute()
            if any(folder == source or source in folder.parents for source in local):
                destination = folder
                while not destination.is_dir() and destination != destination.parent:
                    destination = destination.parent
                self.run_in_pane(pane, self.navigate, str(destination))
                continue
            missing = {source for source in local if source.parent == folder
                       and not source.exists() and not source.is_symlink()}
            if missing:
                pane.model.remove_paths(missing)
                self.run_in_pane_silent(pane, self.update_summary)

    def remember_transfer_selection(self, sources, destination, operation):
        """Keep arrivals selected after KIO's destination listing is rebuilt."""
        if operation in ('trash', 'delete', 'restore'):
            return
        target = QUrl(str(destination))
        named_target = operation in ('copyas', 'moveas')
        parent = QUrl(target)
        if named_target:
            parent.setPath(target.path().rstrip('/').rsplit('/', 1)[0] or '/')
        names = ({target.path().rstrip('/').rsplit('/', 1)[-1]} if named_target else
                 {QUrl(str(source)).path().rstrip('/').rsplit('/', 1)[-1] for source in sources})
        names.discard('')
        if not names:
            return
        for pane in self.panes:
            if not pane.folder:
                continue
            folder = QUrl.fromLocalFile(str(pane.folder)) if not Location.from_value(pane.folder).is_uri else QUrl(str(pane.folder))
            if (folder.scheme(), folder.authority(), folder.path().rstrip('/')) != (parent.scheme(), parent.authority(), parent.path().rstrip('/')):
                continue
            pending = getattr(pane, 'pending_transfer_selection', None)
            if pending is None or pending[0] != pane.folder:
                pending = (pane.folder, set())
                pane.pending_transfer_selection = pending
            pending[1].update(names)

    def update_local_kio_transfer(self, sources, destination, operation, existing_target=False):
        """Patch direct children as they arrive, like Dolphin's item listing."""
        if operation not in ('copy', 'move', 'copyas', 'moveas', 'link') or existing_target:
            return False
        urls = [QUrl(str(source)) for source in sources]
        target_url = QUrl(str(destination))
        if not target_url.isLocalFile() or not all(url.isLocalFile() for url in urls):
            return False
        if self.recursive.isChecked():
            return False
        if any(pane.scanning for pane in self.panes):
            return False
        named = operation in ('copyas', 'moveas')
        destination_path = Path(target_url.toLocalFile())
        moved = {Path(url.toLocalFile()): (destination_path if named else destination_path / Path(url.toLocalFile()).name)
                 for url in urls}
        if not all(target.exists() or target.is_symlink() for target in moved.values()):
            return False
        self.update_transfer_panes(SimpleNamespace(moved=moved, cancelled=False), operation in ('copy', 'copyas', 'link'))
        self.watch_visible_directories()
        return True

    @staticmethod
    def paths_cross_filesystems(paths, destination):
        """Detect transfers that the local rename worker cannot undo."""
        try:
            destination_device = Path(destination).stat().st_dev
            return any(Path(source).parent.stat().st_dev != destination_device for source in paths)
        except OSError:
            return False

    def start_kio_transfer(self, sources, destination, move=False, clipboard_guard=None, operation=None, on_success=None):
        """Run a native KIO job and refresh the affected pane listings."""
        label, failure, success = transfer_labels(operation or ('move' if move else 'copy'))
        if not services.tool_path(tr('mirivue-kio-service')):
            QMessageBox.warning(self, label + tr(' impossible'), tr('Le service KIO nécessaire à l’annulation de cette opération est indisponible.'))
            return None
        # Record the collision *before* KIO presents its overwrite dialog.
        had_collision = cancelled_existing_file_conflict(sources, destination, '')
        target_url = QUrl(str(destination))
        existing_target = False
        if target_url.isLocalFile():
            target_path = Path(target_url.toLocalFile())
            named = operation in ('copyas', 'moveas')
            candidates = [target_path if named else target_path / QUrl(str(source)).path().rstrip('/').rsplit('/', 1)[-1]
                          for source in sources]
            existing_target = any(candidate.exists() or candidate.is_symlink() for candidate in candidates)
        worker = KioTransferWorker(sources, destination, move=move, operation=operation)
        job = self.register_kio_transfer(worker, sources, destination, worker.operation, label)

        def complete(ok, error):
            cancelled = not ok and (worker.cancelled or error == tr('Transfert annulé.') or
                        (had_collision and cancelled_existing_file_conflict(sources, destination, error)))
            message = tr('Transfert annulé.') if cancelled else success if ok else readable_transfer_error(error, failure)
            self.finish_kio_transfer(job, ok, message, cancelled)
            if not ok:
                if cancelled:
                    self.show_activity_message(tr('Transfert annulé.'), 5000)
                    self.refresh_kio_panes(sources, operation)
                    return
                message = readable_transfer_error(error, failure)
                # The KIO job already has a KDE UI delegate with automatic
                # error handling. Keep the details in the window without
                # raising another dialog or an urgent desktop notification.
                self.show_activity_message(message, 15000)
                self.refresh_kio_panes(sources, operation)
                return
            if clipboard_guard:
                self.clear_cut_clipboard(clipboard_guard)
            if (operation or ('move' if move else 'copy')) not in ('delete', 'restore'):
                self.record_kio_history()
            self.show_activity_message(success, 5000)
            transfer_operation = operation or ('move' if move else 'copy')
            if not self.update_local_kio_transfer(sources, destination, transfer_operation, existing_target):
                self.remember_transfer_selection(sources, destination, transfer_operation)
                self.refresh_kio_panes(sources, operation)
            if on_success is not None:
                # Let this worker's completion unwind before starting a
                # possible follow-up KIO job, such as trashing an archive.
                if not self.transfer_quitting and not worker.cancelled:
                    QTimer.singleShot(0, on_success)

        worker.completed.connect(complete)
        worker.finished.connect(worker.deleteLater)
        self.start_runtime_worker(worker, label)
        return worker

    def start_kio_planned_transfers(self, plans, copy_only=False, clipboard_guard=None):
        """Apply explicitly named destinations in order, each with KIO undo."""
        from .media import companion, AUDIO_EXT, IMAGE_EXT
        from .metadata import EXTENSIONS
        expanded = list(plans)
        selected_sources = {source for source, _target in expanded}
        for source, target in plans:
            side = companion(source)
            if (source.is_file() and source.suffix.lower() in EXTENSIONS | AUDIO_EXT | IMAGE_EXT
                    and side.is_file() and not side.is_symlink() and side not in selected_sources):
                expanded.append((side, companion(target)))
                selected_sources.add(side)
        if (len({target for _source, target in expanded}) != len(expanded)
                or any(exists(target) for _source, target in expanded)):
            QMessageBox.warning(self, tr('Destination indisponible'), tr('Un nom de destination existe déjà. Aucun transfert démarré.'))
            return None
        if self.transfers_locked([path for pair in expanded for path in pair]):
            QMessageBox.information(self, tr('Transfert en cours'), tr('Un élément est déjà réservé par un transfert.'))
            return None

        def next_transfer(index):
            if index == len(expanded):
                if clipboard_guard:
                    self.clear_cut_clipboard(clipboard_guard)
                return
            source, target = expanded[index]
            return self.start_kio_transfer(
                [QUrl.fromLocalFile(str(source)).toString()],
                QUrl.fromLocalFile(str(target)).toString(),
                move=not copy_only, operation='copyas' if copy_only else 'moveas',
                on_success=lambda: next_transfer(index + 1),
            )

        return next_transfer(0)

    def allow_drop_destination(self, paths, destination):
        """Validate local, remote and Trash targets without treating URLs as paths."""
        local_paths = [Path(path) for path in paths if not Location.from_value(path).is_uri]
        if self.scanning or not paths or (local_paths and self.movement_locked(local_paths)):
            return False
        location = Location.from_value(destination)
        if location.is_uri:
            scheme = QUrl(str(destination)).scheme().casefold()
            if scheme in {'zip', 'tar', 'sevenz', 'ar', 'recentlyused', 'timeline', 'search'}:
                return False
            return bool(services.tool_path(tr('mirivue-kio-service')) or services.tool_path(tr('mirivue-kio-transfer')))
        if len(local_paths) != len(paths):
            return bool(services.tool_path(tr('mirivue-kio-service')) or services.tool_path(tr('mirivue-kio-transfer')))
        return self.allow_place_drop(local_paths, Path(destination))

    def drop_operation(self, paths, destination, operation):
        """Perform a drop with the same KIO operations exposed by Dolphin."""
        if operation in (tr('link'), tr('trash')):
            sources = [Location.from_value(path).uri for path in paths]
            target = tr('trash:/') if operation == tr('trash') else Location.from_value(destination).uri
            return self.start_kio_transfer(sources, target, operation=operation)
        return self.move_entries(paths, destination, confirmed=True, copy_only=operation == tr('copy'))

    def selected_entries(self):
        paths = [self.row(i).path for i in self.selected_indexes()]
        local = normalize_sources(path for path in paths if not Location.from_value(path).is_uri)
        remote = dict.fromkeys(str(path) for path in paths if Location.from_value(path).is_uri)
        return [*local, *remote]

    def associated_entries(self, paths):
        tr('Find only low-risk, same-name companion files in the same directory.')
        chosen = set(normalize_sources(paths))
        related = []
        video = {tr('.mkv'), tr('.mp4'), tr('.m4v'), tr('.mov'), tr('.avi'), tr('.webm'), tr('.ogv'), tr('.flv'), tr('.wmv'), tr('.mpeg'), tr('.mpg')}
        images = {tr('.jpg'), tr('.jpeg'), tr('.png'), tr('.tif'), tr('.tiff'), tr('.webp'), tr('.dng'), tr('.cr2'), tr('.cr3'), tr('.nef'), tr('.arw'), tr('.raf'), tr('.orf'), tr('.rw2')}
        raw = {tr('.dng'), tr('.cr2'), tr('.cr3'), tr('.nef'), tr('.arw'), tr('.raf'), tr('.orf'), tr('.rw2')}
        for source in chosen:
            if not source.is_file() or source.suffix.lower() == tr('.xmp'):
                continue
            stem = source.stem
            suffix = source.suffix.lower()
            candidates = []
            if suffix in video:
                candidates += [source.with_name(stem + tail) for tail in (tr('.srt'), tr('.ass'), tr('.ssa'), tr('.vtt'), tr('.sub'), tr('.idx'), tr('.nfo'), tr('.cue'), tr('.chapters.xml'))]
            if suffix in images:
                candidates += [source.with_name(stem + tail) for tail in sorted(images | raw)]
            if suffix in {tr('.mp3'), tr('.flac'), tr('.ogg'), tr('.oga'), tr('.opus'), tr('.m4a'), tr('.m4b'), tr('.wav'), tr('.aif'), tr('.aiff')}:
                candidates += [source.with_name(stem + tail) for tail in (tr('.jpg'), tr('.jpeg'), tr('.png'))]
            for candidate in candidates:
                if candidate not in chosen and candidate not in related and candidate.is_file() and (not candidate.is_symlink()):
                    related.append(candidate)
        return related

    def choose_associated_entries(self, paths, operation, include_xmp=False):
        paths = list(paths)
        if any(Location.from_value(path).is_uri for path in paths):
            # Companion discovery is local. Never turn a KIO URL into a Path.
            return list(dict.fromkeys(paths))
        paths = normalize_sources(paths)
        related = self.associated_entries(paths)
        if include_xmp:
            from .media import companion, AUDIO_EXT, IMAGE_EXT
            from .metadata import EXTENSIONS
            for path in paths:
                if not path.is_file() or path.suffix.lower() not in EXTENSIONS | AUDIO_EXT | IMAGE_EXT:
                    continue
                side = companion(path)
                if side.is_file() and not side.is_symlink() and side not in paths and side not in related:
                    related.append(side)
        if not related:
            return paths
        box = QMessageBox(self)
        box.setWindowTitle(tr('Fichiers associés détectés'))
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(trf('\x1f0\x1f fichier(s) associé(s) ont été trouvé(s). Les inclure dans cette opération de \x1f1\x1f ?', len(related), operation))
        if include_xmp:
            visible = [str(path) for path in related[:8]]
            if len(related) > len(visible):
                visible.append(trf('… et \x1f0\x1f autre(s) dans Détails.', len(related) - len(visible)))
            box.setInformativeText(tr('Fichiers supplémentaires proposés :\n') + tr('\n').join(visible))
        else:
            box.setInformativeText(tr('Les fichiers XMP sont traités automatiquement. Cette proposition concerne notamment les sous-titres, fichiers NFO, chapitres et images RAW/JPEG de même nom.'))
        box.setDetailedText(tr('\n').join((str(path) for path in related)))
        include = box.addButton(tr('Inclure les fichiers associés'), QMessageBox.ButtonRole.AcceptRole)
        only = box.addButton(tr('Fichier(s) sélectionné(s) seulement'), QMessageBox.ButtonRole.ActionRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        cancel.setText(tr('Annuler'))
        box.setDefaultButton(only if include_xmp else include)
        box.exec()
        if box.clickedButton() is include:
            return normalize_sources([*paths, *related])
        if box.clickedButton() is only:
            return paths
        return None

    def select_associated_entries(self, paths):
        from PySide6.QtCore import QItemSelectionModel
        wanted = set(normalize_sources([*paths, *self.associated_entries(paths)]))
        selected = 0
        for row, entry in enumerate(self.model.rows):
            if entry.path not in wanted:
                continue
            index = map_file_index(self.proxy, self.model.index(row, 0))
            if index.isValid():
                self.active_view().selectionModel().select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                selected += 1
        self.show_activity_message(trf('\x1f0\x1f élément(s) sélectionné(s), y compris les fichiers associés visibles.', selected), 6000)

    def movement_locked(self, paths):
        if getattr(self, tr('move_worker'), None) is not None:
            return True
        if hasattr(self, tr('media_locked')) and self.media_locked(paths):
            return True
        jobs = ([self.active_job] if self.active_job else []) + self.job_queue
        if self.transfers_locked(paths):
            return True
        if not jobs or not paths:
            return False
        requested = set(paths)
        if any((requested & job[tr('paths')] for job in jobs)):
            return True
        indexes = []
        for job in jobs:
            index = job.get(tr('_locks'))
            if index is None:
                if len(job[tr('paths')]) > 64:
                    return True
                used = {Path(p).resolve() for p in job[tr('paths')]}
                index = (used, {parent for p in used for parent in p.parents})
                job[tr('_locks')] = index
            indexes.append(index)
        for path in paths:
            p = Path(path).resolve()
            for used, parents in indexes:
                if p in used or p in parents or any((parent in used for parent in p.parents)):
                    return True
        return False

    def start_file_drag(self, view):
        paths = self.selected_entries()
        if not paths or self.scanning or self.movement_locked(paths):
            return
        mime = QMimeData()
        mime.setUrls([QUrl(str(p)) if Location.from_value(p).is_uri else QUrl.fromLocalFile(str(p)) for p in paths])
        mime.setData(tr('application/x-mirivue-files'), b'1')
        drag = QDrag(view)
        drag.setMimeData(mime)
        self.decorate_drag(drag, paths)
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction, Qt.DropAction.MoveAction)

    def allow_place_drop(self, paths, destination):
        destination = Path(destination)
        if self.scanning or not destination.is_dir() or self.movement_locked(paths):
            return False
        target = destination.resolve()
        return not any((p.resolve() == target or (p.is_dir() and (not p.is_symlink()) and (p.resolve() in target.parents)) for p in paths))

    def group_selected(self):
        paths = self.selected_entries()
        if not paths:
            return
        if self.scanning or self.movement_locked(paths):
            QMessageBox.information(self, tr('Opération en cours'), tr('Attendez la fin du traitement des fichiers sélectionnés.'))
            return
        suggestion = suggest_folder(paths)
        while True:
            name, ok = QInputDialog.getText(self, tr('Déplacer vers le nouveau dossier'), trf('Nom du dossier à créer dans :\n\x1f0\x1f\nLes \x1f1\x1f éléments sélectionnés y seront déplacés.', self.folder, len(paths)), text=suggestion)
            if not ok:
                return
            suggestion = name
            if not valid_name(name):
                QMessageBox.warning(self, tr('Nom invalide'), invalid_name_reason(name))
                continue
            target = Path(self.folder) / name
            if target.exists() or target.is_symlink():
                QMessageBox.information(self, tr('Dossier déjà présent'), tr('Choisissez un autre nom. Le dossier existant reste inchangé.'))
                continue
            ok, error = services.create_directory(self.folder, name, require_undo=True)
            if not ok:
                QMessageBox.warning(self, tr('Création impossible'), error)
                return
            self.record_kio_history()
            job = self.move_entries(paths, target, confirmed=True)
            # The directory remains in KIO's undo stack if a transfer fails.
            # Ctrl+Z can then remove the empty directory consistently.
            return

    def plan_moves(self, paths, destination, copy_only=False):
        plans = []
        reserved = {target for job in self.pending_transfers() for _, target in job[tr('plans')]}
        for source in normalize_sources(paths):
            if source.parent.resolve() == destination.resolve() and (not copy_only):
                continue
            target = destination / source.name
            while exists(target) or target in reserved:
                name, ok = QInputDialog.getText(self, tr('Nom déjà utilisé'), trf('« \x1f0\x1f » existe déjà dans la destination.\nSaisissez un autre nom, ou Annuler pour ignorer cet élément.', target.name), text=target.name)
                if not ok:
                    target = None
                    break
                if not valid_name(name):
                    QMessageBox.warning(self, tr('Nom invalide'), invalid_name_reason(name))
                    continue
                target = destination / name
            if target is not None:
                plans.append((source, target))
                reserved.add(target)
        return plans

    def move_entries(self, paths, destination, confirmed=False, copy_only=False, plans_override=None, clipboard_guard=None):
        raw_paths = list(paths or [])
        raw_destination = str(destination)
        if any(Location.from_value(path).is_uri for path in [*raw_paths, raw_destination]):
            if not raw_paths:
                return
            if not confirmed and not copy_only:
                answer = QMessageBox.question(self, tr('Déplacer la sélection'), trf('Déplacer 0 élément(s) vers :\n1', len(raw_paths), raw_destination), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer != QMessageBox.StandardButton.Yes:
                    return
            sources = [Location.from_value(path).uri for path in raw_paths]
            destination_uri = Location.from_value(raw_destination).uri
            return self.start_kio_transfer(sources, destination_uri, move=not copy_only, clipboard_guard=clipboard_guard)
        paths = normalize_sources(paths)
        destination = Path(destination)
        if plans_override is None:
            paths = self.choose_associated_entries(paths, tr('copie') if copy_only else tr('déplacement'))
            if paths is None:
                return
        if not paths or not self.allow_place_drop(paths, destination):
            QMessageBox.warning(self, tr('Déplacement indisponible'), tr('La destination est inaccessible, se trouve dans un dossier sélectionné, ou un élément est utilisé par un traitement.'))
            return
        if not confirmed and (not copy_only) and (QMessageBox.question(self, tr('Déplacer la sélection'), trf('Déplacer \x1f0\x1f élément(s) vers :\n\x1f1\x1f\n\nLes éléments quitteront leur emplacement actuel.', len(paths), destination), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes):
            return
        if plans_override is None:
            from .media import companion, AUDIO_EXT, IMAGE_EXT
            from .metadata import EXTENSIONS
            sources = list(paths)
            for path in paths:
                side = companion(path)
                if (path.is_file() and path.suffix.lower() in EXTENSIONS | AUDIO_EXT | IMAGE_EXT
                        and side.is_file() and not side.is_symlink() and side not in sources):
                    sources.append(side)
            if self.transfers_locked([*sources, *(destination / source.name for source in sources)]):
                QMessageBox.information(self, tr('Transfert en cours'), tr('Un élément est déjà réservé par un transfert.'))
                return
            return self.start_kio_transfer(
                [QUrl.fromLocalFile(str(source)).toString() for source in sources],
                QUrl.fromLocalFile(str(destination)).toString(),
                move=not copy_only, clipboard_guard=clipboard_guard,
            )
        plans = plans_override if plans_override is not None else self.plan_moves(paths, destination, copy_only)
        if not plans:
            return
        if not self.allow_place_drop(paths, destination):
            return
        return self.start_kio_planned_transfers(plans, copy_only, clipboard_guard)

    def migrate_moved_data(self, worker):
        if not worker.moved:
            return
        records = dict(self.saved_results)
        for pane in self.panes:
            records.update({str(r.path): library.encode_row(r) for r in pane.model.rows})
        for old, data in records.items():
            old_path = Path(old)
            for source, target in worker.moved.items():
                if old_path != source and source not in old_path.parents:
                    continue
                try:
                    row = library.decode_row(data)
                    if row.file_signature != worker.source_signatures.get(old_path):
                        continue
                    row.path = target / old_path.relative_to(source) if old_path != source else target
                    row.file_signature = fingerprint(row.path)
                    row.values[0] = row.path.name
                    row.sort_values[0] = row.path.name.casefold()
                    row.duplicate_group = 0
                    self.saved_results[str(row.path)] = library.encode_row(row)
                    self.result_cache[row.path] = row
                    if not exists(old_path):
                        self.saved_results.pop(old, None)
                        self.result_cache.pop(old_path, None)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                break
        for key, value in worker.note_updates.items():
            self.settings.setValue(key, value)
        library.write(self.settings, tr('results'), self.saved_results)
        self.clear_duplicates()
        # Keep shared KDE Places bookmarks aligned when Mirivue itself moves
        # the bookmarked directory (or a parent directory containing it).
        for place in self.current_place_entries():
            url = str(place.get('url') or '')
            source_path = QUrl(url).toLocalFile() if url.startswith('file:') else ''
            if not source_path:
                continue
            bookmarked = Path(source_path)
            for source, target in worker.moved.items():
                if not exists(source) and (bookmarked == source or source in bookmarked.parents):
                    relocated = target / bookmarked.relative_to(source)
                    new_url = QUrl.fromLocalFile(str(relocated)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
                    services.change_place('relocate', url, new_url)
                    break
