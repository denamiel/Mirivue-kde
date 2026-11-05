from .item_presentation import map_file_index
from .i18n import tr
"""KIO transfer history, pane updates and background-window lifetime."""
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QItemSelectionModel, QUrl
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QTextBrowser, QMessageBox, QSystemTrayIcon, QWidget

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
        if operation == 'paste':
            locked.append(target)
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
        finished = [job for job in self.transfer_history if job.get(tr('state')) in terminal]
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


    def create_transfer_footer(self, layout):
        # KIO/Plasma owns progress; the window keeps history and stop controls.
        self.transfer_history = []
        self.transfer_quitting = False

    def update_transfer_footer(self):
        # KIO owns detailed progress; Mirivue retains history and stop controls.
        if hasattr(self, 'update_operations_button_visibility'):
            self.update_operations_button_visibility()
        self.sync_activity_progress_visibility()

    def cancel_transfer(self, job):
        if not job.get('cancellable', True):
            return
        worker = job.get('worker')
        if worker is not None and job['state'] in (tr('En attente'), tr('En cours')):
            job['state'] = tr('Arrêt en cours')
            job['message'] = tr('Annulation demandée pour cette opération.')
            worker.cancel()
            self.update_transfer_footer()

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
                target = transfer_url_text(job['destination'])
                item.setText(0, job['label'] + (tr(' → ') + target if target else ''))
                item.setText(1, job[tr('state')])
                item.setText(2, str(len(job['sources'])))
            job = selection()
            cancel.setEnabled(bool(job and job.get('cancellable', True) and job[tr('state')] in (tr('En attente'), tr('En cours'))))
            stop.setEnabled(bool(self.pending_transfers()))
            terminal = {tr('Interrompu'), tr('À vérifier'), tr('Terminé'), 'Interrompu', 'À vérifier', 'Terminé', 'Interrupted', 'Needs Attention', 'Completed'}
            clear_history.setEnabled(any((j[tr('state')] in terminal for j in self.transfer_history)))
            if job:
                entries = [transfer_url_text(source) for source in job['sources'][:200]]
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
        # Closing the window never cancels queued or running file operations.
        self.quit_requested = False
        if self.tray is not None and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.hide()
        if not getattr(self, '_background_transfer_close_timer', None):
            timer = QTimer(self)
            timer.setInterval(250)
            timer.timeout.connect(self.finish_background_transfer_close)
            self._background_transfer_close_timer = timer
        self._background_transfer_close_timer.start()
        return False

    def finish_background_transfer_close(self):
        timer = self._background_transfer_close_timer
        if self.isVisible() or self.closing:
            timer.stop()
            return
        if self.pending_transfers():
            return
        timer.stop()
        # Bypass close-to-tray only after the last operation has completed.
        self.quit_requested = True
        self.close()
