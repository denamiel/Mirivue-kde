# SPDX-License-Identifier: MIT
"""Run the real validator shell with disposable build/test command substitutes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestValidationDiagnostics(unittest.TestCase):
    def run_validator(self, mode):
        with tempfile.TemporaryDirectory(prefix='mirivue-validator-proof-') as temporary:
            root=Path(temporary); commands=root/'bin'; commands.mkdir()
            validator=next(ROOT.glob('Valider-RC*.sh')).read_text()
            # Select a test-only interpreter; production keeps /usr/bin/python3.
            validator=validator.replace('python=/usr/bin/python3', 'python="'+str(commands/'python-test')+'"')
            script=root/'Valider.sh'; script.write_text(validator)
            programs={
                'cmake':'#!/bin/sh\nif [ "$CASE" = build ]; then echo COMPILER_DETAIL >&2; exit 7; fi\nexit 0\n',
                'dbus-run-session':'#!/bin/sh\n[ "$1" = -- ] && shift\nexec "$@"\n',
                'python-test':'''#!/bin/sh
if [ "$1" = -c ]; then exit 0; fi
if [ "$1" = -m ]; then
 echo 'test_failure (Example) ... ERROR'
 echo 'Traceback (most recent call last):'
 echo 'subprocess.TimeoutExpired: ORIGINAL_TIMEOUT_DETAIL'
 echo 'Ran 1 test in 0.01s'
 echo 'FAILED (errors=1)'
 exit 1
fi
exec /usr/bin/python3 "$@"
'''}
            for name,text in programs.items():
                path=commands/name;path.write_text(text);path.chmod(0o755)
            env=dict(os.environ,PATH=str(commands)+os.pathsep+os.environ['PATH'],CASE=mode,
                     MIRIVUE_VALIDATION_LOG_DIR=str(root/'saved'))
            result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True,timeout=15)
            logs={p.name:p.read_text() for p in (root/'saved').rglob('*.log')}
            return result,logs

    def test_failed_suite_keeps_full_timeout_and_exits_unsuccessfully(self):
        result,logs=self.run_validator('tests')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('tests.log',logs)
        self.assertIn('ORIGINAL_TIMEOUT_DETAIL',logs['tests.log'])
        self.assertIn('ORIGINAL_TIMEOUT_DETAIL',result.stdout+result.stderr)

    def test_failed_build_keeps_full_compiler_output(self):
        result,logs=self.run_validator('build')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('build.log',logs)
        self.assertIn('COMPILER_DETAIL',logs['build.log'])
