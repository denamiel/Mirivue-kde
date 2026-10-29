from .i18n import tr
tr('Bounded GUI work, file checks off the GUI thread, and coalesced state writes.')
import json
from PySide6.QtCore import QObject, QThread, Signal, QSettings, QTimer
from .extensions import fingerprint

class PrepareWorker(QThread):

    def __init__(self, rows):
        super().__init__()
        self.rows = rows
        self.valid = []
        self.errors = []
        self.cancelled = False
        self.lock_paths = set()
        self.lock_parents = set()

    def cancel(self):
        self.cancelled = True
        self.requestInterruption()

    def run(self):
        for row in self.rows:
            if self.isInterruptionRequested():
                return
            try:
                resolved = row.path.resolve()
                self.lock_paths.add(resolved)
                self.lock_parents.update(resolved.parents)
                actual = fingerprint(row.path)
                if row.file_signature is not None and actual != row.file_signature:
                    raise ValueError(tr('Le fichier a changé : actualisez et relancez l’opération.'))
                if row.file_signature is None:
                    row.file_signature = actual
                self.valid.append(row)
            except (OSError, ValueError) as error:
                self.errors.append((row.path, str(error)))

class JsonWriter(QThread):

    def __init__(self, filename, fmt, values):
        super().__init__()
        self.filename = filename
        self.fmt = fmt
        self.values = values
        self.error = ''

    def run(self):
        try:
            settings = QSettings(self.filename, self.fmt)
            for key, value in self.values.items():
                encoded = ''.join(json.JSONEncoder(ensure_ascii=False).iterencode(value))
                settings.setValue('library-v1/' + key, encoded)
            settings.sync()
            if settings.status() != QSettings.Status.NoError:
                self.error = tr('Impossible de sauvegarder les résultats locaux. Vérifiez les droits et l’espace disque.')
        except Exception as error:
            self.error = str(error)

class DeferredStore(QObject):
    failed = Signal(str)

    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.pending = {}
        self.latest = {}
        self.worker = None
        self.idle = None
        self.error = ''
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.flush)

    def put(self, key, value):
        self.latest[key] = value
        self.pending[key] = value
        if not self.timer.isActive():
            self.timer.start()

    def busy(self):
        return bool(self.pending or self.worker is not None)

    def flush(self):
        self.timer.stop()
        if self.worker is not None or not self.pending:
            return
        values = self.pending
        self.pending = {}
        self.worker = JsonWriter(self.settings.fileName(), self.settings.format(), values)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def finished(self):
        self.error = self.worker.error
        self.worker.deleteLater()
        self.worker = None
        if self.error:
            self.failed.emit(self.error)
        if self.pending:
            self.flush()
        elif self.idle:
            self.idle()

class OrderedPaths(dict):

    def add(self, path):
        self[path] = None
