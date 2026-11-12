#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Liste les fenêtres vues par KWin, SANS script KWin ni permission particulière.

Utilise l'interface publique de KWin pour KRunner (/WindowsRunner, org.kde.krunner1.Match)
puis org.kde.KWin.getWindowInfo, comme n'importe quelle application de la session.
Sortie : `TESTLAB-WIN pid=<pid|?> class=<classe> caption=<titre>` ; diagnostics `TESTLAB-ERR`.
"""
import json
import subprocess
import sys


def busctl(*args):
    r = subprocess.run(['busctl', '--user', '--json=short', *args], capture_output=True, text=True, timeout=15)
    return r.returncode, r.stdout, r.stderr


def fenetres(requetes):
    vues = {}
    for q in requetes:
        rc, out, err = busctl('call', 'org.kde.KWin', '/WindowsRunner', 'org.kde.krunner1', 'Match', 's', q)
        if rc:
            print(f'TESTLAB-ERR runner rc={rc} {err.strip()[:200]}')
            continue
        for item in json.loads(out)['data'][0]:
            identifiant, caption = item[0], item[1]
            uuid = identifiant.split('_', 1)[-1]
            if uuid in vues:
                continue
            pid, classe = '?', '?'
            rc, out2, err2 = busctl('call', 'org.kde.KWin', '/KWin', 'org.kde.KWin', 'getWindowInfo', 's', uuid)
            if rc == 0:
                info = json.loads(out2)['data'][0]
                valeur = lambda cle: (info.get(cle) or {}).get('data') if isinstance(info.get(cle), dict) else info.get(cle)
                pid = valeur('pid') if valeur('pid') is not None else '?'
                classe = valeur('resourceClass') or valeur('resourceName') or '?'
            else:
                print(f'TESTLAB-ERR getWindowInfo rc={rc} {err2.strip()[:160]}')
            vues[uuid] = (pid, classe, caption)
    for pid, classe, caption in vues.values():
        print(f'TESTLAB-WIN pid={pid} class={classe} caption={caption}')
    if not vues:
        print('TESTLAB-AUCUNE-FENETRE')


if __name__ == '__main__':
    fenetres(sys.argv[1:] or ['Mirivue'])
