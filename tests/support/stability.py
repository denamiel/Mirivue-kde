"""Safe, opt-in validation of Mirivue's local file-transfer engine."""

from __future__ import annotations

from dataclasses import dataclass
import errno
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile
import time
import tracemalloc
import zipfile


@dataclass(frozen=True)
class StabilityResult:
    success: bool
    report: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def tree_manifest(root: Path) -> dict[str, tuple[str, object]]:
    """Describe contents without following links or depending on timestamps."""
    root = Path(root)
    manifest = {}
    for path in sorted(root.rglob('*'), key=lambda item: str(item.relative_to(root))):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            manifest[relative] = ('link', os.readlink(path))
        elif path.is_dir():
            manifest[relative] = ('directory', None)
        elif path.is_file():
            manifest[relative] = ('file', (path.stat().st_size, _sha256(path)))
        else:
            manifest[relative] = ('special', None)
    return manifest


def _filesystem_type(path: Path) -> str:
    try:
        result = subprocess.run(
            ['findmnt', '-n', '-o', 'FSTYPE', '-T', str(path)],
            capture_output=True, text=True, timeout=3, check=False,
        )
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else 'inconnu'
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return 'inconnu'


def _create_source(root: Path, name='source') -> tuple[Path, list[str]]:
    source = root / name
    (source / 'dossier imbriqué').mkdir(parents=True)
    (source / 'texte.txt').write_text('Mirivue — contrôle de stabilité\n', encoding='utf-8')
    (source / 'vide.bin').write_bytes(b'')
    (source / 'Été_日本_😀.txt').write_text('Nom Unicode préservé\n', encoding='utf-8')
    (source / '.fichier-cache').write_bytes('élément caché'.encode('utf-8'))
    pattern = bytes(range(256))
    (source / 'dossier imbriqué' / 'bloc-2-Mio.bin').write_bytes(pattern * 8192)
    warnings = []
    try:
        os.symlink('texte.txt', source / 'lien-vers-texte')
    except OSError as error:
        warnings.append(f'Lien symbolique non créé par ce système de fichiers : {error}')
    return source, warnings


