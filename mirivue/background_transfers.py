from .item_presentation import map_file_index
from .i18n import tr, trf
tr('Serialized, non-modal transfers. All widget updates stay on the GUI thread.')
from pathlib import Path
import json
from PySide6.QtCore import Qt, QTimer, QItemSelectionModel, QProcess, QUrl
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy, QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QTextBrowser, QMessageBox, QSystemTrayIcon, QWidget
from .file_moves import MoveWorker, exists
from .platform_services import services

def transfer_url_text(value):
    url = QUrl(str(value))
    if url.password():
        url.setPassword('')
    return url.toLocalFile() if url.isLocalFile() else url.toDisplayString()

class BackgroundTransfers:

    def kio_transfer_workers(self):
        return [job['worker'] for job in self.pending_transfers()
                if job.get('native') and job.get('worker') is not None]

    @property
    def kio_transfer_worker(self):
        # Compatibility for callers checking whether any native transfer is
        # active. Cancellation always targets the selected job, never this.
        return next(iter(self.kio_transfer_workers()), None)

    def register_kio_transfer(self, worker, sources, destination, operation, label):
        urls = [QUrl(str(source)) for source in sources]
        target = QUrl(str(destination))
        plans = []
        locked = list(urls)
        if operation in ('copy', 'move', 'copyas', 'moveas', 'link', 'extract'):
            for source in urls:
                arrival = QUrl(target)
                if operation not in ('copyas', 'moveas'):
                    arrival.setPath(target.path().rstrip('/') + '/' + source.fileName())
                locked.append(arrival)
                if source.isLocalFile() and arrival.isLocalFile():
                    plans.append((Path(source.toLocalFile()), Path(arrival.toLocalFile())))
        used = {Path(url.toLocalFile()).resolve() for url in locked if url.isLocalFile()}
        job = dict(native=True, worker=worker, sources=list(sources), destination=destination,
                   operation=operation, label=label, plans=plans, copy=operation in ('copy', 'copyas', 'extract', 'link'),
                   state=tr('En cours'), message=tr('La progression détaillée est gérée par KDE.'),
                   count=0, errors=[], locks=(used, {parent for p in used for parent in p.parents}),
                   url_locks={url.toString().rstrip('/') for url in locked if not url.isLocalFile()})
        self.transfer_history.append(job)
        self.update_transfer_footer()
        return job

    def finish_kio_transfer(self, job, ok, message, cancelled=False):
        job.pop('worker', None)
        job['locks'] = (set(), set())
        job['url_locks'] = set()
        job['plans'] = []
        job['state'] = tr('Interrompu') if cancelled else tr('Terminé') if ok else tr('À vérifier')
        job['message'] = message
        job['count'] = len(job['sources']) if ok else 0
        if not ok and not cancelled:
            job['errors'].append(message)
        self.update_transfer_footer()
        if self.transfer_quitting and not self.pending_transfers():
            QTimer.singleShot(0, self.close)

    def pending_transfers(self):
        return [j for j in getattr(self, tr('transfer_history'), []) if j[tr('state')] in (tr('En attente'), tr('En cours'), tr('Arrêt en cours'))]

    def clear_transfer_history(self):
        terminal = {tr('Interrompu'), tr('À vérifier'), tr('Terminé'), 'Interrompu', 'À vérifier', 'Terminé', 'Interrupted', 'Needs Attention', 'Completed'}
        finished = [job for job in self.transfer_history if job.get(tr('state')) in terminal and job is not self.active_transfer]
        if not finished:
            return 0
        self.transfer_history[:] = [job for job in self.transfer_history if not any((job is done for done in finished))]
        self.update_transfer_footer()
        return len(finished)

    def transfers_locked(self, paths):
        pending = self.pending_transfers()
        if not pending:
            return False
        for path in paths:
            url = QUrl(str(path))
            if url.scheme() and not url.isLocalFile():
                value = url.toString().rstrip('/')
                if any(value == used or value.startswith(used + '/') or used.startswith(value + '/')
                       for job in pending for used in job.get('url_locks', ())):
                    return True
                continue
            p = Path(url.toLocalFile() if url.isLocalFile() else path).resolve()
            for job in pending:
                used, parents = job[tr('locks')]
                if p in used or p in parents or any((parent in used for parent in p.parents)):
                    return True
        return False

    def create_transfer_footer(self, layout):
        self.transfer_history = []
        self.active_transfer = None
        self.transfer_quitting = False
        row = QVBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        self.transfer_label = QLabel()
        self.transfer_label.setTextFormat(Qt.TextFormat.PlainText)
        self.transfer_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.transfer_bar = QProgressBar()
        self.transfer_bar.setMinimumWidth(0)
        self.transfer_bar.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.transfer_bar.setMaximumWidth(380)
        row.addWidget(self.transfer_label)
        row.addWidget(self.transfer_bar)
        for widget in (self.transfer_label, self.transfer_bar):
            widget.hide()
        layout.addLayout(row)

    def queue_transfer(self, plans, copy_only, clipboard_guard=None):
        used = {p.resolve() for pair in plans for p in pair}
        from .media import companion
        for source, target in plans:
            if source.is_file() and companion(source).exists():
                used.update((companion(source).resolve(), companion(target).resolve()))
        job = {tr('plans'): plans, tr('copy'): copy_only, tr('clipboard_guard'): clipboard_guard, tr('state'): tr('En attente'), tr('message'): tr('En attente'), tr('done'): 0, tr('total'): 0, tr('errors'): [], tr('locks'): (used, {parent for p in used for parent in p.parents}), tr('count'): 0}
        self.transfer_history.append(job)
        self.update_transfer_footer()
        QTimer.singleShot(0, self.start_next_transfer)
        return job

    def start_next_transfer(self):
        if self.active_transfer or self.closing:
            return
        job = next((j for j in self.transfer_history if j[tr('state')] == tr('En attente')), None)
        if job is None:
            return
        if self.move_worker is not None:
            QTimer.singleShot(100, self.start_next_transfer)
            return
        job[tr('state')] = tr('En cours')
        self.active_transfer = job
        worker = MoveWorker(job[tr('plans')], copy_only=job[tr('copy')])
        job[tr('worker')] = worker
        self.start_plasma_transfer_progress(job)

        def progress(done, total, message):
            job.update(done=done, total=total, message=message, count=len(worker.moved))
            self.update_transfer_footer()
            self.send_plasma_transfer_progress(job, {
                'event': 'progress', 'value': int(done * 100 / total) if total else 0,
                'total': total, 'completed': len(worker.moved), 'message': message,
            })
        worker.progress.connect(progress)
        worker.finished.connect(lambda: self.finish_transfer(job))
        self.start_runtime_worker(worker, tr('Copie de fichiers') if job[tr('copy')] else tr('Déplacement de fichiers'))
        self.update_transfer_footer()

    def finish_transfer(self, job):
        worker = job.pop(tr('worker'))
        job[tr('errors')] = list(worker.errors)
        job[tr('count')] = len(worker.moved)
        job[tr('state')] = tr('Interrompu') if worker.cancelled else tr('À vérifier') if worker.errors else tr('Terminé')
        job[tr('message')] = trf('\x1f0\x1f élément(s) ', job['count']) + (tr('copié(s).') if job[tr('copy')] else tr('déplacé(s).'))
        self.send_plasma_transfer_progress(job, {
            'event': 'finish', 'ok': not worker.cancelled and not worker.errors,
            'cancelled': worker.cancelled,
            'error': tr('Transfert annulé.') if worker.cancelled else '\n'.join(worker.errors),
        })
        if worker.cancelled:
            job[tr('message')] += tr(' Les éléments terminés restent à destination ; les autres restent à la source.')
        clipboard_guard = job.get(tr('clipboard_guard'))
        if clipboard_guard and not worker.cancelled and len(worker.moved) == len(job[tr('plans')]) and all(not exists(source) for source, _target in job[tr('plans')]):
            self.clear_cut_clipboard(clipboard_guard)
        try:
            self.migrate_moved_data(worker)
        except Exception as error:
            job[tr('errors')].append(tr('Transfert terminé, mais certaines données Mirivue n’ont pas été actualisées : ') + str(error))
            job[tr('state')] = tr('À vérifier')
        self.active_transfer = None
        worker.deleteLater()
        if job.get(tr('cleanup')):
            try:
                job[tr('cleanup')].rmdir()
            except OSError:
                pass
        if not self.transfer_quitting:
            self.reload_places()
            if self.recursive.isChecked():
                self.refresh_recursive_transfer_panes([p for pair in job[tr('plans')] for p in pair])
            else:
                self.update_transfer_panes(worker, job[tr('copy')])
        self.update_transfer_footer()
        self.show_activity_message(job[tr('message')] + (tr(' Consultez les erreurs dans Transferts…') if job[tr('errors')] else ''), 15000)
        if self.transfer_quitting:
            QTimer.singleShot(0, self.close)
        else:
            QTimer.singleShot(0, self.start_next_transfer)

    def refresh_recursive_transfer_panes(self, paths):
        tr('Rescan only recursive panes related to a completed transfer.')
        changed = [Path(path).resolve() for path in paths]
        self.capture_pane()
        original = self.bound_pane
        for pane in self.panes:
            if not pane.folder:
                continue
            folder = Path(pane.folder).resolve()
            related = any((folder == path or folder in path.parents or path in folder.parents for path in changed))
            if related:
                self.queue_pane_rescan(pane)
        self.bind_pane(original)
        self.sync_pane_controls()

    def update_transfer_panes(self, worker, copy_only):
        tr('Patch visible directory models after a transfer, preserving metadata and selection.')
        if not worker.moved:
            return
        from . import library
        from .metadata import EXTENSIONS, basic_entry
        from .media import AUDIO_EXT, expected_kind
        moved = dict(worker.moved)
        self.capture_pane()
        thumbnail_sources = {source: next((pane.model.thumbnails[source] for pane in self.panes if source in pane.model.thumbnails), None) for source in moved}
        original = self.bound_pane
        for pane in self.panes:
            if not pane.folder:
                continue
            folder = Path(pane.folder)
            relocated = next((target / folder.relative_to(source) for source, target in moved.items() if not copy_only and (folder == source or source in folder.parents)), None)
            if relocated is not None:
                self.run_in_pane(pane, self.navigate, str(relocated))
                continue
            removed = [source for source in moved if not copy_only and source.parent == folder]
            arrived = [(source, target) for source, target in moved.items() if target.parent == folder]
            if not removed and (not arrived):
                continue
            pane.model.remove_paths(removed)
            selected = []
            missing_previews = False
            needs_duration = []
            for source, target in arrived:
                # The directory watcher may have inserted this item already.
                # Replace its row instead of showing the arrival twice.
                pane.model.remove_paths({target})
                cached = self.result_cache.get(target)
                if cached is not None:
                    try:
                        row = library.decode_row(library.encode_row(cached))
                    except (KeyError, TypeError, ValueError):
                        row = basic_entry(target)
                else:
                    row = basic_entry(target)
                if target.suffix.casefold() in EXTENSIONS | AUDIO_EXT and not row.is_dir:
                    row.is_video = target.suffix.casefold() in EXTENSIONS
                    row.media_type = expected_kind(target)
                    if row.sort_values[2] < 0:
                        needs_duration.append(target)
                    if not row.metadata_loaded:
                        row.values[10] = row.sort_values[10] = tr('Informations détaillées non lues')
                icon = thumbnail_sources.get(source)
                if icon is not None:
                    # DecorationRole is read during rowsInserted. Publish the
                    # existing thumbnail before inserting the destination row.
                    pane.model.thumbnails[target] = icon
                elif pane.model.show_thumbnails and not row.is_dir:
                    missing_previews = True
                pane.model.add(row)
                selected.append(target)
            first = True
            for target in selected:
                source_index = next((pane.model.index(i, 0) for i, row in enumerate(pane.model.rows) if row.path == target), None)
                index = map_file_index(pane.proxy, source_index) if source_index is not None else None
                if index is None or not index.isValid():
                    continue
                flags = (QItemSelectionModel.SelectionFlag.ClearAndSelect if first else QItemSelectionModel.SelectionFlag.Select) | QItemSelectionModel.SelectionFlag.Rows
                for view in (pane.table, pane.icons, pane.compact):
                    view.selectionModel().select(index, flags)
                if first:
                    pane.content_stack.currentWidget().scrollTo(index)
                    first = False
            if missing_previews and not pane.scanning:
                # Use the normal KDE preview worker for newly arrived files,
                # exactly as after listing a directory. This also picks up
                # files whose source thumbnail was not loaded yet.
                self.run_in_pane(pane, self.start_thumbnails)
            if needs_duration and not pane.scanning:
                self.start_duration_lookup(pane, needs_duration)
        self.bind_pane(original)
        self.sync_pane_controls()
        self.update_pane_emphasis()

    def update_transfer_footer(self):
        pending = [job for job in self.pending_transfers() if not job.get('native')]
        job = self.active_transfer or (pending[0] if pending else None)
        if job:
            self.transfer_label.setText((tr('Copie') if job[tr('copy')] else tr('Déplacement')) + trf(' — \x1f0\x1f — \x1f1\x1f en attente', job['message'], len(pending) - 1))
            if job[tr('total')] > 0:
                self.transfer_bar.setRange(0, job[tr('total')])
                self.transfer_bar.setValue(job[tr('done')])
                self.transfer_bar.setFormat(tr('%p %'))
            else:
                self.transfer_bar.setRange(0, 0)
                self.transfer_bar.setFormat(tr('Inventaire…'))
            self.transfer_label.setToolTip(job[tr('message')])
        if hasattr(self, 'update_operations_button_visibility'):
            self.update_operations_button_visibility()
        self.sync_activity_progress_visibility()

    def cancel_transfer(self, job):
        if job.get('native'):
            worker = job.get('worker')
            if worker is not None and job['state'] in (tr('En attente'), tr('En cours')):
                job['state'] = tr('Arrêt en cours')
                job['message'] = tr('Annulation demandée pour cette opération.')
                worker.cancel()
                self.update_transfer_footer()
            return
        if job[tr('state')] == tr('En attente'):
            job[tr('state')] = tr('Interrompu')
            job[tr('message')] = tr('Annulé avant le démarrage.')
            if job.get(tr('cleanup')):
                try:
                    job[tr('cleanup')].rmdir()
                except OSError:
                    pass
        elif job is self.active_transfer:
            job[tr('state')] = tr('Arrêt en cours')
            job[tr('worker')].requestInterruption()
            job[tr('message')] = tr('Arrêt après sécurisation du fichier…')
        self.update_transfer_footer()

    def send_plasma_transfer_progress(self, job, data):
        """Send only presentation data to the KDE job; the worker owns files."""
        process = job.get('plasma_progress_process')
        if process is None:
            return
        encoded = (json.dumps(data, ensure_ascii=False) + '\n').encode('utf-8')
        if process.state() == QProcess.ProcessState.Running:
            process.write(encoded)
        elif process.state() == QProcess.ProcessState.Starting:
            job['plasma_pending_events'].append(encoded)

    def start_plasma_transfer_progress(self, job):
        # KUiServerV2JobTracker presents the standard Plasma notification.
        # The local checked worker continues if Plasma is not available.
        tool = services.tool_path('mirivue-job-progress') if services.is_plasma else None
        if not tool:
            return
        process = QProcess(self)
        process.setProgram(tool)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        job['plasma_progress_process'] = process
        job['plasma_progress_buffer'] = bytearray()
        job['plasma_pending_events'] = []

        def requests():
            buffer = job['plasma_progress_buffer']
            buffer.extend(bytes(process.readAllStandardOutput()))
            while b'\n' in buffer:
                line, _, remaining = buffer.partition(b'\n')
                buffer[:] = remaining
                try:
                    action = json.loads(line).get('action')
                except (ValueError, UnicodeDecodeError):
                    continue
                if job is not self.active_transfer:
                    continue
                if action == 'cancel':
                    self.cancel_transfer(job)
                elif action == 'pause' and job.get(tr('state')) == tr('En cours'):
                    job[tr('worker')].pause()
                elif action == 'resume' and job.get(tr('state')) == tr('En cours'):
                    job[tr('worker')].resume()

        process.readyReadStandardOutput.connect(requests)
        process.finished.connect(lambda *_: job.pop('plasma_progress_process', None))
        process.finished.connect(process.deleteLater)
        destination = job[tr('plans')][0][1].parent

        def started():
            self.send_plasma_transfer_progress(job, {
                'event': 'start', 'title': tr('Copie') if job[tr('copy')] else tr('Déplacement'),
                'destination': str(destination), 'destinationUrl': destination.as_uri(),
                'count': len(job[tr('plans')]),
            })
            for event in job.pop('plasma_pending_events', []):
                process.write(event)

        process.started.connect(started)
        process.start()

    def show_transfers(self):
        self.show_jobs(tab='transfers')

    def create_transfers_page(self, parent):
        dialog = QWidget(parent)
        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels([tr('Opération'), tr('État'), tr('Éléments')])
        tree.headerItem().setToolTip(2, tr('Pour les opérations KDE : nombre d’éléments sélectionnés. La progression détaillée et le contenu des dossiers sont suivis par KDE.'))
        tree.setColumnWidth(0, 440)
        tree.setColumnWidth(1, 150)
        layout.addWidget(tree)
        details = QTextBrowser()
        layout.addWidget(details)
        cancel = QPushButton(tr('Arrêter le transfert sélectionné'))
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        stop = QPushButton(tr('Arrêter tous les transferts…'))
        actions.addWidget(stop)
        clear_history = QPushButton(tr('Effacer l’historique terminé'))
        actions.addWidget(clear_history)
        layout.addLayout(actions)
        items = {}

        def selection():
            item = tree.currentItem()
            index = item.data(0, Qt.ItemDataRole.UserRole) if item else None
            return self.transfer_history[index] if index is not None and index < len(self.transfer_history) else None

        def refresh():
            for i, job in enumerate(self.transfer_history):
                if i not in items:
                    item = QTreeWidgetItem(tree)
                    item.setData(0, Qt.ItemDataRole.UserRole, i)
                    items[i] = item
                item = items[i]
                if job.get('native'):
                    target = transfer_url_text(job['destination'])
                    item.setText(0, job['label'] + (tr(' → ') + target if target else ''))
                else:
                    item.setText(0, (tr('Copie') if job[tr('copy')] else tr('Déplacement')) + tr(' → ') + str(job[tr('plans')][0][1].parent))
                item.setText(1, job[tr('state')])
                total = len(job['sources']) if job.get('native') else len(job['plans'])
                item.setText(2, str(total) if job.get('native') else trf('\x1f0\x1f/\x1f1\x1f', job['count'], total))
            job = selection()
            cancel.setEnabled(bool(job and job[tr('state')] in (tr('En attente'), tr('En cours'))))
            stop.setEnabled(bool(self.pending_transfers()))
            terminal = {tr('Interrompu'), tr('À vérifier'), tr('Terminé'), 'Interrompu', 'À vérifier', 'Terminé', 'Interrupted', 'Needs Attention', 'Completed'}
            clear_history.setEnabled(any((j[tr('state')] in terminal and j is not self.active_transfer for j in self.transfer_history)))
            if job:
                if job.get('native'):
                    entries = [transfer_url_text(source) for source in job['sources'][:200]]
                else:
                    entries = [trf('\x1f0\x1f → \x1f1\x1f', a, b) for a, b in job[tr('plans')][:200]]
                details.setPlainText(job['message'] + tr('\n') + tr('\n').join(entries) + tr('\n') + tr('\n').join(job['errors']))
        cancel.clicked.connect(lambda: self.cancel_transfer(selection()) if selection() else None)

        def stop_all():
            if QMessageBox.question(dialog, tr('Arrêter les transferts'), tr('Arrêter tous les transferts, y compris ceux en attente ? Les analyses continueront.'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                for job in self.pending_transfers():
                    self.cancel_transfer(job)
        stop.clicked.connect(stop_all)

        def clear_finished_history():
            if not self.clear_transfer_history():
                return
            tree.clear()
            items.clear()
            details.clear()
            refresh()
        clear_history.clicked.connect(clear_finished_history)
        tree.currentItemChanged.connect(lambda *_: refresh())
        timer = QTimer(dialog)
        timer.timeout.connect(refresh)
        timer.start(250)
        refresh()
        return dialog

    def allow_transfer_close(self):
        if not self.pending_transfers():
            return True
        if self.transfer_quitting:
            return False
        box = QMessageBox(self)
        box.setWindowTitle(tr('Transferts en cours'))
        box.setText(tr('Des opérations de fichiers sont en cours. Que souhaitez-vous faire ?'))
        keep = box.addButton(tr('Continuer en arrière-plan'), QMessageBox.ButtonRole.ActionRole)
        stop = box.addButton(tr('Arrêter les transferts et quitter'), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr('Revenir à Mirivue'), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is keep:
            self.quit_requested = False
            if self.tray is not None and QSystemTrayIcon.isSystemTrayAvailable():
                self.tray.show()
                self.hide()
            else:
                self.showMinimized()
        elif box.clickedButton() is stop:
            self.transfer_quitting = True
            for job in self.pending_transfers():
                self.cancel_transfer(job)
            if not self.active_transfer:
                QTimer.singleShot(0, self.close)
        else:
            self.quit_requested = False
        return False
