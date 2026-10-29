from .i18n import tr, trf
from pathlib import Path
from PySide6.QtCore import QTimer, QByteArray
from PySide6.QtWidgets import QMessageBox, QInputDialog, QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout, QLabel
from . import library
from .extensions import fingerprint

class EnhancementMixin:

    def load_library(self):
        self.saved_results = library.read(self.settings, tr('results'), {})
        if not isinstance(self.saved_results, dict):
            self.saved_results = {}
        self.saved_history = library.read(self.settings, tr('history'), [])
        self.resume_data = library.read(self.settings, tr('pending'), [])
        if not isinstance(self.resume_data, list):
            self.resume_data = []
        compatible_pending = []
        for data in self.resume_data:
            try:
                library.restore_job(data)
                compatible_pending.append(data)
            except (KeyError, TypeError, ValueError):
                pass
        if len(compatible_pending) != len(self.resume_data):
            self.resume_data = compatible_pending
            library.write(self.settings, tr('pending'), self.resume_data)
        compatible_history = []
        for data in self.saved_history if isinstance(self.saved_history, list) else []:
            try:
                restored = library.restore_job(data)
                compatible_history.append(data)
                self.job_history.append(restored)
            except (KeyError, TypeError, ValueError):
                pass
        if compatible_history != self.saved_history:
            self.saved_history = compatible_history
            library.write(self.settings, tr('history'), self.saved_history)
        for group in library.read(self.settings, tr('duplicates'), []):
            try:
                files = [(Path(p), tuple(sig)) for p, sig in group[tr('files')]]
                if len(files) > 1 and all((fingerprint(p) == sig for p, sig in files)):
                    self.duplicate_groups.append(dict(digest=group[tr('digest')], files=files))
            except (OSError, KeyError, TypeError, ValueError):
                pass
        self.resume_action.setEnabled(bool(self.resume_data))
        if self.resume_data:
            self.resume_button.show()
            self.resume_button.setText(trf('Reprendre \x1f0\x1f tâche(s) interrompue(s)…', len(self.resume_data)))
        self.update_activity_entry_points()

    def save_result(self, row):
        self.result_cache[row.path] = row
        self.saved_results[str(row.path)] = library.encode_row(row)
        if getattr(self, tr('_receiving_result'), False):
            self._results_dirty = True
        else:
            library.write(self.settings, tr('results'), self.saved_results)

    def remember_jobs(self):
        if not hasattr(self, tr('saved_results')) or self.closing:
            return
        if getattr(self, tr('_receiving_result'), False):
            self.schedule_checkpoint()
            return
        jobs = ([self.active_job] if self.active_job else []) + self.job_queue
        library.write(self.settings, tr('pending'), self.resume_data + [library.job_data(j) for j in jobs if j.get(tr('_ready'), True)])

    def resume_operations(self):
        pending = []
        for data in self.resume_data:
            try:
                job = library.restore_job(data)
                job[tr('rows')] = [r for r in job[tr('rows')] if r.path not in job[tr('done')]]
                job.update(done=set(), started=set(), errors=[], state=tr('En attente'), message=tr('Reprise après interruption'))
                if job[tr('kind')] == tr('duplicates'):
                    job[tr('rows')] = [library.decode_row(r) for r in data[tr('rows')]]
                job[tr('paths')] = {r.path for r in job[tr('rows')]}
                if job[tr('rows')]:
                    pending.append(job)
            except (KeyError, TypeError, ValueError):
                pass
        count = sum((len(j[tr('rows')]) for j in pending))
        if QMessageBox.question(self, tr('Reprendre les tâches'), trf('Reprendre \x1f0\x1f tâche(s), concernant \x1f1\x1f élément(s) ?', len(pending), count)) != QMessageBox.StandardButton.Yes:
            return
        for job in pending:
            policy = (job[tr('kind')], job[tr('samples')])
            if job[tr('kind')] == tr('duplicates'):
                policy = (*policy, frozenset(job[tr('paths')]))
            job[tr('_policy')] = policy
            for path in job[tr('paths')]:
                self._claims[policy, path] = job
            self.job_queue.append(job)
            self.job_history.append(job)
            for row in job[tr('rows')]:
                self.result_cache[row.path] = row
        self.resume_data = []
        self.resume_button.hide()
        self.resume_action.setEnabled(False)
        self.update_activity_entry_points()
        self.remember_jobs()
        self.start_next_job()
        self.update_job_footer()

    def discard_pending(self):
        self.resume_data = []
        library.write(self.settings, tr('pending'), [])
        self.resume_button.hide()
        self.resume_action.setEnabled(False)
        self.update_activity_entry_points()
        self.remember_jobs()

    def paths_locked(self, paths):
        return self.movement_locked(paths)

    def selection_locked(self):
        return self.paths_locked([self.row(i).path for i in self.selected_indexes()])




    def apply_column_profile(self, columns):
        for c in range(self.model.columnCount()):
            self.table.setColumnHidden(c, c in (12, 13) or c not in columns)
        header = self.table.horizontalHeader()
        for pos, c in enumerate(columns):
            header.moveSection(header.visualIndex(c), pos)
        self.table.setColumnWidth(10, 240)
        self.sync_columns_menu()
        self.schedule_pane_column_save(self.bound_pane)

    def save_column_profile(self):
        name, ok = QInputDialog.getText(self, tr('Configuration de colonnes'), tr('Nom de votre configuration :'))
        if ok and name.strip():
            profiles = library.read(self.settings, tr('column_profiles'), {})
            profiles[name.strip()] = bytes(self.table.horizontalHeader().saveState().toBase64()).decode()
            library.write(self.settings, tr('column_profiles'), profiles)
            self.refresh_profiles()

    def refresh_profiles(self):
        self.custom_profiles.clear()
        for name, state in library.read(self.settings, tr('column_profiles'), {}).items():
            self.custom_profiles.addAction(name, lambda checked=False, s=state: self.table.horizontalHeader().restoreState(QByteArray.fromBase64(s.encode())))