def run_stability_check(base, cancelled=lambda: False, progress=lambda message: None, transfer=None) -> StabilityResult:
    """Exercise the real transfer engine inside one uniquely-owned directory."""
    base = Path(base).expanduser().absolute()
    lines = ['Contrôle de stabilité des opérations de fichiers', f'Dossier choisi : {base}']
    success = False
    root = None
    if transfer is None:
        from .file_moves import move_one as transfer
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        if shutil.disk_usage(base).free < 16 * 1024 * 1024:
            raise OSError(errno.ENOSPC, 'Au moins 16 Mio libres sont nécessaires pour le contrôle.')
        filesystem = _filesystem_type(base)
        lines.append(f'Système de fichiers : {filesystem}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-', dir=base))
        lines.append(f'Espace isolé : {root.name}')
        source, warnings = _create_source(root)
        expected = tree_manifest(source)
        if cancelled():
            raise InterruptedError()

        copied = root / 'copie vérifiée'
        progress('Copie et vérification SHA-256…')
        transfer(source, copied, cancelled=cancelled, progress=progress, copy_only=True)
        if tree_manifest(source) != expected or tree_manifest(copied) != expected:
            raise OSError('La copie ne correspond pas à la source ou la source a été modifiée.')
        lines.append('RÉUSSI — copie avec conservation de la source et des contenus')

        progress('Contrôle du refus d’écrasement…')
        before_conflict = tree_manifest(copied)
        try:
            transfer(source, copied, cancelled=cancelled, progress=progress, copy_only=True)
        except OSError as error:
            if error.errno != errno.EEXIST and not isinstance(error, FileExistsError):
                raise
        else:
            raise OSError('Le moteur n’a pas refusé une destination existante.')
        if tree_manifest(copied) != before_conflict:
            raise OSError('La destination existante a changé pendant le test de conflit.')
        lines.append('RÉUSSI — conflit de nom refusé sans écrasement')

        rename_source = root / 'nom initial.txt'
        rename_source.write_text('renommage sûr', encoding='utf-8')
        rename_target = root / 'nom renommé — 日本.txt'
        progress('Renommage sans écrasement…')
        transfer(rename_source, rename_target, cancelled=cancelled, progress=progress, copy_only=False)
        if rename_source.exists() or _sha256(rename_target) != hashlib.sha256('renommage sûr'.encode()).hexdigest():
            raise OSError('Le renommage n’a pas conservé le contenu attendu.')
        lines.append('RÉUSSI — renommage Unicode sans écrasement')

        moved = root / 'dossier déplacé'
        progress('Déplacement et inventaire final…')
        transfer(copied, moved, cancelled=cancelled, progress=progress, copy_only=False)
        if copied.exists() or tree_manifest(moved) != expected:
            raise OSError('Le déplacement n’a pas produit l’inventaire attendu.')
        lines.append('RÉUSSI — déplacement avec inventaire intact')

        abandoned = list(root.rglob('.mirivue-deplacement-*'))
        if abandoned:
            raise OSError('Un dossier temporaire de transfert est resté présent.')
        lines.append('RÉUSSI — aucun dossier temporaire de transfert abandonné')
        for warning in warnings:
            lines.append('RÉSERVE — ' + warning)
        success = True
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        if root is not None:
            try:
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def run_cross_volume_check(source_base, destination_base, cancelled=lambda: False,
                           progress=lambda message: None, transfer=None,
                           device_ids=None) -> StabilityResult:
    """Move synthetic trees in both directions between two distinct devices."""
    source_base = Path(source_base).expanduser().absolute()
    destination_base = Path(destination_base).expanduser().absolute()
    lines = [
        'Contrôle croisé des déplacements entre deux disques',
        f'Premier emplacement : {source_base}',
        f'Second emplacement : {destination_base}',
    ]
    success = False
    source_root = destination_root = None
    if transfer is None:
        from .file_moves import move_one as transfer
    try:
        for base in (source_base, destination_base):
            if not base.is_dir() or base.is_symlink():
                raise OSError('Chaque emplacement doit être un dossier local existant et non un lien symbolique.')
            if not os.access(base, os.W_OK | os.X_OK):
                raise PermissionError(f'Emplacement inaccessible en écriture : {base}')
            if shutil.disk_usage(base).free < 16 * 1024 * 1024:
                raise OSError(errno.ENOSPC, f'Au moins 16 Mio libres sont nécessaires dans : {base}')
        devices = device_ids or (source_base.stat().st_dev, destination_base.stat().st_dev)
        if devices[0] == devices[1]:
            raise OSError('Les deux dossiers appartiennent au même système de fichiers. Choisissez deux disques ou partitions différents.')
        source_type = _filesystem_type(source_base)
        destination_type = _filesystem_type(destination_base)
        lines.extend((f'Premier système de fichiers : {source_type}', f'Second système de fichiers : {destination_type}'))
        source_root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-croisee-', dir=source_base))
        destination_root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-croisee-', dir=destination_base))
        lines.extend((f'Espace isolé 1 : {source_root.name}', f'Espace isolé 2 : {destination_root.name}'))

        outward_source, outward_warnings = _create_source(source_root, 'source aller')
        outward_manifest = tree_manifest(outward_source)
        outward_target = destination_root / 'destination aller'
        progress(f'Déplacement {source_type} vers {destination_type}…')
        transfer(outward_source, outward_target, cancelled=cancelled, progress=progress, copy_only=False)
        if outward_source.exists() or tree_manifest(outward_target) != outward_manifest:
            raise OSError('Le déplacement aller n’a pas conservé exactement les contenus.')
        lines.append(f'RÉUSSI — déplacement {source_type} → {destination_type}, source supprimée après vérification')

        return_source, return_warnings = _create_source(destination_root, 'source retour')
        return_manifest = tree_manifest(return_source)
        return_target = source_root / 'destination retour'
        progress(f'Déplacement {destination_type} vers {source_type}…')
        transfer(return_source, return_target, cancelled=cancelled, progress=progress, copy_only=False)
        if return_source.exists() or tree_manifest(return_target) != return_manifest:
            raise OSError('Le déplacement retour n’a pas conservé exactement les contenus.')
        lines.append(f'RÉUSSI — déplacement {destination_type} → {source_type}, source supprimée après vérification')

        abandoned = list(source_root.rglob('.mirivue-deplacement-*')) + list(destination_root.rglob('.mirivue-deplacement-*'))
        if abandoned:
            raise OSError('Un dossier temporaire de transfert est resté présent.')
        lines.append('RÉUSSI — aucun dossier temporaire de transfert abandonné sur les deux disques')
        for warning in outward_warnings + return_warnings:
            lines.append('RÉSERVE — ' + warning)
        success = True
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        for label, root in (('premier', source_root), ('second', destination_root)):
            if root is None:
                continue
            try:
                shutil.rmtree(root)
                lines.append(f'RÉUSSI — espace de test {label} supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet sur le {label} emplacement : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def run_failure_recovery_check(base, cancelled=lambda: False,
                               progress=lambda message: None, transfer=None) -> StabilityResult:
    """Inject common transfer failures and verify that no partial result escapes."""
    base = Path(base).expanduser().absolute()
    lines = [
        'Contrôle de récupération après incident',
        f'Dossier choisi : {base}',
        'Les incidents sont simulés dans un espace isolé ; aucun disque ne sera rempli ou déconnecté.',
    ]
    success = False
    root = None
    if transfer is None:
        from .file_moves import move_one as transfer

    scenarios = (
        ('espace disque insuffisant', errno.ENOSPC,
         'RÉUSSI — espace insuffisant simulé : source intacte et destination incomplète supprimée'),
        ('destination protégée', errno.EACCES,
         'RÉUSSI — destination protégée simulée : source intacte et aucun fichier publié'),
        ('périphérique retiré', errno.EIO,
         'RÉUSSI — retrait de périphérique simulé : source intacte et transfert temporaire nettoyé'),
    )
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        if shutil.disk_usage(base).free < 16 * 1024 * 1024:
            raise OSError(errno.ENOSPC, 'Au moins 16 Mio libres sont nécessaires pour le contrôle.')
        lines.append(f'Système de fichiers : {_filesystem_type(base)}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-incidents-', dir=base))
        lines.append(f'Espace isolé : {root.name}')

        for index, (label, error_number, success_line) in enumerate(scenarios, start=1):
            if cancelled():
                raise InterruptedError()
            source = root / f'source-{index}.bin'
            target = root / f'destination-{index}.bin'
            pattern = bytes(range(256))
            source.write_bytes(pattern * 16384)  # 4 Mio, uniquement dans l’espace isolé.
            expected = (source.stat().st_size, _sha256(source))
            fault_raised = False

            def inject_fault(done, _total, *, number=error_number, incident=label):
                nonlocal fault_raised
                if cancelled():
                    raise InterruptedError()
                if done > 0 and not fault_raised:
                    fault_raised = True
                    raise OSError(number, f'Incident simulé : {incident}')

            progress(f'Simulation contrôlée : {label}…')
            try:
                transfer(
                    source, target, cancelled=cancelled, progress=progress,
                    copy_only=True, bytes_progress=inject_fault,
                )
            except InterruptedError:
                raise
            except OSError as error:
                if error.errno != error_number:
                    raise OSError(f'Le scénario « {label} » a produit une erreur inattendue : {error}') from error
            else:
                raise OSError(f'Le scénario « {label} » n’a pas interrompu le transfert comme prévu.')

            if not fault_raised:
                raise OSError(f'Le scénario « {label} » n’a pas été déclenché après le début de la copie.')
            if not source.is_file() or (source.stat().st_size, _sha256(source)) != expected:
                raise OSError(f'La source a été modifiée pendant le scénario « {label} ».')
            if os.path.lexists(target):
                raise OSError(f'Une destination incomplète a été publiée pendant le scénario « {label} ».')
            if list(root.glob('.mirivue-deplacement-*')):
                raise OSError(f'Un dossier temporaire subsiste après le scénario « {label} ».')
            lines.append(success_line)

        success = True
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        if root is not None:
            try:
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def _write_rar4_stored(path: Path, name: str, data: bytes) -> None:
    """Write one uncompressed RAR 4 entry for the isolated compatibility test."""
    import zlib

    def header(kind, flags, body=b''):
        raw = struct.pack('<BHH', kind, flags, 7 + len(body)) + body
        return struct.pack('<H', zlib.crc32(raw) & 0xffff) + raw

    encoded = name.encode('ascii')
    main = header(0x73, 0, b'\0' * 6)
    file_body = struct.pack(
        '<IIBIIBBHI', len(data), len(data), 3, zlib.crc32(data) & 0xffffffff,
        0, 20, 0x30, len(encoded), 0o100644,
    ) + encoded
    file_header = header(0x74, 0x8000, file_body)
    end = header(0x7b, 0x4000)
    path.write_bytes(b'Rar!\x1a\x07\x00' + main + file_header + data + end)


