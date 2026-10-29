from .i18n import tr, trf
tr('Explicit, no-overwrite moves. Cross-volume copies are staged before publication.')
from collections import Counter
import hashlib
import errno
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import time
from PySide6.QtCore import QThread, Signal
from .platform_services import services
TECHNICAL = {tr('hdr'), tr('sdr'), tr('uhd'), tr('hd'), tr('fhd'), tr('hevc'), tr('avc'), tr('aac'), tr('ac'), tr('dts'), tr('truehd'), tr('atmos'), tr('bluray'), tr('bdrip'), tr('brrip'), tr('webrip'), tr('web'), tr('dl'), tr('dvdrip'), tr('remux'), tr('multi'), tr('vostfr'), tr('vf'), tr('vff'), tr('vfq'), tr('french'), tr('eng'), tr('mkv'), tr('mp4'), tr('avi'), tr('saison'), tr('season'), tr('episode'), tr('ep')}

def suggest_folder(paths):
    sequences = []
    for path in paths:
        tokens = re.findall(tr('[^\\W_]+'), Path(path).stem, flags=re.UNICODE)
        sequences.append([t for t in tokens if len(t) > 1 and (not any((c.isdigit() for c in t))) and (t.casefold() not in TECHNICAL) and (not (t.isupper() and re.fullmatch(tr('[IVXLCDM]+'), t)))])
    counts = Counter((word for tokens in sequences for word in {t.casefold() for t in tokens}))
    repeated = {t for t, count in counts.items() if count >= 2}
    if not repeated:
        return tr('Nouveau dossier')
    best = max((counts[t] for t in repeated))
    chosen = {t for t in repeated if counts[t] >= max(2, best - 1)}
    ordered = []
    for tokens in sequences:
        for token in tokens:
            if token.casefold() in chosen and token.casefold() not in {t.casefold() for t in ordered}:
                ordered.append(token)
    return tr(' ').join(ordered[:6])[:100].strip() or tr('Nouveau dossier')

def valid_name(name):
    return services.validate_portable_name(name) is None

def invalid_name_reason(name):
    return services.validate_portable_name(name) or tr('Nom invalide.')

def exists(path):
    return os.path.lexists(path)

def normalize_sources(paths):
    paths = list(dict.fromkeys((Path(p).absolute() for p in paths)))
    selected = set(paths)
    return [p for p in paths if not any((parent in selected and (not parent.is_symlink()) for parent in p.parents))]

def validate_target(source, target):
    source = Path(source)
    target = Path(target)
    if not exists(source):
        raise OSError(tr('La source n’existe plus.'))
    if not target.parent.is_dir():
        raise OSError(tr('Le dossier de destination est inaccessible.'))
    if source.is_dir() and (not source.is_symlink()):
        resolved = source.resolve()
        parent = target.parent.resolve()
        if parent == resolved or resolved in parent.parents:
            raise OSError(tr('Impossible de déplacer un dossier à l’intérieur de lui-même.'))
    if exists(target):
        raise FileExistsError(tr('Un élément porte déjà ce nom dans la destination.'))

def rename_noreplace(source, target):
    tr('Atomically rename without replacing a destination on the current OS.')
    services.rename_no_replace(Path(source), Path(target))

def tree_snapshot(path, cancelled=lambda: False, progress=lambda count, current: None):
    output = {}
    last_report = 0.0

    def visit(p):
        nonlocal last_report
        if cancelled():
            raise InterruptedError()
        st = p.lstat()
        if not (stat.S_ISREG(st.st_mode) or stat.S_ISDIR(st.st_mode) or stat.S_ISLNK(st.st_mode)):
            raise OSError(tr('Ce dossier contient un élément spécial qui ne peut pas être déplacé.'))
        output[str(p.relative_to(path))] = (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, os.readlink(p) if p.is_symlink() else '')
        now = time.monotonic()
        if len(output) == 1 or now - last_report >= 0.08:
            progress(len(output), p)
            last_report = now
        if stat.S_ISDIR(st.st_mode):
            for child in p.iterdir():
                visit(child)
    visit(path)
    progress(len(output), path)
    return output

