from .i18n import tr, trf
tr('Exact-byte duplicate detection; no filename or perceptual matching.')
import hashlib
import os
import stat
from pathlib import Path
from collections import defaultdict
from .extensions import fingerprint

def file_hash(path, cancelled=lambda: False):
    path = Path(path)
    signature = fingerprint(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, tr('O_NOFOLLOW'), 0))
    with os.fdopen(fd, tr('rb')) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != signature:
            raise ValueError(tr('Le fichier a changé ou n’est pas un fichier ordinaire.'))
        digest = hashlib.sha256()
        while True:
            if cancelled():
                raise InterruptedError()
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        if fingerprint(path) != signature:
            raise ValueError(tr('Le fichier a changé pendant sa lecture.'))
    return (signature, digest.hexdigest())

def find_duplicates(paths, cancelled=lambda: False, progress=lambda text: None, warning=lambda text: None):
    sizes = defaultdict(list)
    seen = set()
    for path in dict.fromkeys(paths):
        if cancelled():
            raise InterruptedError()
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                continue
            identity = (info.st_dev, info.st_ino)
            if identity in seen:
                continue
            seen.add(identity)
            sizes[info.st_size].append(path)
        except OSError as error:
            warning(trf('\x1f0\x1f : \x1f1\x1f', path, error))
    hashes = defaultdict(list)
    candidates = [p for group in sizes.values() if len(group) > 1 for p in group]
    for i, path in enumerate(candidates, 1):
        progress(trf('Recherche des doublons — lecture \x1f0\x1f/\x1f1\x1f : \x1f2\x1f', i, len(candidates), path.name))
        try:
            signature, digest = file_hash(path, cancelled)
            hashes[signature[2], digest].append((path, signature))
        except InterruptedError:
            raise
        except (OSError, ValueError) as error:
            warning(trf('\x1f0\x1f : \x1f1\x1f', path, error))
    return [dict(digest=digest, files=files) for (size, digest), files in hashes.items() if len(files) > 1]

def keep_one(group, keeper, trash, cancelled=lambda: False, progress=lambda text: None):
    files = dict(group[tr('files')])
    keeper = Path(keeper)
    if keeper not in files:
        raise ValueError(tr('Aucun fichier à conserver dans ce groupe.'))
    for path, expected in files.items():
        progress(trf('Vérification avant mise à la corbeille : \x1f0\x1f', path.name))
        signature, digest = file_hash(path, cancelled)
        if signature != expected or digest != group[tr('digest')] or path.stat().st_nlink != 1:
            raise ValueError(tr('Un fichier a changé. Aucun fichier supprimé : relancez la recherche de doublons.'))
    removed = []
    errors = []
    for path, expected in files.items():
        if path == keeper:
            continue
        if cancelled():
            break
        try:
            if fingerprint(keeper) != files[keeper] or fingerprint(path) != expected or path.is_symlink():
                raise ValueError(tr('Un fichier a changé ; opération arrêtée.'))
            trash(path)
            removed.append(path)
        except (OSError, ValueError) as error:
            errors.append(trf('\x1f0\x1f : \x1f1\x1f', path, error))
            break
    return (removed, errors)
