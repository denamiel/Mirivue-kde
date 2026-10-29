import errno
import os
from pathlib import Path
import shutil
import struct
import tempfile
import zlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from support.stability import (
    _create_archive_samples,
    run_archive_stability_check, run_cross_volume_check, run_deletion_stability_check,
    run_failure_recovery_check,
    run_large_folder_stability_check, run_multimedia_stability_check,
    run_stability_check, tree_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def transfer(source, target, cancelled=lambda: False, progress=lambda text: None, copy_only=False):
    source, target = Path(source), Path(target)
    if target.exists() or target.is_symlink():
        raise FileExistsError(errno.EEXIST, 'exists', str(target))
    if cancelled():
        raise InterruptedError()
    if copy_only:
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)
    else:
        source.rename(target)


class TestStabilityCheck(unittest.TestCase):
    def test_real_rar_sample_has_valid_header_and_file_crc(self):
        with tempfile.TemporaryDirectory() as temporary:
            archives, _ = _create_archive_samples(Path(temporary))
            data = archives['RAR'].read_bytes()
            self.assertTrue(data.startswith(b'Rar!\x1a\x07\x00'))
            offset = 7
            while offset < len(data):
                crc, kind, flags, size = struct.unpack_from('<HBHH', data, offset)
                self.assertEqual(crc, zlib.crc32(data[offset + 2:offset + size]) & 0xffff)
                if kind == 0x74:
                    packed_size, unpacked_size, _host, file_crc = struct.unpack_from('<IIBI', data, offset + 7)
                    self.assertEqual(packed_size, unpacked_size)
                    self.assertEqual(file_crc, zlib.crc32(data[offset + size:offset + size + packed_size]))
                    return
                offset += size
            self.fail('En-tête du fichier RAR absent')

    def test_manifest_preserves_empty_hidden_unicode_and_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.caché').write_bytes(b'')
            (root / 'Été_日本.txt').write_text('été', encoding='utf-8')
            os.symlink('Été_日本.txt', root / 'lien')
            manifest = tree_manifest(root)
            self.assertEqual(manifest['.caché'][1][0], 0)
            self.assertEqual(manifest['lien'], ('link', 'Été_日本.txt'))
            self.assertEqual(manifest['Été_日本.txt'][0], 'file')

    def test_complete_check_cleans_its_unique_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'fichier personnel simulé.txt'
            sentinel.write_text('ne pas toucher', encoding='utf-8')
            result = run_stability_check(base, transfer=transfer)
            self.assertTrue(result.success, result.report)
            self.assertIn('conflit de nom refusé', result.report)
            self.assertIn('espace de test supprimé', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'ne pas toucher')

    def test_cancelled_check_also_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            result = run_stability_check(base, cancelled=lambda: True, transfer=transfer)
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-*')))

    def test_release_does_not_import_development_validation_module(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn("help_menu.addAction(tr('Tester", source)
        self.assertNotIn('from .stability import', source)
        self.assertFalse((ROOT / 'mirivue' / 'stability.py').exists())
        self.assertTrue((ROOT / 'tests' / 'support' / 'stability.py').is_file())

    def test_cross_volume_check_moves_both_ways_and_cleans_both_roots(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_base, second_base = Path(first), Path(second)
            first_sentinel = first_base / 'personnel-1.txt'
            second_sentinel = second_base / 'personnel-2.txt'
            first_sentinel.write_text('un', encoding='utf-8')
            second_sentinel.write_text('deux', encoding='utf-8')
            result = run_cross_volume_check(
                first_base, second_base, transfer=transfer, device_ids=(1, 2),
            )
            self.assertTrue(result.success, result.report)
            self.assertIn('source supprimée après vérification', result.report)
            self.assertEqual(result.report.count('source supprimée après vérification'), 2)
            self.assertFalse(list(first_base.glob('Mirivue-validation-croisee-*')))
            self.assertFalse(list(second_base.glob('Mirivue-validation-croisee-*')))
            self.assertEqual(first_sentinel.read_text(encoding='utf-8'), 'un')
            self.assertEqual(second_sentinel.read_text(encoding='utf-8'), 'deux')

    def test_cross_volume_check_refuses_one_device(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = run_cross_volume_check(first, second, transfer=transfer, device_ids=(1, 1))
            self.assertFalse(result.success)
            self.assertIn('même système de fichiers', result.report)
            self.assertFalse(list(Path(first).glob('Mirivue-validation-croisee-*')))
            self.assertFalse(list(Path(second).glob('Mirivue-validation-croisee-*')))

    def test_cancelled_cross_volume_check_cleans_both_roots(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = run_cross_volume_check(
                first, second, cancelled=lambda: True, transfer=transfer, device_ids=(1, 2),
            )
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(Path(first).glob('Mirivue-validation-croisee-*')))
            self.assertFalse(list(Path(second).glob('Mirivue-validation-croisee-*')))

    def test_failure_recovery_check_preserves_sources_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'fichier personnel simulé.txt'
            sentinel.write_text('ne pas toucher', encoding='utf-8')
            calls = []

            def faulting_transfer(source, target, cancelled=lambda: False,
                                  progress=lambda text: None, copy_only=False,
                                  bytes_progress=lambda done, total: None):
                staging = Path(tempfile.mkdtemp(prefix='.mirivue-deplacement-', dir=Path(target).parent))
                try:
                    partial = staging / Path(source).name
                    partial.write_bytes(Path(source).read_bytes()[:1024])
                    calls.append(Path(source).name)
                    bytes_progress(1024, Path(source).stat().st_size * 2)
                finally:
                    shutil.rmtree(staging, ignore_errors=True)

            result = run_failure_recovery_check(base, transfer=faulting_transfer)
            self.assertTrue(result.success, result.report)
            self.assertEqual(len(calls), 3)
            self.assertIn('espace insuffisant simulé', result.report)
            self.assertIn('destination protégée simulée', result.report)
            self.assertIn('retrait de périphérique simulé', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-incidents-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'ne pas toucher')

    def test_cancelled_failure_recovery_check_cleans_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            result = run_failure_recovery_check(base, cancelled=lambda: True, transfer=lambda *args, **kwargs: None)
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-incidents-*')))

    def test_archive_check_validates_four_formats_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'personnel.txt'
            sentinel.write_text('intact', encoding='utf-8')

            def samples(root):
                archives, manifests = {}, {}
                for label in ('ZIP', '7z', 'RAR', 'TAR'):
                    archive = root / ('controle.' + label.casefold())
                    archive.write_bytes(label.encode())
                    expected = root / ('attendu-' + label.casefold())
                    expected.mkdir()
                    (expected / 'texte.txt').write_text(label, encoding='utf-8')
                    archives[label] = archive
                    manifests[label] = tree_manifest(expected)
                return archives, manifests

            def extractor(archive, destination, cancelled, progress):
                if archive.name == 'archive-corrompue.zip':
                    return False, 'archive corrompue'
                if cancelled():
                    return False, 'annulé'
                label = {'zip': 'ZIP', '7z': '7z', 'rar': 'RAR', 'tar': 'TAR'}[archive.suffix.lstrip('.')]
                if (destination / 'texte.txt').exists():
                    return False, 'conflit'
                (destination / 'texte.txt').write_text(label, encoding='utf-8')
                progress(0)
                progress(100)
                return True, ''

            with patch('support.stability._create_archive_samples', side_effect=samples):
                result = run_archive_stability_check(base, extractor)
            self.assertTrue(result.success, result.report)
            self.assertEqual(result.report.count('contenus vérifiés et progression affichée'), 4)
            self.assertIn('conflit de nom RAR refusé', result.report)
            self.assertIn('extraction annulée sans contenu résiduel', result.report)
            self.assertIn('archive corrompue refusée', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-archives-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'intact')

    def test_cancelled_archive_check_cleans_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            archive = base / 'factice.zip'
            archive.write_bytes(b'x')
            with patch('support.stability._create_archive_samples', return_value=({'ZIP': archive}, {'ZIP': {}})):
                result = run_archive_stability_check(
                    base, lambda *args: (False, ''), cancelled=lambda: True,
                )
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-archives-*')))

    def test_multimedia_validation_covers_metadata_decode_corruption_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'personnel.txt'
            sentinel.write_text('intact', encoding='utf-8')
            progress = []

            def samples(root, cancelled):
                result = []
                for label, kind, suffix in (
                    ('WAV / PCM', 'audio', '.wav'),
                    ('FLAC', 'audio', '.flac'),
                    ('MP3', 'audio', '.mp3'),
                    ('MP4 / MPEG-4 + AAC', 'video', '.mp4'),
                    ('MKV / FFV1 + FLAC', 'video', '.mkv'),
                ):
                    path = root / ('controle-' + label.split()[0].casefold() + suffix)
                    path.write_bytes(label.encode())
                    result.append((label, kind, path))
                return result

            def inspect_sample(path, cancelled):
                kind = 'video' if path.suffix in ('.mp4', '.mkv') else 'audio'
                return SimpleNamespace(
                    media_type=kind, sort_values=[-1, -1, 1.2],
                    media_technical={'width': 320, 'height': 180} if kind == 'video' else {},
                )

            def decode(path, cancelled):
                return (path.name != 'media-corrompu.mp4', 'corrompu')

            result = run_multimedia_stability_check(
                base, progress=lambda current, total, message: progress.append((current, total, message)),
                sample_factory=samples, inspector=inspect_sample, decoder=decode,
            )
            self.assertTrue(result.success, result.report)
            self.assertEqual(result.report.count('métadonnées, durée et décodage complet vérifiés'), 5)
            self.assertIn('média corrompu refusé', result.report)
            self.assertIn('espace de test supprimé', result.report)
            self.assertEqual(progress[-1][:2], (6, 6))
            self.assertFalse(list(base.glob('Mirivue-validation-multimedia-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'intact')

    def test_cancelled_multimedia_validation_cleans_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            result = run_multimedia_stability_check(
                base, cancelled=lambda: True,
                sample_factory=lambda root, cancelled: (_ for _ in ()).throw(InterruptedError()),
                inspector=lambda *args: None, decoder=lambda *args: (False, ''),
            )
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-multimedia-*')))

    def test_large_folder_check_validates_listing_sort_search_memory_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'personnel.txt'
            sentinel.write_text('intact', encoding='utf-8')

            def build(path, is_dir=False):
                return SimpleNamespace(path=Path(path), is_dir=is_dir)

            def natural(name):
                import re
                return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', name)]

            result = run_large_folder_stability_check(
                base, entry_builder=build, sort_key=natural,
                file_count=1100, directory_count=20,
            )
            self.assertTrue(result.success, result.report)
            self.assertIn('inventaire complet : 1120 éléments', result.report)
            self.assertIn('tri naturel cohérent', result.report)
            self.assertIn('recherche exacte', result.report)
            self.assertIn('pic mémoire', result.report)
            self.assertIn('espace de test supprimé', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-grand-dossier-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'intact')

    def test_cancelled_large_folder_check_cleans_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            result = run_large_folder_stability_check(
                base, cancelled=lambda: True,
                entry_builder=lambda path, is_dir=False: SimpleNamespace(path=Path(path)),
                sort_key=lambda name: name,
                file_count=10, directory_count=1,
            )
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-grand-dossier-*')))

    def test_deletion_check_uses_only_isolated_files_and_cleans_trash(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / 'personnel.txt'
            sentinel.write_text('intact', encoding='utf-8')
            trash_files = base / '.fausse-corbeille' / 'files'
            trash_info = base / '.fausse-corbeille' / 'info'
            trash_files.mkdir(parents=True)
            trash_info.mkdir(parents=True)

            def remover(paths, mode, cancelled, progress):
                removed, errors, locations = set(), [], {}
                for path in map(Path, paths):
                    progress(path)
                    if mode == 'permanent':
                        path.unlink()
                    else:
                        target = trash_files / path.name
                        shutil.move(path, target)
                        (trash_info / (path.name + '.trashinfo')).write_text('[Trash Info]\n', encoding='utf-8')
                        locations[path] = target
                    removed.add(path)
                return removed, errors, locations

            result = run_deletion_stability_check(base, remover)
            self.assertTrue(result.success, result.report)
            self.assertIn('suppression définitive limitée', result.report)
            self.assertIn('mise à la corbeille, contenu vérifié, restauration et nettoyage', result.report)
            self.assertFalse(any(trash_files.iterdir()))
            self.assertFalse(any(trash_info.iterdir()))
            self.assertFalse(list(base.glob('Mirivue-validation-suppressions-*')))
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'intact')

    def test_cancelled_deletion_check_cleans_root(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            result = run_deletion_stability_check(
                base, lambda *args: (set(), [], {}), cancelled=lambda: True,
            )
            self.assertFalse(result.success)
            self.assertIn('ANNULÉ', result.report)
            self.assertFalse(list(base.glob('Mirivue-validation-suppressions-*')))


if __name__ == '__main__':
    unittest.main()