def _create_archive_samples(root: Path) -> tuple[dict[str, Path], dict[str, dict]]:
    payload = root / 'contenu-source'
    (payload / 'dossier').mkdir(parents=True)
    (payload / 'texte.txt').write_text('Archive Mirivue — contrôle\n', encoding='utf-8')
    (payload / 'vide.bin').write_bytes(b'')
    (payload / 'dossier' / 'bloc.bin').write_bytes(bytes(range(256)) * 4096)
    expected = tree_manifest(payload)
    archives = {}
    manifests = {}

    archives['ZIP'] = root / 'controle.zip'
    with zipfile.ZipFile(archives['ZIP'], 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for item in sorted(payload.rglob('*')):
            output.write(item, item.relative_to(payload))
    manifests['ZIP'] = expected

    archives['TAR'] = root / 'controle.tar'
    with tarfile.open(archives['TAR'], 'w') as output:
        for item in sorted(payload.iterdir()):
            output.add(item, arcname=item.name, recursive=True)
    manifests['TAR'] = expected

    seven_zip = shutil.which('7z') or shutil.which('7zz')
    if seven_zip:
        archive = root / 'controle.7z'
        result = subprocess.run(
            [seven_zip, 'a', '-t7z', str(archive), '.'], cwd=payload,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=60, check=False,
        )
        if result.returncode == 0 and archive.is_file():
            archives['7z'] = archive
            manifests['7z'] = expected

    rar_data = b'Archive RAR Mirivue\n'
    archives['RAR'] = root / 'controle.rar'
    _write_rar4_stored(archives['RAR'], 'texte-rar.txt', rar_data)
    rar_manifest_root = root / 'contenu-rar-attendu'
    rar_manifest_root.mkdir()
    (rar_manifest_root / 'texte-rar.txt').write_bytes(rar_data)
    manifests['RAR'] = tree_manifest(rar_manifest_root)
    return archives, manifests


def run_archive_stability_check(base, extractor, cancelled=lambda: False,
                                progress=lambda current, total, message: None) -> StabilityResult:
    """Create harmless archives and validate the application's extraction backends."""
    base = Path(base).expanduser().absolute()
    lines = [
        'Contrôle de stabilité des archives',
        f'Dossier choisi : {base}',
        'Les archives et leurs contenus sont créés uniquement dans un espace isolé.',
    ]
    root = None
    success = False
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        if shutil.disk_usage(base).free < 32 * 1024 * 1024:
            raise OSError(errno.ENOSPC, 'Au moins 32 Mio libres sont nécessaires pour le contrôle.')
        lines.append(f'Système de fichiers : {_filesystem_type(base)}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-archives-', dir=base))
        lines.append(f'Espace isolé : {root.name}')
        archives, manifests = _create_archive_samples(root)
        if '7z' not in archives:
            lines.append('NON TESTÉ — 7z : utilitaire 7z/7zz absent, création de l’archive impossible')

        ordered = [('ZIP', archives.get('ZIP')), ('7z', archives.get('7z')),
                   ('RAR', archives.get('RAR')), ('TAR', archives.get('TAR'))]
        tested = 0
        extracted_destinations = {}
        for position, (label, archive) in enumerate(ordered, start=1):
            if archive is None:
                continue
            if cancelled():
                raise InterruptedError()
            destination = root / f'extrait-{label.casefold()}'
            destination.mkdir()
            observed_progress = []

            def report(value, text='', *, step=position):
                value = max(0, min(100, int(value)))
                observed_progress.append(value)
                progress((step - 1) * 100 + value, len(ordered) * 100,
                         text or f'Extraction {label} — {value} %')

            progress((position - 1) * 100, len(ordered) * 100, f'Préparation de l’archive {label}…')
            ok, error = extractor(archive, destination, cancelled, report)
            if not ok:
                lines.append(f'ÉCHEC — {label} : {error or "extraction impossible"}')
                continue
            if tree_manifest(destination) != manifests[label]:
                lines.append(f'ÉCHEC — {label} : les contenus extraits ne correspondent pas à l’archive')
                continue
            if not observed_progress or max(observed_progress) < 100:
                lines.append(f'ÉCHEC — {label} : la progression n’a pas atteint 100 %')
                continue
            lines.append(f'RÉUSSI — {label} : contenus vérifiés et progression affichée')
            tested += 1
            extracted_destinations[label] = destination

        conflict_ok = False
        rar_destination = extracted_destinations.get('RAR')
        if rar_destination is not None:
            before_conflict = tree_manifest(rar_destination)
            progress(0, 0, 'Contrôle du refus d’un conflit de nom RAR…')
            conflict_result, _conflict_error = extractor(
                archives['RAR'], rar_destination, cancelled, lambda *_: None)
            conflict_ok = not conflict_result and tree_manifest(rar_destination) == before_conflict
            lines.append(
                'RÉUSSI — conflit de nom RAR refusé sans écrasement'
                if conflict_ok else
                'ÉCHEC — le conflit de nom RAR n’a pas été refusé sans modification')

        cancellation_ok = False
        if archives.get('ZIP') is not None:
            cancelled_destination = root / 'extrait-annule'
            cancelled_destination.mkdir()
            progress(0, 0, 'Contrôle de l’annulation d’une extraction…')
            cancellation_result, _cancellation_error = extractor(
                archives['ZIP'], cancelled_destination, lambda: True, lambda *_: None)
            cancellation_ok = not cancellation_result and not any(cancelled_destination.iterdir())
            lines.append(
                'RÉUSSI — extraction annulée sans contenu résiduel'
                if cancellation_ok else
                'ÉCHEC — l’annulation a laissé un contenu extrait')

        corrupted = root / 'archive-corrompue.zip'
        corrupted.write_bytes(b'PK\x03\x04archive volontairement incomplete')
        corrupted_destination = root / 'extrait-corrompu'
        corrupted_destination.mkdir()
        progress(0, 0, 'Contrôle du refus d’une archive corrompue…')
        ok, _error = extractor(corrupted, corrupted_destination, cancelled, lambda *_: None)
        if ok:
            lines.append('ÉCHEC — une archive corrompue a été signalée comme extraite')
        else:
            lines.append('RÉUSSI — archive corrompue refusée sans toucher aux fichiers personnels')

        expected_formats = 4
        success = tested == expected_formats and conflict_ok and cancellation_ok and not ok
        if tested != expected_formats:
            lines.append(f'INCOMPLET — {tested}/{expected_formats} formats validés')
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        if root is not None:
            try:
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def _run_media_command(arguments, cancelled=lambda: False, timeout=45):
    """Run one bounded FFmpeg command while keeping cancellation responsive."""
    process = subprocess.Popen(
        arguments, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if cancelled():
                process.terminate()
                raise InterruptedError()
            if time.monotonic() >= deadline:
                process.kill()
                raise TimeoutError('Le traitement multimédia a dépassé 45 secondes.')
            time.sleep(0.025)
        error = process.stderr.read().decode('utf-8', 'replace').strip()
        return process.returncode == 0, error
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def _create_multimedia_samples(root, cancelled=lambda: False):
    """Create short, deterministic media without reading any personal file."""
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise OSError('FFmpeg est absent.')
    audio_source = 'sine=frequency=660:sample_rate=48000:duration=1.2'
    video_source = 'testsrc2=size=320x180:rate=25:duration=1.2'
    definitions = [
        ('WAV / PCM', 'audio', root / 'controle-pcm.wav',
         ['-f', 'lavfi', '-i', audio_source, '-c:a', 'pcm_s16le']),
        ('FLAC', 'audio', root / 'controle.flac',
         ['-f', 'lavfi', '-i', audio_source, '-c:a', 'flac']),
        ('MP3', 'audio', root / 'controle.mp3',
         ['-f', 'lavfi', '-i', audio_source, '-c:a', 'libmp3lame', '-b:a', '128k']),
        ('MP4 / MPEG-4 + AAC', 'video', root / 'controle.mp4',
         ['-f', 'lavfi', '-i', video_source, '-f', 'lavfi', '-i', audio_source,
          '-shortest', '-c:v', 'mpeg4', '-q:v', '5', '-pix_fmt', 'yuv420p',
          '-c:a', 'aac', '-b:a', '96k']),
        ('MKV / FFV1 + FLAC', 'video', root / 'controle.mkv',
         ['-f', 'lavfi', '-i', video_source, '-f', 'lavfi', '-i', audio_source,
          '-shortest', '-c:v', 'ffv1', '-level', '3', '-c:a', 'flac']),
    ]
    samples = []
    for label, kind, path, options in definitions:
        if cancelled():
            raise InterruptedError()
        ok, error = _run_media_command(
            [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y', *options, str(path)],
            cancelled,
        )
        if not ok or not path.is_file() or path.stat().st_size == 0:
            raise OSError(f'Création impossible pour {label} : {error or "fichier vide"}')
        samples.append((label, kind, path))
    return samples


def _decode_multimedia_sample(path, cancelled=lambda: False):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        return False, 'FFmpeg est absent.'
    return _run_media_command(
        [ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(path), '-f', 'null', '-'],
        cancelled,
    )


def _remove_multimedia_caches(paths):
    """Do not retain cache records whose isolated source files are gone."""
    try:
        from . import media, metadata
        for path in paths:
            for cache in (
                media.cache_path(path), metadata._video_cache_path(path),
                metadata._quick_metadata_cache_path(path),
            ):
                try:
                    cache.unlink(missing_ok=True)
                except OSError:
                    pass
    except (ImportError, AttributeError):
        pass


def run_multimedia_stability_check(base, cancelled=lambda: False,
                                   progress=lambda current, total, message: None,
                                   sample_factory=None, inspector=None, decoder=None) -> StabilityResult:
    """Validate Mirivue metadata and decode paths using synthetic local media."""
    base = Path(base).expanduser().absolute()
    lines = [
        'Contrôle de stabilité multimédia',
        f'Dossier choisi : {base}',
        'Les médias sont générés uniquement dans un espace isolé ; aucun son n’est émis.',
    ]
    root = None
    samples = []
    success = False
    sample_factory = sample_factory or _create_multimedia_samples
    if inspector is None:
        from .metadata import inspect as inspector
    decoder = decoder or _decode_multimedia_sample
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        if shutil.disk_usage(base).free < 64 * 1024 * 1024:
            raise OSError(errno.ENOSPC, 'Au moins 64 Mio libres sont nécessaires pour le contrôle.')
        lines.append(f'Système de fichiers : {_filesystem_type(base)}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-multimedia-', dir=base))
        lines.append(f'Espace isolé : {root.name}')
        progress(0, 1, 'Création des médias de contrôle…')
        samples = sample_factory(root, cancelled)
        if not samples:
            raise OSError('Aucun média de contrôle n’a pu être créé.')
        total = len(samples) + 1
        validated = 0
        for position, (label, expected_kind, path) in enumerate(samples, start=1):
            if cancelled():
                raise InterruptedError()
            progress(position - 1, total, f'Lecture des métadonnées et décodage — {label}…')
            row = inspector(path, cancelled)
            actual_kind = getattr(row, 'media_type', '')
            duration = getattr(row, 'sort_values', [-1, -1, -1])[2]
            if actual_kind != expected_kind or not isinstance(duration, (int, float)) or duration <= 0:
                lines.append(f'ÉCHEC — {label} : type ou durée non reconnu par Mirivue')
                continue
            if expected_kind == 'video':
                technical = getattr(row, 'media_technical', {})
                if not technical.get('width') or not technical.get('height'):
                    lines.append(f'ÉCHEC — {label} : résolution non reconnue par Mirivue')
                    continue
            decoded, error = decoder(path, cancelled)
            if not decoded:
                lines.append(f'ÉCHEC — {label} : décodage incomplet ({error or "erreur inconnue"})')
                continue
            validated += 1
            progress(position, total, f'{label} validé.')
            lines.append(f'RÉUSSI — {label} : métadonnées, durée et décodage complet vérifiés')

        corrupted = root / 'media-corrompu.mp4'
        corrupted.write_bytes(b'\x00\x00\x00\x18ftypisommedia volontairement corrompu')
        progress(len(samples), total, 'Contrôle du refus d’un média corrompu…')
        decoded, _error = decoder(corrupted, cancelled)
        corruption_ok = not decoded
        lines.append(
            'RÉUSSI — média corrompu refusé sans toucher aux fichiers personnels'
            if corruption_ok else
            'ÉCHEC — le média corrompu a été signalé comme entièrement décodable')
        progress(total, total, 'Contrôle multimédia terminé.')
        success = validated == len(samples) and corruption_ok
        if validated != len(samples):
            lines.append(f'INCOMPLET — {validated}/{len(samples)} formats multimédias validés')
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        _remove_multimedia_caches([path for _label, _kind, path in samples])
        if root is not None:
            try:
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def run_large_folder_stability_check(base, cancelled=lambda: False,
                                     progress=lambda current, total, message: None,
                                     entry_builder=None, sort_key=None,
                                     file_count=20000, directory_count=400) -> StabilityResult:
    """Exercise the listing path on a large synthetic directory and clean it."""
    base = Path(base).expanduser().absolute()
    lines = [
        'Contrôle de stabilité des grands dossiers',
        f'Dossier choisi : {base}',
        'Les éléments sont créés uniquement dans un espace isolé.',
    ]
    root = None
    success = False
    tracing_was_active = tracemalloc.is_tracing()
    total = file_count + directory_count
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        if shutil.disk_usage(base).free < 128 * 1024 * 1024:
            raise OSError(errno.ENOSPC, 'Au moins 128 Mio libres sont nécessaires pour le contrôle.')
        if entry_builder is None or sort_key is None:
            raise ValueError('Le moteur de liste de Mirivue est indisponible.')
        lines.append(f'Système de fichiers : {_filesystem_type(base)}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-grand-dossier-', dir=base))
        lines.append(f'Espace isolé : {root.name}')
        creation_started = time.monotonic()
        hidden_count = unicode_count = target_count = 0
        for index in range(file_count):
            if cancelled():
                raise InterruptedError()
            hidden = index % 100 == 0
            unicode_name = index % 211 == 0
            target = index % 997 == 0
            prefix = '.cache-' if hidden else ('Été_日本_😀-' if unicode_name else ('cible-' if target else 'élément-'))
            (root / f'{prefix}{index}.txt').touch()
            hidden_count += int(hidden)
            unicode_count += int(unicode_name and not hidden)
            target_count += int(target and not hidden and not unicode_name)
            if index % 250 == 0:
                progress(index, total, f'Création des fichiers — {index}/{file_count}…')
        for index in range(directory_count):
            if cancelled():
                raise InterruptedError()
            name = f'.dossier-cache-{index}' if index % 50 == 0 else f'dossier-{index}'
            (root / name).mkdir()
            hidden_count += int(index % 50 == 0)
            if index % 50 == 0:
                progress(file_count + index, total, f'Création des dossiers — {index}/{directory_count}…')
        creation_seconds = time.monotonic() - creation_started
        progress(total, total, 'Inventaire du grand dossier…')

        scan_started = time.monotonic()
        all_entries = list(os.scandir(root))
        visible_entries = [entry for entry in all_entries if not entry.name.startswith('.')]
        scan_seconds = time.monotonic() - scan_started
        expected_visible = total - hidden_count
        if len(all_entries) != total or len(visible_entries) != expected_visible:
            raise OSError(f'Inventaire incohérent : {len(all_entries)} éléments, {len(visible_entries)} visibles.')
        lines.append(f'RÉUSSI — inventaire complet : {total} éléments, dont {hidden_count} cachés')

        if not tracing_was_active:
            tracemalloc.start()
        before_current, _before_peak = tracemalloc.get_traced_memory()
        build_started = time.monotonic()
        rows = []
        for index, entry in enumerate(visible_entries, start=1):
            if cancelled():
                raise InterruptedError()
            rows.append(entry_builder(Path(entry.path), entry.is_dir(follow_symlinks=False)))
            if index % 1000 == 0:
                progress(index, len(visible_entries), f'Préparation de l’affichage — {index}/{len(visible_entries)}…')
        build_seconds = time.monotonic() - build_started
        current, peak = tracemalloc.get_traced_memory()
        peak_mib = max(current, peak) - before_current
        peak_mib = max(0, peak_mib) / (1024 * 1024)
        if not tracing_was_active:
            tracemalloc.stop()
        if len(rows) != expected_visible:
            raise OSError('Le modèle d’affichage n’a pas reçu tous les éléments visibles.')
        if peak_mib > 512:
            raise MemoryError(f'La préparation de la liste a utilisé plus de 512 Mio ({peak_mib:.1f} Mio).')
        lines.append(f'RÉUSSI — préparation de {len(rows)} lignes avec un pic mémoire de {peak_mib:.1f} Mio')

        progress(0, len(rows), 'Tri naturel des noms…')
        sort_started = time.monotonic()
        rows.sort(key=lambda row: sort_key(row.path.name))
        sort_seconds = time.monotonic() - sort_started
        names = [row.path.name for row in rows]
        try:
            if names.index('élément-2.txt') >= names.index('élément-10.txt'):
                raise OSError('Le tri naturel place 10 avant 2.')
        except ValueError:
            raise OSError('Les éléments de contrôle du tri sont absents.')
        lines.append('RÉUSSI — tri naturel cohérent sur toutes les lignes')

        progress(0, len(rows), 'Recherche dans le grand dossier…')
        search_started = time.monotonic()
        matches = [row for row in rows if 'cible-' in row.path.name.casefold()]
        search_seconds = time.monotonic() - search_started
        if len(matches) != target_count:
            raise OSError(f'La recherche a trouvé {len(matches)} élément(s) au lieu de {target_count}.')
        unicode_visible = sum('Été_日本_😀-' in row.path.name for row in rows)
        if unicode_visible != unicode_count:
            raise OSError('Certains noms Unicode n’ont pas été conservés.')
        lines.append(f'RÉUSSI — recherche exacte et {unicode_visible} noms Unicode conservés')
        lines.append(
            'MESURES — création {:.2f} s ; inventaire {:.2f} s ; affichage {:.2f} s ; tri {:.2f} s ; recherche {:.2f} s'.format(
                creation_seconds, scan_seconds, build_seconds, sort_seconds, search_seconds,
            )
        )
        success = True
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        if tracemalloc.is_tracing() and not tracing_was_active:
            tracemalloc.stop()
        if root is not None:
            try:
                progress(0, 0, 'Nettoyage du grand dossier de test…')
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))


