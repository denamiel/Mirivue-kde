from .i18n import tr, trf
tr('Explicit combined checks and on-demand folder duration scans.')
import os
from pathlib import Path
from PySide6.QtCore import Signal
from .app import DeepScanner
from .metadata import inspect, EXTENSIONS
from .media import AUDIO_EXT, IMAGE_EXT, kind

class DurationScanner(DeepScanner):
    duration_ready = Signal(object, object)
    inventory_progress = Signal(object, int, str)
    scan_progress = Signal(object, int, int, str)

    def __init__(self, paths):
        super().__init__(paths, embed=False)

    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():
                return
            self.item_started.emit(path)
            total = 0.0
            count = 0
            errors = []
            counts = {tr('video'): 0, tr('audio'): 0, tr('image'): 0}
            try:
                if path.is_symlink():
                    raise ValueError(tr('Choisissez un dossier réel, pas un lien symbolique.'))
                candidates = []
                for base, dirs, files in os.walk(path, followlinks=False, onerror=lambda e: errors.append(str(e))):
                    dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
                    for name in files:
                        if self.isInterruptionRequested():
                            raise InterruptedError()
                        candidate = Path(base) / name
                        if candidate.suffix.lower() not in EXTENSIONS | AUDIO_EXT | IMAGE_EXT or candidate.is_symlink():
                            continue
                        candidates.append(candidate)
                        if len(candidates) == 1 or len(candidates) % 25 == 0:
                            self.inventory_progress.emit(path, len(candidates), str(candidate))
                total_candidates = len(candidates)
                if candidates:
                    self.inventory_progress.emit(path, total_candidates, str(candidates[-1]))
                self.scan_progress.emit(path, 0, total_candidates, '')
                for index, candidate in enumerate(candidates, 1):
                    if self.isInterruptionRequested():
                        raise InterruptedError()
                    self.current.emit(tr('Durée totale : ') + str(candidate))
                    try:
                        row = inspect(candidate, self.isInterruptionRequested)
                        media = kind(row)
                        if media in counts:
                            counts[media] += 1
                        if media == tr('image'):
                            continue
                        seconds = row.sort_values[2]
                        if seconds < 0:
                            raise ValueError(tr('Durée inconnue'))
                        total += seconds
                        count += 1
                    except InterruptedError:
                        raise
                    except Exception as error:
                        errors.append(trf('\x1f0\x1f : \x1f1\x1f', candidate.name, error))
                    self.scan_progress.emit(path, index, total_candidates, str(candidate))
                self.duration_ready.emit(path, (total, count, errors, counts))
            except InterruptedError:
                return
            except Exception as error:
                self.failure.emit(path, str(error))
