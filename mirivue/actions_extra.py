from .i18n import tr, trf
from .iconography import themed_icon
from PySide6.QtWidgets import QStyle
tr('User-visible analysis policy, safe MKV fallback and explicit dependency setup.')
from pathlib import Path
import shutil
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QMenu, QMessageBox, QFileDialog, QDialog, QVBoxLayout, QLabel, QProgressBar
from . import library
from .platform_services import services
from .metadata import duration
from .movement import MoveDialog
from .remux import RemuxWorker

def component_path(name):
    if name == tr('qt-multimedia'):
        try:
            from PySide6 import QtMultimedia, QtMultimediaWidgets
            return tr('PySide6.QtMultimedia')
        except ImportError:
            return None
    return services.tool_path(name)

class ExtraActionsMixin:

    def init_extra_actions(self, organize_menu, operations_menu):
        from PySide6.QtGui import QAction
        self.folder_duration_action = QAction(tr('Calculer la durée totale des dossiers sélectionnés'), self)
        self.folder_duration_action.triggered.connect(self.start_folder_duration)
        self.folder_duration_action.setToolTip(tr('Additionne la durée des médias contenus dans les dossiers sélectionnés.'))
        organize_menu.addAction(self.folder_duration_action)
        self.stop_analyses_button = QPushButton(tr('Arrêter'))
        self.stop_analyses_button.setIcon(themed_icon(tr('process-stop'), self, QStyle.StandardPixmap.SP_MediaStop))
        self.stop_analyses_button.setToolTip(tr('Arrêter la tâche en cours ou toutes les tâches ; les copies et déplacements continuent.'))
        menu = QMenu(self)
        current = menu.addAction(tr('Arrêter l’analyse en cours'), lambda: self.cancel_job(self.active_job) if self.active_job else None)
        menu.addAction(tr('Arrêter toutes les analyses…'), self.stop_all_analyses)
        menu.aboutToShow.connect(lambda: current.setEnabled(bool(self.active_job)))
        self.stop_analyses_button.setMenu(menu)
        self.stop_analyses_button.setEnabled(False)
        self.stop_analyses_button.hide()
        self.job_footer.insertWidget(self.job_footer.indexOf(self.job_button), self.stop_analyses_button)
        self.inline_label = QLabel()
        self.inline_label.setTextFormat(Qt.TextFormat.PlainText)
        self.inline_label.setMinimumWidth(150)
        self.inline_label.setMaximumWidth(360)
        self.inline_progress = QProgressBar()
        self.inline_progress.setMinimumWidth(100)
        self.inline_progress.setMaximumWidth(260)
        self.inline_stop = QPushButton(tr('Arrêter'))
        self.inline_stop.setIcon(themed_icon(tr('process-stop'), self, QStyle.StandardPixmap.SP_MediaStop))
        self.inline_stop.clicked.connect(self.stop_inline_operation)
        for widget in (self.inline_label, self.inline_progress, self.inline_stop):
            widget.hide()
        index = self.job_footer.indexOf(self.job_button)
        for widget in (self.inline_label, self.inline_progress, self.inline_stop):
            self.job_footer.insertWidget(index, widget)
            index += 1
        self._inline_operation = None
        self.stop_all_analyses_action = operations_menu.addAction(tr('Arrêter toutes les analyses…'), self.stop_all_analyses)

    def begin_inline_operation(self, worker, title):
        if self._inline_operation is not None:
            return False
        self._inline_operation = worker
        self.inline_label.setText(title + tr(' — préparation…'))
        self.inline_progress.setRange(0, 0)
        self.inline_progress.setFormat(tr('Traitement en cours'))
        self.inline_label.show()
        self.inline_progress.show()
        self.inline_stop.show()
        return True

    def update_inline_operation(self, message, done=None, total=None):
        if self._inline_operation is None:
            return
        self.inline_label.setText(str(message))
        if done is None or total is None or total <= 0:
            self.inline_progress.setRange(0, 0)
            self.inline_progress.setFormat(tr('Traitement en cours'))
        else:
            self.inline_progress.setRange(0, total)
            self.inline_progress.setValue(done)
            self.inline_progress.setFormat(tr('%p %'))

    def stop_inline_operation(self):
        worker = self._inline_operation
        if worker is None:
            return
        self.inline_stop.setEnabled(False)
        self.inline_label.setText(tr('Arrêt après sécurisation du fichier…'))
        worker.requestInterruption()

    def finish_inline_operation(self, worker):
        if self._inline_operation is not worker:
            return
        self._inline_operation = None
        for widget in (self.inline_label, self.inline_progress, self.inline_stop):
            widget.hide()
        self.inline_stop.setEnabled(True)

    def make_action(self, title, callback):
        from PySide6.QtGui import QAction
        action = QAction(title, self)
        action.triggered.connect(callback)
        return action

    def stop_all_analyses(self):
        if not self.jobs_busy():
            return
        if QMessageBox.question(self, tr('Arrêter les tâches'), trf('Arrêter la tâche en cours et retirer \x1f0\x1f demande(s) en attente ?\nLes résultats terminés restent conservés. Les copies et déplacements continuent.', len(self.job_queue)), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.cancel_all_jobs()

    def start_folder_duration(self):
        paths = [self.row(i).path for i in self.selected_indexes() if self.row(i).is_dir]
        if not paths:
            QMessageBox.information(self, tr('Durée totale'), tr('Sélectionnez un ou plusieurs dossiers. Les vidéos, sons et images des sous-dossiers seront comptés ; les durées audio et vidéo seront additionnées.'))
            return
        self.table.setColumnHidden(2, False)
        self.enqueue_analysis(tr('duration'), paths)

    def duration_result(self, path, result):
        total, count, errors = result[:3]
        counts = result[3] if len(result) > 3 else {}
        for _, row in self.result_entries(path):
            if row.path == path:
                row.total_duration = total
                row.media_counts = counts
                from .media import sync_columns
                sync_columns(row)
                row.duration_note = trf('\x1f0\x1f média(s) audio/vidéo — calcul du \x1f1\x1f', count, library.stamp()) + (tr(' — résultat partiel :\n') + tr('\n').join(errors) if errors else '')
                row.values[2] = duration(total)
                row.sort_values[2] = total
                row.values[15] = duration(total)
                row.sort_values[15] = total
                if errors and self.active_job:
                    self.active_job[tr('errors')].extend(errors)
                break
        self.repaint_panes()

    def duration_failure(self, path, error):
        for _, row in self.result_entries(path):
            if row.path == path:
                row.total_duration = None
                row.duration_note = str(error)
                row.values[2] = ''
                row.sort_values[2] = -1
        self.repaint_panes()

    def offer_mkv_copy(self, row):
        if self.movement_locked([row.path]) or self._inline_operation is not None:
            QMessageBox.information(self, tr('Traitement en cours'), tr('Attendez la fin du traitement en cours.'))
            return
        if not self.ensure_components([tr('ffmpeg'), tr('ffprobe')]):
            return
        if QMessageBox.question(self, tr('Créer une copie MKV compatible'), tr('Créer une copie MKV compatible, sans réencodage ?\nL’original reste conservé. Toutes les pistes et les données encodées seront contrôlées ; une légère adaptation des repères de temps propres au conteneur est acceptée.'), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        target, _ = QFileDialog.getSaveFileName(self, tr('Nom de la copie MKV'), str(row.path.with_name(row.path.stem + tr(' — copie.mkv'))), tr('Vidéo Matroska (*.mkv)'))
        if not target:
            return
        worker = RemuxWorker(row.path, Path(target))
        self.move_worker = worker
        self.begin_inline_operation(worker, tr('Copie MKV'))
        worker.progress.connect(lambda text: self.update_inline_operation(tr('Copie MKV — ') + text))

        def finished():
            self.move_worker = None
            self.finish_inline_operation(worker)
            if worker.error:
                QMessageBox.warning(self, tr('Copie MKV non créée'), worker.error)
            else:
                self.show_activity_message(tr('Copie MKV créée et vérifiée ; original conservé.'), 10000)
                self.refresh_visible_entries([Path(target)])
            worker.deleteLater()
        worker.finished.connect(finished)
        self.start_runtime_worker(worker, tr('Création de la copie MKV'))

    @staticmethod
    def mkv_copy_is_relevant(error):
        text = str(error).casefold()
        markers = (tr('could not find tag'), tr('codec none'), tr('codec not currently supported'), tr('could not write header'), tr('incompatible with container'), tr('conteneur'), tr('container'))
        return any((marker in text for marker in markers))

    def ensure_components(self, commands, report=False):
        missing = [name for name in commands if not component_path(name)]
        if not missing:
            if report:
                QMessageBox.information(self, tr('Composants vidéo'), tr('Les outils nécessaires sont disponibles. Une piste inconnue ou incompatible ne se résout pas nécessairement en installant un codec.'))
            return True
        manager = shutil.which(tr('pacman')) or shutil.which(tr('dnf'))
        if services.name != tr('linux') or Path(tr('/run/ostree-booted')).exists() or not manager:
            QMessageBox.information(self, tr('Composants manquants'), tr('Installez via votre logithèque : ') + tr(', ').join(missing))
            return False
        arch = Path(manager).name == tr('pacman')
        names = {tr('ffmpeg'): tr('ffmpeg') if arch else tr('ffmpeg-free'), tr('ffprobe'): tr('ffmpeg') if arch else tr('ffmpeg-free'), tr('mediainfo'): tr('mediainfo'), tr('mkvpropedit'): tr('mkvtoolnix-cli') if arch else tr('mkvtoolnix'), tr('mkvextract'): tr('mkvtoolnix-cli') if arch else tr('mkvtoolnix'), tr('qt-multimedia'): tr('pyside6') if arch else tr('python3-pyside6')}
        packages = sorted({names[name] for name in missing if name in names})
        if not packages:
            packages = missing
        command = (('sudo pacman -Syu --needed ' if arch else 'sudo dnf install ')
                   + ' '.join(packages))
        box = QMessageBox(self)
        box.setWindowTitle(tr('Composants manquants'))
        box.setText(tr('Installez les composants avec le gestionnaire de paquets du système, puis relancez l’opération.'))
        box.setInformativeText(tr('Paquets requis : ') + tr(', ').join(packages) + tr('\n\nCommande proposée :\n') + command)
        box.exec()
        return False
