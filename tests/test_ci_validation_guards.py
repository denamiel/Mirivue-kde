"""A failing container must not become a green validation through tee."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class TestValidationFailuresRemainRed(unittest.TestCase):
    def test_image_validation_propagates_container_failure(self):
        workflow = yaml.safe_load((ROOT / '.github/workflows/fedora-package.yml').read_text())
        step = next(s for s in workflow['jobs']['fichiers-images']['steps']
                    if s.get('name', '').startswith('Copie, déplacement'))
        with tempfile.TemporaryDirectory(prefix='mirivue-ci-guard-') as folder:
            work = Path(folder)
            (work / 'fichiers-images-artefacts').mkdir()
            fake_bin = work / 'bin'
            fake_bin.mkdir()
            docker = fake_bin / 'docker'
            docker.write_text('#!/bin/sh\necho synthetic-container-failure\nexit 23\n')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.defpath,
                       RUNNER_TEMP=folder, TEST_FS='ext4')
            result = subprocess.run(['bash', '-e', '-c', step['run']], cwd=work, env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertIn('synthetic-container-failure', result.stdout)
            self.assertEqual(result.returncode, 23, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
