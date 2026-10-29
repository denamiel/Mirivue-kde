from .i18n import tr, trf
tr('Internal name validation and safe argument building for external renamers.')
import os
from pathlib import Path
import shlex
import shutil
import re
import string
from types import SimpleNamespace
from .extensions import Rename, fingerprint
from .platform_services import services
PRESETS = {tr('Thunar'): (tr('thunar'), tr('-B')), tr('Bulky'): (tr('bulky'), ''), tr('KRename'): (tr('krename'), '')}

def folder_rename_rows(folder):
    """Inventory direct children for the same safe preview used by selections."""
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError(tr('Le dossier sélectionné n’est plus accessible.'))
    with os.scandir(folder) as entries:
        paths = [folder / entry.name for entry in entries]
    rows = []
    for path in sorted(paths, key=lambda item: (item.name.casefold(), item.name)):
        try:
            signature = fingerprint(path)
            is_dir = path.is_dir()
        except OSError:
            signature = None
            is_dir = False
        rows.append(SimpleNamespace(path=path, is_dir=is_dir, file_signature=signature))
    return rows

def batch_names(rows, mode, first='', second='', start=1, digits=3):
    tr('Build portable bulk-rename proposals while preserving file extensions.')
    names = []
    for offset, row in enumerate(rows):
        original = row.path.name
        suffix = '' if getattr(row, tr('is_dir'), False) else row.path.suffix
        stem = original[:-len(suffix)] if suffix else original
        if mode == tr('prefix'):
            candidate = str(first) + stem
        elif mode == tr('suffix'):
            candidate = stem + str(first)
        elif mode == tr('replace'):
            candidate = stem.replace(str(first), str(second)) if str(first) else stem
        elif mode == tr('number'):
            candidate = str(first).strip() + tr(' ') + str(int(start) + offset).zfill(int(digits)) if str(first).strip() else stem
        elif mode == tr('title'):
            candidate = re.sub(r'(^|[\s_-]+)([^\W\d_])', lambda match: match.group(1) + match.group(2).upper(), stem, flags=re.UNICODE)
        elif mode == 'metadata':
            from .media import FIELDS
            tags = getattr(row, 'media_tags', {})
            fields = [name for _, name, _, _ in string.Formatter().parse(first) if name]
            if any(name not in FIELDS or not tags.get(name) for name in fields):
                raise ValueError(tr('Un champ du modèle est inconnu ou manquant. Complétez les métadonnées ou changez le modèle.'))
            candidate = re.sub(r'[/\\\x00-\x1f]', '_', first.format_map(tags)).strip()
            if not candidate:
                raise ValueError(tr('Le nom proposé est vide.'))
        else:
            candidate = original
        names.append(candidate + suffix if mode != tr('manual') else candidate)
    return names

def prepare_names(rows, names):
    if len(rows) != len(names):
        raise ValueError(tr('Le nombre de noms ne correspond pas à la sélection'))
    # A destination occupied by another selected item is not a conflict when
    # that item is itself moving.  apply_renames stages the batch first, so
    # chains such as 002→001, 003→002 can be completed without overwriting.
    changed_sources = {
        row.path for row, name in zip(rows, names)
        if name != row.path.name
    }
    plans = []
    for row, name in zip(rows, names):
        if name == row.path.name:
            continue
        issue = ''
        reason = services.validate_portable_name(name)
        if reason:
            issue = reason
            target = row.path
        else:
            target = row.path.parent / name
            try:
                if row.path.is_symlink() or not (row.path.is_file() or row.path.is_dir()):
                    issue = tr('Fichier ordinaire requis.')
                elif row.file_signature is None or fingerprint(row.path) != row.file_signature:
                    issue = tr('Fichier modifié : actualisez le dossier.')
                elif os.path.lexists(target) and target not in changed_sources:
                    issue = tr('Ce nom existe déjà.')
            except OSError as error:
                issue = str(error)
        plans.append(Rename(row.path, target, row.file_signature, issue))
    targets = {}
    for p in plans:
        targets[p.destination] = targets.get(p.destination, 0) + 1
    return [Rename(p.source, p.destination, p.signature, p.issue or (tr('Nom proposé plusieurs fois.') if targets[p.destination] > 1 else '')) for p in plans]

def external_command(program, arguments, paths):
    program = program.strip()
    executable = shutil.which(os.path.expanduser(program))
    if not executable:
        raise ValueError(trf('Logiciel introuvable : \x1f0\x1f. Installez-le avec votre logithèque ou choisissez un autre programme.', program))
    try:
        args = shlex.split(arguments)
    except ValueError as error:
        raise ValueError(tr('Options invalides : vérifiez les guillemets.')) from error
    if not paths:
        raise ValueError(tr('Sélectionnez au moins un fichier ou un dossier.'))
    for path in paths:
        if not (path.is_file() or path.is_dir()):
            raise ValueError(trf('Élément introuvable : \x1f0\x1f. Actualisez le dossier.', path))
    return (executable, args + [str(path.absolute()) for path in paths])

def find_external_renames(rows):
    tr('Follow in-place renames by identity; never guess by similar names.')
    pending = []
    for row in rows:
        try:
            if row.file_signature and fingerprint(row.path) != row.file_signature:
                pending.append(row)
        except OSError:
            pending.append(row)
    directories = {}
    for row in pending:
        if row.path.parent in directories:
            continue
        identities = {}
        try:
            for path in row.path.parent.iterdir():
                try:
                    identities.setdefault(fingerprint(path), []).append(path)
                except OSError:
                    pass
        except OSError:
            pass
        directories[row.path.parent] = identities
    renamed = {}
    for row in pending:
        matches = directories[row.path.parent].get(row.file_signature, [])
        if len(matches) == 1 and matches[0] != row.path:
            renamed[row.path] = matches[0]
    return renamed