def _move_one(source, target, cancelled=lambda: False, progress=lambda text: None, copy_only=False,
              bytes_progress=lambda done, total: None, before_snapshot=None):
    source = Path(source)
    target = Path(target)
    validate_target(source, target)
    if cancelled():
        raise InterruptedError()
    if not copy_only:
        try:
            rename_noreplace(source, target)
            return ''
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
    before = before_snapshot if before_snapshot is not None else tree_snapshot(source, cancelled)
    total_bytes = 2 * sum((info[3] for info in before.values() if stat.S_ISREG(info[2])))
    transferred = 0
    bytes_progress(0, total_bytes)
    staging = Path(tempfile.mkdtemp(prefix=tr('.mirivue-deplacement-'), dir=target.parent))
    staged = staging / source.name

    def copy_file(src, dst):
        nonlocal transferred
        if cancelled():
            raise InterruptedError()
        progress(tr('Copie de ') + Path(src).name)
        digest = hashlib.sha256()
        with open(src, tr('rb')) as incoming, open(dst, tr('xb')) as outgoing:
            while True:
                if cancelled():
                    raise InterruptedError()
                data = incoming.read(1024 * 1024)
                if not data:
                    break
                outgoing.write(data)
                digest.update(data)
                transferred += len(data)
                bytes_progress(transferred, total_bytes)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        progress(tr('Vérification de ') + Path(src).name)
        copied = hashlib.sha256()
        with open(dst, tr('rb')) as stream:
            while True:
                if cancelled():
                    raise InterruptedError()
                data = stream.read(1024 * 1024)
                if not data:
                    break
                copied.update(data)
                transferred += len(data)
                bytes_progress(transferred, total_bytes)
        if copied.digest() != digest.digest():
            raise OSError(tr('La copie ne correspond pas au contenu lu. La source est conservée.'))
        shutil.copystat(src, dst)
        return dst
    try:
        if source.is_symlink():
            os.symlink(os.readlink(source), staged)
        elif source.is_dir():
            shutil.copytree(source, staged, symlinks=True, copy_function=copy_file)
        else:
            copy_file(source, staged)
        def verify_inventory(count, _current):
            progress(trf('Contrôle final — \x1f0\x1f élément(s) vérifié(s)', count))

        if tree_snapshot(source, cancelled, verify_inventory) != before:
            raise OSError(tr('La source a changé pendant la copie. Elle a été conservée ; recommencez.'))
        if cancelled():
            raise InterruptedError()
        rename_noreplace(staged, target)
        if copy_only:
            return ''
        try:
            if source.is_dir() and (not source.is_symlink()):
                shutil.rmtree(source)
            else:
                source.unlink()
        except OSError:
            return tr('La copie est disponible à destination, mais la source n’a pas pu être entièrement supprimée. Vérifiez les deux emplacements.')
        return ''
    finally:
        shutil.rmtree(staging, ignore_errors=True)

def move_one(source, target, cancelled=lambda: False, progress=lambda text: None, copy_only=False,
             bytes_progress=lambda done, total: None, before_snapshot=None):
    from .media import companion, AUDIO_EXT, IMAGE_EXT
    from .metadata import EXTENSIONS
    from .extensions import fingerprint
    side = companion(source)
    target_side = companion(target)
    has_side = source.suffix.lower() in EXTENSIONS | AUDIO_EXT | IMAGE_EXT and source.is_file() and side.is_file()
    created = False
    signature = None
    published = None
    if has_side:
        if side.is_symlink() or exists(target_side):
            raise OSError(errno.EEXIST, tr('Conflit de fichier compagnon XMP'), str(target_side))
        signature = fingerprint(side)
        _move_one(side, target_side, cancelled, progress, copy_only=True)
        published = fingerprint(target_side)
        created = True
    try:
        warning = _move_one(source, target, cancelled, progress, copy_only, bytes_progress, before_snapshot)
    except BaseException:
        if created and fingerprint(target_side) == published:
            target_side.unlink()
        raise
    if has_side and (not copy_only):
        try:
            if fingerprint(side) == signature:
                side.unlink()
            else:
                warning = (warning or '') + tr(' Le compagnon XMP source a changé et a été conservé.')
        except OSError:
            warning = (warning or '') + tr(' Le compagnon XMP source n’a pas pu être retiré.')
    return warning

