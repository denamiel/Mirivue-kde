"""Validate real file operations on a disposable ext4 or NTFS3 mount."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from PySide6.QtWidgets import QApplication
from mirivue.platform_services import services

root = Path(os.environ['MIRIVUE_FILESYSTEM_ROOT'])
assert root.is_mount(), 'a mounted image is required'
app = QApplication(['Mirivue-filesystem-validation'])
with tempfile.TemporaryDirectory(prefix='mirivue-fs-', dir=root) as folder:
    work = Path(folder)
    for key, name in [('HOME', 'home'), ('XDG_CONFIG_HOME', 'config'),
                      ('XDG_DATA_HOME', 'data'), ('XDG_STATE_HOME', 'state'),
                      ('XDG_CACHE_HOME', 'cache')]:
        (work / name).mkdir()
        os.environ[key] = str(work / name)
    (work / 'config/kiorc').write_text('[Confirmations]\nConfirmTrash=false\nConfirmDelete=false\n')
    source, target = work / 'source', work / 'target'
    source.mkdir()
    target.mkdir()
    payload = bytes(range(256)) * 4096
    (source / 'été 日本.bin').write_bytes(payload)
    (source / 'photo ').write_bytes(b'SPACE')
    (source / 'photo').write_bytes(b'OTHER')
    (source / 'link').symlink_to('été 日本.bin')

    def manifest(folder):
        return {str(p.relative_to(folder)): ('link', os.readlink(p)) if p.is_symlink()
                else ('directory',) if p.is_dir()
                else ('file', hashlib.sha256(p.read_bytes()).hexdigest())
                for p in folder.rglob('*')}

    expected = manifest(source)

    def request(command, paths, destination='', cancelled=None):
        return services._kio_service_request(command,
            sources=[p.as_uri() if isinstance(p, Path) else p for p in paths],
            destination=destination.as_uri() if isinstance(destination, Path) else destination,
            cancelled=cancelled, timeout=15)

    try:
        ok, error = request('copy', [source], target)
        assert ok, error
        assert manifest(source) == expected
        copied = target / 'source'
        assert manifest(copied) == expected
        moved = work / 'moved'
        moved.mkdir()
        ok, error = request('move', [copied], moved)
        assert ok, error
        assert not copied.exists()
        assert manifest(moved / 'source') == expected

        collision = moved / 'source/photo'
        collision.write_bytes(b'DESTINATION')
        started = time.monotonic()
        ok, error = request('copy', [source / 'photo'], moved / 'source',
                            cancelled=lambda: time.monotonic() - started > 0.8)
        assert not ok, 'collision unexpectedly accepted'
        assert collision.read_bytes() == b'DESTINATION'
        assert (source / 'photo').read_bytes() == b'OTHER'

        victim = source / 'photo '
        ok, error = request('trash', [victim])
        assert ok, error
        assert not victim.exists()
        assert (source / 'photo').read_bytes() == b'OTHER'
        listed = subprocess.run([services.tool_path('mirivue-kio-list'), 'trash:/'],
                                capture_output=True, text=True, timeout=15, check=True)
        entries = json.loads(listed.stdout.splitlines()[-1])['entries']
        uri = next(e['url'] for e in entries if e['name'] == 'photo ')
        ok, error = request('restore', [uri])
        assert ok, error
        assert victim.read_bytes() == b'SPACE'

        link = source / 'link'
        ok, error = request('trash', [link])
        assert ok, error
        assert not link.is_symlink()
        assert (source / 'été 日本.bin').read_bytes() == payload
        print(json.dumps(dict(filesystem=os.environ['MIRIVUE_FILESYSTEM_TYPE'],
                             copy=True, move=True, conflict_cancel=True, trash_restore=True,
                             exact_name=True, symlink_target_preserved=True)))
    finally:
        services.shutdown_kio_service()
