# SPDX-License-Identifier: MIT
"""Stand-in application for the TestLab harness tests (no Qt, no display).

Usage: testlab_fake_application.py MODE REPORT [TARGET]
  succes  write the environment to REPORT, a marker in $HOME and exit 0
  echec   write the environment and exit 3
  bloque  start a detached child that ignores SIGTERM, then sleep forever
  ecrit   try to write into TARGET (outside the disposable root) and record
          whether the write succeeded
REPORT lives inside the disposable root, which the application may write.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

mode, report = sys.argv[1], Path(sys.argv[2])
keys = ('HOME', 'TMPDIR', 'DBUS_SESSION_BUS_ADDRESS', 'QT_QPA_PLATFORM', 'XDG_CONFIG_HOME',
        'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'XDG_RUNTIME_DIR', 'DISPLAY')
result = {key: os.environ.get(key) for key in keys}
result['uid'] = os.getuid()
Path(os.environ['HOME'], 'marqueur-testlab').write_text('jetable\n', encoding='utf-8')
if mode == 'ecrit':
    try:
        Path(sys.argv[3]).write_text('écriture interdite\n', encoding='utf-8')
        result['ecriture'] = 'ok'
    except OSError as error:
        result['ecriture'] = f'refusée : {type(error).__name__}'
report.write_text(json.dumps(result), encoding='utf-8')
if mode in ('succes', 'ecrit'):
    sys.exit(0)
if mode == 'echec':
    print('échec simulé', file=sys.stderr)
    sys.exit(3)
if mode == 'bloque':
    child = subprocess.Popen(
        [sys.executable, '-c',
         'import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: time.sleep(1)'],
        start_new_session=True)
    Path(str(report) + '.enfant').write_text(str(child.pid), encoding='utf-8')
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(1)
sys.exit(f'mode inconnu : {mode}')
