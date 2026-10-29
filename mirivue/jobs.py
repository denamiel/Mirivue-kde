from .i18n import tr, trf, configured_language
tr('Serial user operations, independent from directory navigation (GUI-thread state).')
from pathlib import Path
import hashlib
from collections import deque
from PySide6.QtCore import Qt, QTimer
import time
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QProgressBar, QHBoxLayout, QVBoxLayout, QDialog, QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QTextBrowser, QSizePolicy, QToolButton, QStyle, QWidget, QTabWidget
from .extensions import fingerprint
from .metadata import quantity
from .pane_status import summarize_items
from . import library
from .iconography import themed_icon
LABELS = {tr('duration'): tr('Durée totale des dossiers'), tr('duplicates'): tr('Recherche de doublons')}

class JobMixin:

    def init_jobs(self):
        self.job_queue = []
        self.active_job = None
        self.job_history = []
        self.result_cache = {}
        from .responsive import OrderedPaths
        self._dirty_paths = OrderedPaths()
        self._results_dirty = False
        self._receiving_result = False
        self._claims = {}
        self._job_refresh = QTimer(self)
        self._job_refresh.setSingleShot(True)
        self._job_refresh.setInterval(120)
        self._job_refresh.timeout.connect(self.flush_job_updates)
        self._checkpoint = QTimer(self)
        self._checkpoint.setSingleShot(True)
        self._checkpoint.setInterval(750)
        self._checkpoint.timeout.connect(self.flush_checkpoint)

    def jobs_busy(self):
        return bool(self.active_job or self.job_queue)

    def result_rows(self):
        models = [p.model for p in self.panes] if hasattr(self, tr('panes')) else [self.model]
        visible = list({r.path: r for model in models for r in model.rows}.values())
        paths = {r.path for r in visible}
        return visible + [r for p, r in self.result_cache.items() if p not in paths]

    def update_selection_info(self, rows=None, pane=None):
        pane = pane or getattr(self, tr('bound_pane'), None)
        if pane is None or not hasattr(pane, tr('selection_label')):
            return
        if rows is None:
            view = pane.content_stack.currentWidget()
            if view is pane.table:
                indexes = view.selectionModel().selectedRows(0)
            else:
                indexes = [index for index in view.selectionModel().selectedIndexes() if index.column() == 0]
            rows = []
            seen = set()
            for index in indexes:
                source_index = pane.proxy.mapToSource(index)
                row_number = source_index.row()
                if row_number not in seen and 0 <= row_number < len(pane.model.rows):
                    seen.add(row_number)
                    rows.append(pane.model.rows[row_number])
        label = summarize_items(
            rows,
            tr,
            lambda size: quantity(size, [tr('o'), tr('Kio'), tr('Mio'), tr('Gio'), tr('Tio')], 1024),
            selected=True,
        )
        pane.selection_label.set_full_text(label)
        pane.selection_label.setToolTip(str(rows[0].path) if len(rows) == 1 else '')

    def path_menu(self, button, path, pos):
        pane = next((p for p in self.panes if p.crumbs.isAncestorOf(button)), self.bound_pane)
        self.pane_path_menu(pane, button, pos, path)

    def show_shortcuts(self):
        from .keyboard import show_shortcuts
        show_shortcuts(self)

    def show_features(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Guide de Mirivue'))
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        guide = 'fonctionnalites_en.html' if configured_language() == 'en' else 'fonctionnalites.html'
        browser.setHtml((Path(__file__).parent / guide).read_text())
        layout.addWidget(browser)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def create_job_footer(self, layout):
        footer = QVBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(2)
        self.job_footer = footer
        self.job_label = QLabel(tr('Aucune tâche en cours'))
        self.job_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.job_label.setMinimumWidth(0)
        self.job_label.setTextFormat(Qt.TextFormat.PlainText)
        self.job_progress = QProgressBar()
        self.job_progress.setMinimumWidth(0)
        self.job_progress.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.job_progress.setMaximumWidth(360)
        self.job_progress.setRange(0, 1)
        self.job_progress.setValue(0)
        self.job_button = QToolButton(self.operations_sidebar_slot)
        self.job_button.setAutoRaise(True)
        self.job_button.setIcon(themed_icon(tr('view-more-symbolic'), self, QStyle.StandardPixmap.SP_TitleBarMenuButton))
        self.job_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.job_button.setToolTip(tr('Afficher les opérations, leur progression et leur historique.'))
        self.job_button.setAccessibleName(tr('Opérations, messages et historique'))
        self.job_button.clicked.connect(self.show_jobs)
        footer.addWidget(self.job_label)
        footer.addWidget(self.job_progress)
        self.operations_sidebar_slot.layout().addWidget(self.job_button, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.operations_sidebar_slot.setFixedHeight(max(30, self.job_button.sizeHint().height() + 2))
        self.activity_fallback_button = QToolButton(self.right_toolbar_group)
        self.activity_fallback_button.setAutoRaise(True)
        self.activity_fallback_button.setIcon(themed_icon(tr('view-process-all'), self, QStyle.StandardPixmap.SP_BrowserReload))
        self.activity_fallback_button.setToolTip(tr('Afficher les opérations, leur progression et leur historique.'))
        self.activity_fallback_button.setAccessibleName(tr('Opérations en cours'))
        self.activity_fallback_button.clicked.connect(self.show_jobs)
        self.activity_fallback_button.hide()
        self.right_toolbar_layout.addWidget(self.activity_fallback_button)
        for widget in (self.job_label, self.job_progress):
            widget.hide()
        layout.addLayout(footer)

    def update_job_footer(self):
        if not self._job_refresh.isActive():
            self._job_refresh.start()

    def flush_job_updates(self):
        self._job_refresh.stop()
        if not hasattr(self, tr('job_label')):
            return
        self.render_job_footer()
        dirty = set(list(self._dirty_paths)[:128])
        for path in dirty:
            self._dirty_paths.pop(path, None)
        models = [p.model for p in self.panes] if hasattr(self, tr('panes')) else [self.model]
        for model in models:
            indices = []
            for i, row in enumerate(model.rows):
                if row.path not in dirty:
                    continue
                base = row.values[10].split(tr(' • '))[0]
                row.values[10] = row.sort_values[10] = base + (tr(' • ') + row.validation_status if row.validation_status else '') + (trf(' • Doublon groupe \x1f0\x1f', row.duplicate_group) if row.duplicate_group else '')
                indices.append(i)
            groups = []
            for i in indices:
                if groups and i == groups[-1][1] + 1:
                    groups[-1][1] = i
                else:
                    groups.append([i, i])
            for first, last in groups:
                model.dataChanged.emit(model.index(first, 0), model.index(last, model.columnCount() - 1), [Qt.ItemDataRole.ForegroundRole])
                model.dataChanged.emit(model.index(first, 1), model.index(last, model.columnCount() - 1), [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole, Qt.ItemDataRole.ToolTipRole])
        if dirty:
            errors = sum((bool(r.error or r.bitrate_error or r.validation_error) for r in self.model.rows))
            self.summary.setText(trf('\x1f0\x1f affichée(s) / \x1f1\x1f élément(s) • \x1f2\x1f erreur(s)', self.proxy.rowCount(), len(self.model.rows), errors))
            self.errors.setEnabled(bool(errors or self.notices))
            self.errors.setVisible(bool(errors or self.notices))
            self.errors_slot.setVisible(bool(errors or self.notices))
        for pane in getattr(self, tr('panes'), []):
            pane.content_stack.currentWidget().viewport().update()
        if self._dirty_paths:
            self._job_refresh.start()

    def schedule_checkpoint(self):
        if not self._checkpoint.isActive():
            self._checkpoint.start()

    def flush_checkpoint(self):
        self._checkpoint.stop()
        if self._results_dirty:
            self._results_dirty = False
            library.write(self.settings, tr('results'), self.saved_results)
        self.remember_jobs()

    def report_store_error(self, message):
        self.notices.append(tr('Sauvegarde locale : ') + message)
        self.errors.setEnabled(True)
        self.errors.show()
        self.errors_slot.show()
        self.show_activity_message(tr('Résultats non sauvegardés : ') + message)

    def result_entries(self, path):
        row = self.result_cache.get(path)
        if row is None:
            row = next((r for r in self.result_rows() if r.path == path), None)
        return [] if row is None else [(0, row)]

    def render_job_footer(self):
        job = self.active_job
        if job and job.get(tr('_preparing')):
            self.job_label.setText(trf('Préparation de la tâche… \x1f0\x1f fichiers — \x1f1\x1f demande(s) en attente', len(job['rows']), len(self.job_queue)))
            self.job_progress.setRange(0, 0)
        elif job:
            self.job_progress.setFormat(tr('%p %'))
            self.job_label.setText(trf('\x1f0\x1f — \x1f1\x1f/\x1f2\x1f fichiers — \x1f3\x1f en attente', job['label'], len(job['done']), len(job['rows']), len(self.job_queue)))
            self.job_label.setToolTip(job.get(tr('message'), ''))
            self.job_progress.setRange(0, max(1, len(job[tr('rows')])))
            self.job_progress.setValue(len(job[tr('done')]))
            if job[tr('kind')] == tr('duration'):
                current = job.get('_duration_current', 0)
                total = job.get('_duration_total', 0)
                found = job.get('_duration_found', 0)
                if total:
                    self.job_label.setText(trf('Durée totale des dossiers — \x1f0\x1f/\x1f1\x1f médias — \x1f2\x1f/\x1f3\x1f dossiers', current, total, len(job[tr('done')]), len(job[tr('rows')])))
                    self.job_progress.setRange(0, total)
                    self.job_progress.setValue(current)
                    self.job_progress.setFormat(tr('%v/%m médias'))
                else:
                    self.job_label.setText(trf('Inventaire du dossier — \x1f0\x1f média(s) trouvé(s)', found))
                    self.job_progress.setRange(0, 0)
                    self.job_progress.setFormat(tr('Inventaire…'))
            elif len(job[tr('done')]) < len(job[tr('rows')]):
                self.job_progress.setRange(0, 0)
                self.job_progress.setFormat(tr('Traitement en cours'))
        elif self.job_queue:
            self.job_label.setText(tr('Préparation de la tâche…'))
            self.job_progress.setRange(0, 0)
        else:
            self.job_label.setText(tr('Aucune tâche en cours'))
            self.job_progress.setRange(0, 1)
            self.job_progress.setValue(0)
        busy = self.jobs_busy()
        self.sync_activity_progress_visibility()
        if hasattr(self, tr('stop_analyses_button')):
            self.stop_analyses_button.setEnabled(busy)
            self.stop_analyses_button.setVisible(busy)
        if getattr(self, tr('_last_jobs_busy'), None) != busy and hasattr(self, tr('delete_button')):
            self._last_jobs_busy = busy
            self.update_delete_button()

    def update_operations_button_visibility(self):
        """Keep one compact entry point for analyses and file transfers."""
        if not hasattr(self, 'job_button'):
            return
        self.update_activity_entry_points()

    def job_item_started(self, job, path):
        job[tr('started')].add(path)
        job[tr('sample')] = 0
        if job[tr('kind')] == tr('duration'):
            job['_duration_found'] = 0
            job['_duration_current'] = 0
            job['_duration_total'] = 0
        self.update_job_footer()

    def duration_inventory_progress(self, job, path, found, current_path):
        if self.active_job is not job:
            return
        job['_duration_found'] = found
        job[tr('message')] = tr('Inventaire : ') + current_path
        self.update_job_footer()

    def duration_scan_progress(self, job, path, current, total, current_path):
        if self.active_job is not job:
            return
        job['_duration_current'] = current
        job['_duration_total'] = total
        job[tr('message')] = current_path
        self.update_job_footer()

    def enqueue_analysis(self, kind, paths, samples=5):
        if self.closing:
            return
        if kind not in LABELS:
            return
        if self.transfers_locked(paths) or (hasattr(self, tr('media_locked')) and self.media_locked(paths)):
            QMessageBox.information(self, tr('Transfert en cours'), tr('Attendez la fin du transfert de ces éléments avant de les analyser.'))
            return
        required = {tr('duration'): [tr('mediainfo'), tr('ffprobe')]}.get(kind, [])
        if required and (not self.ensure_components(required)):
            return
        requested = set(paths)
        rows = [r for r in self.model.rows if r.path in requested]
        if not rows:
            QMessageBox.information(self, tr('Opération'), tr('Aucun fichier vidéo à traiter dans la sélection.'))
            return
        job = {tr('kind'): kind, tr('samples'): samples, tr('label'): LABELS[kind], tr('rows'): rows, tr('done'): set(), tr('errors'): [], tr('paths'): {r.path for r in rows}, tr('state'): tr('En attente'), tr('message'): '', tr('started'): set(), tr('date'): library.stamp()}
        policy = (kind, samples)
        if kind == tr('duplicates'):
            if any((j[tr('kind')] == kind and j[tr('paths')] == job[tr('paths')] for j in ([self.active_job] if self.active_job else []) + self.job_queue)):
                return
            policy = (*policy, frozenset(job[tr('paths')]))
        else:
            rows = [r for r in rows if (policy, r.path) not in self._claims]
            if not rows:
                self.show_activity_message(tr('Cette analyse est déjà en cours ou en attente pour ces fichiers.'), 6000)
                return
            job[tr('rows')] = rows
            job[tr('paths')] = {r.path for r in rows}
        job[tr('_policy')] = policy
        job[tr('_ready')] = False
        job[tr('_encoded')] = {}
        for row in rows:
            self._claims[policy, row.path] = job
        self.job_queue.append(job)
        self.job_history.append(job)
        self.job_label.setText(tr('Préparation de la tâche…'))
        self.stop_analyses_button.setEnabled(True)
        cursor = iter(rows)

        def prepare_batch():
            if not any((j is job for j in self.job_queue)):
                return
            deadline = time.monotonic() + 0.006
            while time.monotonic() < deadline:
                try:
                    row = next(cursor)
                except StopIteration:
                    job[tr('_ready')] = True
                    self.remember_jobs()
                    self.start_next_job()
                    self.update_job_footer()
                    return
                self.result_cache[row.path] = row
                job[tr('_encoded')][row.path] = library.encode_row(row)
            QTimer.singleShot(1, prepare_batch)
        if len(rows) <= 64:
            prepare_batch()
        else:
            QTimer.singleShot(0, prepare_batch)
        self.update_job_footer()

    def start_next_job(self):
        if self.active_job or not self.job_queue or self.closing:
            return
        if not self.job_queue[0].get(tr('_ready'), True):
            return
        from .responsive import PrepareWorker
        job = self.job_queue.pop(0)
        self.active_job = job
        job[tr('state')] = tr('En cours')
        job[tr('_preparing')] = True
        worker = PrepareWorker(job[tr('rows')])
        job[tr('worker')] = worker

        def prepared():
            if worker.cancelled or self.closing:
                self.finish_job()
                return
            job[tr('_locks')] = (worker.lock_paths, worker.lock_parents)
            for row in worker.valid:
                encoded = job.get(tr('_encoded'), {}).get(row.path)
                if encoded is not None and encoded.get(tr('file_signature')) is None:
                    job[tr('_encoded')][row.path] = dict(encoded, file_signature=row.file_signature)
            valid = worker.valid
            errors = iter(worker.errors)

            def apply_errors():
                if worker.cancelled or self.closing:
                    self.finish_job()
                    return
                for _ in range(32):
                    try:
                        path, error = next(errors)
                    except StopIteration:
                        job[tr('_preparing')] = False
                        worker.deleteLater()
                        self.launch_prepared_job(job, valid)
                        return
                    job[tr('errors')].append(trf('\x1f0\x1f : \x1f1\x1f', path, error))
                    job[tr('done')].add(path)
                    self._receiving_result = True
                    try:
                        handler = {tr('duration'): self.duration_failure, tr('duplicates'): self.deep_failure}[job[tr('kind')]]
                        handler(path, error)
                        row = self.result_cache.get(path)
                        if row is not None:
                            self.save_result(row)
                            job[tr('_encoded')][path] = self.saved_results[str(path)]
                    finally:
                        self._receiving_result = False
                    self._dirty_paths.add(path)
                self.update_job_footer()
                QTimer.singleShot(1, apply_errors)
            apply_errors()
        worker.finished.connect(prepared)
        self.start_runtime_worker(worker, tr('Préparation de la tâche'))
        self.update_job_footer()

    def launch_prepared_job(self, job, valid):
        from .app import DuplicateScanner
        paths = [r.path for r in valid]
        kind = job[tr('kind')]
        from .analysis_extra import DurationScanner
        if kind == tr('duration'):
            worker = DurationScanner(paths)
        elif kind == tr('duplicates'):
            worker = DuplicateScanner(paths, embed=False)
        else:
            return
        job[tr('worker')] = worker
        worker.item_started.connect(lambda path: self.job_item_started(job, path))
        job[tr('_events')] = deque()
        job[tr('_draining')] = False

        def drain():
            deadline = time.monotonic() + 0.006
            while job[tr('_events')] and time.monotonic() < deadline:
                callback, path, value = job[tr('_events')].popleft()
                callback(path, value)
            if job[tr('_events')]:
                QTimer.singleShot(1, drain)
            else:
                job[tr('_draining')] = False

        def connect(signal, handler, terminal=True, error=False):

            def apply_result(path, value):
                self._receiving_result = True
                try:
                    handler(path, value)
                finally:
                    self._receiving_result = False
                self._dirty_paths.add(path)
                if error and value:
                    job[tr('errors')].append(trf('\x1f0\x1f : \x1f1\x1f', path, value))
                if terminal:
                    job[tr('done')].add(path)
                    job[tr('sample')] = 0
                    row = self.result_cache.get(path)
                    if row is not None:
                        row.analysis_dates[kind] = library.stamp()
                        self._receiving_result = True
                        try:
                            self.save_result(row)
                        finally:
                            self._receiving_result = False
                        job.setdefault(tr('_encoded'), {})[path] = self.saved_results[str(path)]
                    self.schedule_checkpoint()
                self.update_job_footer()

            def receive(path, value):
                job[tr('_events')].append((apply_result, path, value))
                if not job[tr('_draining')]:
                    job[tr('_draining')] = True
                    QTimer.singleShot(0, drain)
            signal.connect(receive)
        if kind == tr('duration'):
            connect(worker.duration_ready, self.duration_result)
            connect(worker.failure, self.duration_failure, error=True)
            worker.inventory_progress.connect(lambda path, found, current_path: self.duration_inventory_progress(job, path, found, current_path))
            worker.scan_progress.connect(lambda path, current, total, current_path: self.duration_scan_progress(job, path, current, total, current_path))
        elif kind == tr('duplicates'):
            worker.groups_found.connect(self.duplicates_found)
            worker.cleanup_warning.connect(job[tr('errors')].append)
        worker.current.connect(lambda message: self.job_message(job, message))
        worker.finished.connect(self.finish_job)
        self.update_job_footer()
        self.start_runtime_worker(worker, tr('Tâche — ') + str(kind))

    def job_message(self, job, message):
        job[tr('message')] = message
        self.update_job_footer()

    def finish_job(self):
        job = self.active_job
        if not job:
            return
        if getattr(self, tr('_applying_results'), False) or job.get(tr('_draining'), False):
            QTimer.singleShot(10, self.finish_job)
            return
        worker = job[tr('worker')]
        job[tr('state')] = tr('Annulée') if worker.cancelled else tr('Terminée avec erreurs') if job[tr('errors')] else tr('Terminée')
        if job[tr('kind')] == tr('duplicates') and (not worker.cancelled):
            job[tr('done')] = set(job[tr('paths')])
        job.pop(tr('worker'))
        worker.deleteLater()
        self.active_job = None
        self.release_claims(job)
        self.flush_job_updates()
        self.flush_checkpoint()
        self.saved_history.append(library.job_data(job))
        self.saved_history = self.saved_history[-500:]
        library.write(self.settings, tr('history'), self.saved_history)
        self.remember_jobs()
        self.update_job_footer()
        if self.closing:
            self.close()
        else:
            QTimer.singleShot(0, self.start_next_job)

    def release_claims(self, job):
        policy = job.get(tr('_policy'))
        for path in job[tr('paths')]:
            if self._claims.get((policy, path)) is job:
                self._claims.pop((policy, path), None)

    def cancel_job(self, job):
        if job is self.active_job:
            job[tr('state')] = tr('Annulation…')
            job[tr('worker')].cancel()
        elif any((j is job for j in self.job_queue)):
            self.job_queue = [j for j in self.job_queue if j is not job]
            job[tr('state')] = tr('Annulée')
            self.release_claims(job)
        self.remember_jobs()
        self.update_job_footer()
        if not self.active_job:
            QTimer.singleShot(0, self.start_next_job)

    def cancel_all_jobs(self):
        for job in list(self.job_queue):
            self.cancel_job(job)
        if self.active_job:
            self.cancel_job(self.active_job)

    def show_jobs(self, checked=False, tab=None):
        dialog = getattr(self, '_operations_dialog', None)
        if dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle(tr('Opérations en cours et historique'))
            dialog.resize(950, 480)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            layout = QVBoxLayout(dialog)
            tabs = QTabWidget(dialog)
            tabs.setObjectName('operationsTabs')
            layout.addWidget(tabs)
            tabs.addTab(self.create_transfers_page(dialog), tr('Transferts'))
            tabs.addTab(self.create_analyses_page(dialog), tr('Analyses'))
            dialog.tabs = tabs
            self._operations_dialog = dialog
            dialog.destroyed.connect(lambda: setattr(self, '_operations_dialog', None))
            if self.jobs_busy() and not self.pending_transfers():
                tabs.setCurrentIndex(1)
        if tab is not None:
            dialog.tabs.setCurrentIndex(0 if tab == 'transfers' else 1)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def create_analyses_page(self, parent):
        dialog = QWidget(parent)
        layout = QVBoxLayout(dialog)
        running = QLabel()
        running.setWordWrap(True)
        layout.addWidget(running)
        tree = QTreeWidget()
        tree.setHeaderLabels([tr('Analyse'), tr('État'), tr('Fichiers'), tr('Date')])
        tree.setColumnWidth(0, 260)
        tree.setColumnWidth(1, 220)
        layout.addWidget(tree)
        tree.setVisible(bool(self.job_history))
        details = QTextBrowser()
        details.setMaximumHeight(130)
        details.hide()
        layout.addWidget(details)
        cancel = QPushButton(tr('Arrêter l’analyse sélectionnée'))
        clear_history = QPushButton(tr('Effacer l’historique terminé'))
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(clear_history)
        layout.addLayout(actions)
        items = {}

        def selected():
            item = tree.currentItem()
            index = item.data(0, Qt.ItemDataRole.UserRole) if item else None
            return index if index is not None and index < len(self.job_history) else None

        def refresh():
            background = self.runtime_tasks.descriptions()
            running.setText(
                tr('Tâches en arrière-plan : ') + tr(', ').join(background)
                if background else tr('Aucune tâche en arrière-plan.')
            )
            for i, job in enumerate(self.job_history):
                if i not in items:
                    items[i] = QTreeWidgetItem(tree)
                    items[i].setData(0, Qt.ItemDataRole.UserRole, i)
                item = items[i]
                item.setText(0, job[tr('label')])
                item.setText(1, job[tr('state')])
                item.setText(2, trf('\x1f0\x1f/\x1f1\x1f', len(job['done']), len(job['rows'])))
                item.setText(3, job.get(tr('date'), ''))
            tree.setVisible(bool(self.job_history))
            i = selected()
            cancel.setEnabled(i is not None and self.job_history[i][tr('state')] in (tr('En attente'), tr('En cours')))
            clear_history.setEnabled(any((self.job_is_finished(job) for job in self.job_history)))
            cancel.setVisible(bool(self.job_history))
            clear_history.setVisible(bool(self.job_history))
            details.setVisible(i is not None)
            if i is not None:
                job = self.job_history[i]
                details.setPlainText(job[tr('message')] + tr('\n') + tr('\n').join((str(r.path) for r in job[tr('rows')][:200])) + (tr('\n… liste limitée à 200 fichiers.') if len(job[tr('rows')]) > 200 else '') + tr('\n') + tr('\n').join(job[tr('errors')][:200]))
            else:
                details.clear()
        cancel.clicked.connect(lambda: self.cancel_job(self.job_history[selected()]) if selected() is not None else None)

        def clear_finished_history():
            if not self.clear_job_history():
                return
            tree.clear()
            items.clear()
            details.clear()
            refresh()
        clear_history.clicked.connect(clear_finished_history)
        tree.currentItemChanged.connect(lambda *_: refresh())
        timer = QTimer(dialog)
        timer.timeout.connect(refresh)
        timer.start(300)
        refresh()
        return dialog

    def clear_job_history(self):
        terminal = {tr('Terminée'), tr('Terminée avec erreurs'), tr('Annulée'), 'Terminée', 'Terminée avec erreurs', 'Annulée', 'Completed', 'Completed with errors', 'Cancelled'}
        finished = [job for job in self.job_history if job.get(tr('state')) in terminal and job is not self.active_job and not any((job is queued for queued in self.job_queue))]
        if not finished:
            return 0
        self.job_history = [job for job in self.job_history if not any((job is done for done in finished))]
        self.saved_history = [data for data in self.saved_history if data.get(tr('state')) not in terminal]
        library.write(self.settings, tr('history'), self.saved_history)
        self.update_job_footer()
        return len(finished)

    def job_is_finished(self, job):
        terminal = {tr('Terminée'), tr('Terminée avec erreurs'), tr('Annulée'), 'Terminée', 'Terminée avec erreurs', 'Annulée', 'Completed', 'Completed with errors', 'Cancelled'}
        return job.get(tr('state')) in terminal and job is not self.active_job and not any((job is queued for queued in self.job_queue))

    def job_is_live(self, job):
        return job is self.active_job or any((job is queued for queued in self.job_queue)) or job.get(tr('state')) in (tr('En attente'), tr('En cours'), tr('Annulation…'), tr('Arrêt en cours'))
