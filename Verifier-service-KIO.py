#!/usr/bin/env python3
"""Check Mirivue's installed KIO service with a disposable Trash job."""

import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import uuid


def verify(helper: Path, root: Path) -> None:
    data = root / 'kio-data'
    home = root / 'kio-home'
    source = data / 'source' / 'essai-kio.txt'
    source.parent.mkdir(parents=True)
    home.mkdir()
    source.write_text('essai jetable\n', encoding='utf-8')
    input_path = root / 'kio-service.in'
    output_path = root / 'kio-service.out'
    os.mkfifo(input_path, 0o600)
    os.mkfifo(output_path, 0o600)
    environment = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(data),
                       XDG_CONFIG_HOME=str(root / 'kio-config'),
                       XDG_CACHE_HOME=str(root / 'kio-cache'),
                       XDG_STATE_HOME=str(root / 'kio-state'),
                       QT_QPA_PLATFORM='offscreen')
    request_id = uuid.uuid4().hex
    with (open(input_path, 'r+b', buffering=0) as writer,
          open(output_path, 'r+b', buffering=0) as reader,
          open(root / 'kio-service.log', 'w+b') as errors):
        os.set_blocking(reader.fileno(), False)
        process = subprocess.Popen([str(helper), '--service', str(input_path), str(output_path)],
                                   env=environment, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=errors)
        try:
            request = {'command': 'trash', 'id': request_id,
                       'sources': [source.as_uri()]}
            writer.write((json.dumps(request) + '\n').encode('utf-8'))
            buffer = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(reader, selectors.EVENT_READ)
                deadline = time.monotonic() + 25
                result = None
                while result is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError('le service KIO n’a pas répondu en 25 s ; '
                                           'vérifier si une confirmation KDE attend une réponse')
                    if process.poll() is not None:
                        raise RuntimeError(f'le service KIO s’est arrêté (code {process.returncode})')
                    if not selector.select(timeout=min(remaining, 0.2)):
                        continue
                    buffer.extend(os.read(reader.fileno(), 65536))
                    while b'\n' in buffer:
                        line, _, tail = buffer.partition(b'\n')
                        buffer = bytearray(tail)
                        event = json.loads(line)
                        if event.get('event') == 'complete' and event.get('id') == request_id:
                            result = event
                            break
            if not result.get('ok'):
                raise RuntimeError('DeleteOrTrashJob : ' + str(result.get('error', 'échec inconnu')))
            if source.exists():
                raise RuntimeError('la source existe encore après la mise à la corbeille KIO')
            if not (data / 'Trash' / 'files' / source.name).is_file():
                raise RuntimeError('le fichier est absent de la corbeille de test isolée')
            writer.write((json.dumps({'command': 'shutdown', 'id': uuid.uuid4().hex}) + '\n').encode())
            process.wait(timeout=3)
            print('RÉUSSI — service KIO et DeleteOrTrashJob vérifiés sur un fichier jetable')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    try:
        verify(Path(sys.argv[1]), Path(sys.argv[2]))
    except (OSError, RuntimeError, ValueError) as error:
        print(f'ÉCHEC — vérification du service KIO : {error}', file=sys.stderr)
        sys.exit(1)