def _trash_candidates(base, name, recorded=None):
    candidates = []
    if recorded:
        candidates.append(Path(recorded))
    data_home = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    candidates.append(data_home / 'Trash' / 'files' / name)
    try:
        result = subprocess.run(
            ['findmnt', '-n', '-o', 'TARGET', '-T', str(base)],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            mount = Path(result.stdout.strip().splitlines()[0])
            uid = str(os.getuid())
            candidates.extend((
                mount / f'.Trash-{uid}' / 'files' / name,
                mount / '.Trash' / uid / 'files' / name,
            ))
    except (OSError, subprocess.TimeoutExpired):
        pass
    unique = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def run_deletion_stability_check(base, remover, cancelled=lambda: False,
                                 progress=lambda message: None) -> StabilityResult:
    """Validate permanent deletion and Trash using only uniquely-owned files."""
    base = Path(base).expanduser().absolute()
    lines = [
        'Contrôle de stabilité des suppressions',
        f'Dossier choisi : {base}',
        'Les fichiers sont créés uniquement dans un espace isolé.',
    ]
    root = None
    success = False
    trash_path = None
    trash_info = None
    try:
        if not base.is_dir() or base.is_symlink():
            raise OSError('Le dossier choisi doit être un dossier local existant et non un lien symbolique.')
        if not os.access(base, os.W_OK | os.X_OK):
            raise PermissionError('Le dossier choisi n’est pas accessible en écriture.')
        lines.append(f'Système de fichiers : {_filesystem_type(base)}')
        root = Path(tempfile.mkdtemp(prefix='Mirivue-validation-suppressions-', dir=base))
        lines.append(f'Espace isolé : {root.name}')
        permanent = root / 'suppression-definitive.txt'
        permanent.write_text('Mirivue — suppression définitive isolée\n', encoding='utf-8')
        permanent_hash = _sha256(permanent)
        if cancelled():
            raise InterruptedError()
        progress('Contrôle de la suppression définitive…')
        removed, errors, _locations = remover(
            [permanent], 'permanent', cancelled, lambda _path: None,
        )
        if errors or permanent.exists() or permanent not in removed:
            raise OSError('La suppression définitive du fichier de contrôle a échoué : ' + '; '.join(errors))
        if permanent_hash != hashlib.sha256('Mirivue — suppression définitive isolée\n'.encode()).hexdigest():
            raise OSError('Le contenu synthétique de référence était incohérent.')
        lines.append('RÉUSSI — suppression définitive limitée au fichier de contrôle')

        trash_file = root / f'Mirivue-corbeille-{root.name}.txt'
        trash_file.write_text('Mirivue — corbeille isolée\n', encoding='utf-8')
        expected_hash = _sha256(trash_file)
        if cancelled():
            raise InterruptedError()
        progress('Contrôle de la mise à la corbeille…')
        removed, errors, locations = remover(
            [trash_file], 'trash', cancelled, lambda _path: None,
        )
        if errors or trash_file.exists() or trash_file not in removed:
            raise OSError('La mise à la corbeille du fichier de contrôle a échoué : ' + '; '.join(errors))
        recorded = locations.get(trash_file)
        trash_path = next(
            (candidate for candidate in _trash_candidates(base, trash_file.name, recorded) if candidate.is_file()),
            None,
        )
        if trash_path is None:
            raise OSError(f'Le fichier de contrôle {trash_file.name} est dans la corbeille, mais son emplacement n’a pas pu être vérifié automatiquement.')
        if _sha256(trash_path) != expected_hash:
            raise OSError('Le contenu placé dans la corbeille ne correspond pas au fichier de contrôle.')
        trash_info = trash_path.parent.parent / 'info' / (trash_path.name + '.trashinfo')
        restored = root / 'restaure-de-la-corbeille.txt'
        shutil.move(str(trash_path), str(restored))
        trash_path = None
        if _sha256(restored) != expected_hash:
            raise OSError('Le contenu restauré depuis la corbeille est incorrect.')
        if trash_info.is_file():
            trash_info.unlink()
        trash_info = None
        restored.unlink()
        lines.append('RÉUSSI — mise à la corbeille, contenu vérifié, restauration et nettoyage')
        success = True
    except InterruptedError:
        lines.append('ANNULÉ — le contrôle a été interrompu ; les données de test vont être nettoyées.')
    except Exception as error:
        lines.append(f'ÉCHEC — {error}')
    finally:
        for leftover in (trash_path, trash_info):
            if leftover is not None:
                try:
                    Path(leftover).unlink(missing_ok=True)
                except OSError:
                    pass
        if root is not None:
            try:
                shutil.rmtree(root)
                lines.append('RÉUSSI — espace de test supprimé')
            except OSError as error:
                success = False
                lines.append(f'ÉCHEC — nettoyage incomplet : {error}')
        lines.append('Aucun fichier personnel n’a été utilisé.')
    return StabilityResult(success, '\n'.join(lines))
