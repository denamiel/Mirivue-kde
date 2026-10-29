"""Safe extraction fallback for formats not exposed as KIO archive URLs."""

from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def safe_archive_entry_name(name):
    """Accept one top-level member name, never a path supplied by an archive."""
    value = str(name or '')
    return bool(value and value not in ('.', '..') and '\x00' not in value
                and '/' not in value and '\\' not in value
                and not Path(value).is_absolute())


def safe_archive_member_path(name):
    """Accept a relative member path that cannot leave the staging directory."""
    value = str(name or '')
    if not value or '\x00' in value:
        return False
    normalized = value.replace('\\', '/')
    if normalized.startswith('/') or (len(normalized) >= 2 and normalized[1] == ':'):
        return False
    return all(part not in ('', '.', '..') for part in normalized.split('/'))


def preflight_archive_members(archive, maximum_entries=100_000):
    """List members with 7-Zip and reject traversal before extraction starts."""
    sevenzip = shutil.which('7z') or shutil.which('7zz')
    if not sevenzip:
        raise OSError('7-Zip est nécessaire pour contrôler cette archive avant extraction.')
    try:
        result = subprocess.run(
            [sevenzip, 'l', '-slt', '--', str(archive)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OSError(f'Impossible de contrôler l’archive : {error}') from error
    if result.returncode != 0:
        message = result.stderr.decode(errors='replace').strip()
        raise OSError(message or 'La liste de l’archive est illisible.')
    output = result.stdout.decode(errors='replace')
    payload = output.split('----------', 1)[-1]
    members = [line[7:] for line in payload.splitlines() if line.startswith('Path = ')]
    if len(members) > maximum_entries:
        raise OSError('L’archive contient trop d’éléments.')
    if not members:
        raise OSError('L’archive est vide ou illisible.')
    dangerous = next((name for name in members if not safe_archive_member_path(name)), None)
    if dangerous is not None:
        raise OSError(f'L’archive contient un chemin dangereux : {dangerous}')
    return members


def validate_extracted_tree(root, maximum_entries=100_000):
    """Reject special files and links escaping the extraction staging area."""
    root = Path(root).resolve()
    count = 0
    for current, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            count += 1
            if count > maximum_entries:
                raise OSError('L’archive contient trop d’éléments.')
            path = Path(current) / name
            stat_result = path.lstat()
            if path.is_symlink():
                target = Path(os.readlink(path))
                if target.is_absolute():
                    raise OSError('L’archive contient un lien symbolique absolu dangereux.')
                resolved = (path.parent / target).resolve(strict=False)
                if resolved != root and root not in resolved.parents:
                    raise OSError('L’archive contient un lien symbolique sortant du dossier d’extraction.')
            elif not (path.is_file() or path.is_dir()):
                raise OSError('L’archive contient un type de fichier spécial non pris en charge.')
    return count


def extract_rar_with_ark(ark, archive, destination, cancelled=lambda: False,
                         progress=lambda value, message='': None):
    """Extract into a staging directory, then publish without overwriting."""
    archive, destination = Path(archive), Path(destination)
    staging = None
    published = []
    try:
        preflight_archive_members(archive)
        destination.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.mirivue-extraction-', dir=destination))
        progress(0, 'Extraction RAR avec Ark…')
        # A pipe left unread could block Ark when it emits enough diagnostics.
        # A temporary file permits long extractions while cancellation remains available.
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                [str(ark), '--batch', '--destination', str(staging), str(archive)],
                stdout=subprocess.DEVNULL, stderr=errors,
            )
            while process.poll() is None:
                if cancelled():
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    return False, 'Extraction annulée.'
                time.sleep(0.05)
            errors.seek(0)
            error = errors.read(16384).decode(errors='replace').strip()
        if process.returncode != 0:
            return False, error or 'Ark n’a pas pu extraire l’archive RAR.'
        validate_extracted_tree(staging)
        children = list(staging.iterdir())
        if not children:
            return False, 'L’archive RAR est vide ou illisible.'
        conflicts = [destination / child.name for child in children
                     if os.path.lexists(destination / child.name)]
        if conflicts:
            return False, f'Un élément existe déjà dans la destination : {conflicts[0].name}'
        from .file_moves import rename_noreplace
        for child in children:
            target = destination / child.name
            rename_noreplace(child, target)
            published.append((child, target))
        progress(100, 'Extraction RAR terminée.')
        return True, ''
    except OSError as error:
        for source, target in reversed(published):
            try:
                if os.path.lexists(target) and staging is not None:
                    target.rename(source)
            except OSError:
                pass
        if error.errno == errno.EEXIST:
            return False, 'Un élément porte déjà ce nom dans la destination.'
        return False, str(error)
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
