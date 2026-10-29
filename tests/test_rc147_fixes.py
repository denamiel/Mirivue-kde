"""Exercise colon-bearing paths and the service verifier's FIFO protocol."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestReleaseFixes(unittest.TestCase):
    def test_launcher_resolves_existing_colon_folder_before_url_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'Saison:2').mkdir()
            result = subprocess.run(
                ['bash', '-x', str(ROOT / 'Lancer.sh'), '--version', 'Saison:2'],
                cwd=folder, capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(str(folder / 'Saison:2'), result.stderr)

    def test_service_verifier_uses_trash_request_and_isolated_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / 'fake-service'
            helper.write_text('''#!/usr/bin/env python3
import json, os, pathlib, shutil, sys
assert sys.argv[1] == '--service'
with open(sys.argv[2], 'r+b', buffering=0) as incoming, open(sys.argv[3], 'r+b', buffering=0) as outgoing:
    request = json.loads(incoming.readline())
    assert request['command'] == 'trash' and request['id']
    source = pathlib.Path(request['sources'][0].removeprefix('file://'))
    assert source.is_file() and source.parent.parent == pathlib.Path(os.environ['XDG_DATA_HOME'])
    destination = pathlib.Path(os.environ['XDG_DATA_HOME']) / 'Trash/files' / source.name
    destination.parent.mkdir(parents=True)
    shutil.move(source, destination)
    outgoing.write((json.dumps({'event': 'complete', 'id': request['id'], 'ok': True}) + '\\n').encode())
    assert json.loads(incoming.readline())['command'] == 'shutdown'
''')
            helper.chmod(0o755)
            result = subprocess.run(
                [os.environ.get('PYTHON', '/usr/bin/python3'),
                 str(ROOT / 'Verifier-service-KIO.py'), str(helper), str(root / 'test')],
                capture_output=True, text=True, timeout=35,
            )
            # The harness needs an existing temporary root, as provided by
            # Verifier-installation-RC193.sh.
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('DeleteOrTrashJob vérifiés', result.stdout)


if __name__ == '__main__':
    unittest.main()
