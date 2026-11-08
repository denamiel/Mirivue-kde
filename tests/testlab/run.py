#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one TestLab scenario against the installed (or source) application.

Exit codes: 0 success, 1 scenario failure, 2 environment unavailable,
3 cleanup or isolation failure. Reports: <artefacts>/rapport.json and junit.xml.
"""
import argparse
import os
from pathlib import Path
import shutil
import signal
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from testlab.harness import Lab, markdown_summary  # noqa: E402
from testlab.scenarios import SCENARIOS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def application_command(choice):
    if choice == 'installee':
        if shutil.which('mirivue-kde') is None:
            raise SystemExit('mirivue-kde n’est pas installé ; utiliser --application sources.')
        return ['mirivue-kde'], None, {}
    # Source tree: the native helpers are expected in <dépôt>/tools.
    return [sys.executable, '-m', 'mirivue'], str(ROOT), {'PYTHONPATH': str(ROOT)}


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scenario', choices=sorted(SCENARIOS))
    parser.add_argument('--artefacts', required=True, type=Path)
    parser.add_argument('--application', choices=('installee', 'sources'), default='installee')
    parser.add_argument('--delai', type=float, default=180.0, help='délai maximal du scénario (s)')
    parser.add_argument('--surveiller', action='append', type=Path, default=None,
                        help='chemin supplémentaire qui doit rester inchangé (répétable)')
    options = parser.parse_args(arguments)
    if options.artefacts.exists() and any(options.artefacts.iterdir()):
        parser.error(f'le dossier d’artefacts doit être vide : {options.artefacts}')
    command, cwd, extra = application_command(options.application)
    lab = Lab(options.scenario, options.artefacts, app=command, timeout=options.delai,
              launch_cwd=cwd, extra_environment=extra)
    if options.surveiller:
        lab.watch += [str(path.resolve()) for path in options.surveiller]

    # Last resort if the harness itself blocks: raise inside the run so the
    # cleanup still executes.
    def expired(_signal, _frame):
        raise TimeoutError('Délai de sécurité du harness dépassé.')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(int(options.delai) + 120)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('SIGTERM')))
    code = lab.run(SCENARIOS[options.scenario][0])
    signal.alarm(0)
    summary = markdown_summary(lab.report)
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write(summary + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