class MoveWorker(QThread):
    progress = Signal(int, int, str)

    def __init__(self, plans, notes=None, copy_only=False):
        super().__init__()
        self.plans = plans
        self.moved = {}
        self.errors = []
        self.cancelled = False
        self.copy_only = copy_only
        self.notes = notes or {}
        self.note_updates = {}
        self.source_signatures = {}
        self._running = threading.Event()
        self._running.set()

    def pause(self):
        self._running.clear()

    def resume(self):
        self._running.set()

    def requestInterruption(self):
        super().requestInterruption()
        self._running.set()

    def checked_interruption(self):
        while not self._running.wait(0.1):
            if self.isInterruptionRequested():
                return True
        return self.isInterruptionRequested()

    def run(self):
        for i, (source, target) in enumerate(self.plans):
            if self.checked_interruption():
                self.cancelled = True
                break
            self.progress.emit(0, 0, tr('Préparation de ') + source.name)
            position = i * 1000
            last_emit = 0
            message = tr('Préparation de ') + source.name

            def report(text):
                nonlocal message
                message = text
                self.progress.emit(position, len(self.plans) * 1000, message)

            def advance(done, total):
                nonlocal position, last_emit
                position = i * 1000 + (min(990, int(990 * done / total)) if total else 0)
                now = time.monotonic()
                if now - last_emit >= 0.08 or done == 0 or done == total:
                    self.progress.emit(position, len(self.plans) * 1000, message)
                    last_emit = now
            def inventory(count, _current):
                nonlocal message
                message = trf('Préparation de \x1f0\x1f — \x1f1\x1f élément(s) trouvé(s)', source.name, count)
                self.progress.emit(0, 0, message)

            try:
                snapshot = tree_snapshot(source, self.checked_interruption, inventory)
                signatures = {source / relative: (info[0], info[1], info[3], info[4]) for relative, info in snapshot.items()}
                self.source_signatures.update(signatures)
                message = trf('Préparation terminée — \x1f0\x1f élément(s)', len(snapshot))
                self.progress.emit(position, len(self.plans) * 1000, message)
                warning = move_one(source, target, self.checked_interruption, report, copy_only=self.copy_only,
                                   bytes_progress=advance, before_snapshot=snapshot)
                self.moved[source] = target
                if warning:
                    self.errors.append(trf('\x1f0\x1f : \x1f1\x1f', source.name, warning))
            except InterruptedError:
                self.cancelled = True
                break
            except OSError as error:
                if self.isInterruptionRequested():
                    self.cancelled = True
                    break
                if error.errno == errno.EEXIST:
                    message = tr('Un élément de ce nom existe déjà. Aucun remplacement effectué.')
                elif error.errno == errno.ENOSPC:
                    message = tr('Le disque de destination est plein. La source est conservée.')
                elif error.errno in (errno.EACCES, errno.EPERM):
                    message = tr('Vous n’avez pas les droits nécessaires.')
                elif error.errno == errno.ENOENT:
                    message = tr('La source ou la destination n’est plus disponible.')
                elif error.errno == errno.ENOTSUP:
                    message = tr('Ce système de fichiers ne permet pas le déplacement sécurisé utilisé par Mirivue.')
                elif error.errno == errno.EIO:
                    message = tr('Le disque a signalé une erreur de lecture ou d’écriture. Vérifiez les emplacements.')
                else:
                    message = str(error)
                self.errors.append(trf('\x1f0\x1f : \x1f1\x1f', source.name, message))
            self.progress.emit((i + 1) * 1000, len(self.plans) * 1000, tr('Copie en cours') if self.copy_only else tr('Déplacement en cours'))
