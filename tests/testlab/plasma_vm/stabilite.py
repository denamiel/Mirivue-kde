#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Mesure la stabilité du TestLab Plasma VM à partir des exécutions GitHub réelles.

Protocole (à faire relire ; le seuil n'est pas un jugement de ce script) :
- Un « essai » est un job `vm-mirivue` (un essai de la matrice). Il est COMPTÉ s'il a atteint
  l'étape « Démarrer l'invité » ; un échec avant cette étape (récupération de l'image, cache,
  dépôt RPM, checkout) est une panne d'INFRASTRUCTURE : exclue du taux, mais rapportée.
- Une « exécution indépendante » est une exécution du workflow espacée d'au moins
  `--espacement-h` heures de la précédente retenue (sélection gloutonne par date). Les essais
  parallèles d'une même exécution, et les exécutions rapprochées, ne sont PAS indépendants.
- Seuil par défaut : au moins 30 essais comptés issus d'exécutions indépendantes, sur au moins
  24 h, SANS aucun échec du TestLab (règle de trois : 0 échec sur 30 ⇒ taux < 10 % à 95 %).
  Tout échec du TestLab doit être analysé individuellement avant de conclure.
Sans données suffisantes, le verdict est « INSUFFISANT », jamais « stable ».
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta

WORKFLOW = 'testlab-plasma-vm.yml'
PREFIXE_ESSAI = 'VM Fedora KDE — Mirivue RPM'
ETAPE_INVITE = "Démarrer l'invité"


def _date(texte):
    return datetime.fromisoformat(texte.replace('Z', '+00:00'))


def classer_essai(job):
    """'ok' | 'echec_testlab' | 'infra' | 'ignore' (annulé, non terminé, hors périmètre)."""
    if not job['name'].startswith(PREFIXE_ESSAI):
        return 'ignore'
    if job.get('conclusion') == 'success':
        return 'ok'
    if job.get('conclusion') != 'failure':
        return 'ignore'
    for etape in job.get('steps', []):
        if etape['name'].startswith(ETAPE_INVITE):
            return 'echec_testlab' if etape.get('conclusion') == 'failure' else 'infra'
    return 'infra'


def selectionner_independantes(executions, espacement_h):
    retenues, derniere = [], None
    for e in sorted(executions, key=lambda x: x['created_at']):
        debut = _date(e['created_at'])
        if derniere is None or debut - derniere >= timedelta(hours=espacement_h):
            retenues.append(e['id'])
            derniere = debut
    return set(retenues)


def evaluer(executions, espacement_h=2.0, min_essais=30, min_duree_h=24.0):
    """`executions` : [{id, created_at, head_sha, jobs:[{name, conclusion, steps}]}]."""
    independantes = selectionner_independantes(executions, espacement_h)
    bilan = {'executions_total': len(executions), 'executions_independantes': len(independantes),
             'essais_comptes': 0, 'ok': 0, 'echecs_testlab': [], 'pannes_infra': [], 'dates': []}
    for e in sorted(executions, key=lambda x: x['created_at']):
        if e['id'] not in independantes:
            continue
        bilan['dates'].append(e['created_at'])
        for job in e['jobs']:
            classe = classer_essai(job)
            ref = {'run': e['id'], 'sha': e['head_sha'][:7], 'job': job['name']}
            if classe == 'ok':
                bilan['ok'] += 1
                bilan['essais_comptes'] += 1
            elif classe == 'echec_testlab':
                bilan['echecs_testlab'].append(ref)
                bilan['essais_comptes'] += 1
            elif classe == 'infra':
                bilan['pannes_infra'].append(ref)
    dates = [_date(d) for d in bilan['dates']]
    bilan['duree_h'] = round((max(dates) - min(dates)).total_seconds() / 3600, 1) if dates else 0.0
    manques = []
    if bilan['essais_comptes'] < min_essais:
        manques.append(f"{bilan['essais_comptes']} essai(s) compté(s) < {min_essais}")
    if bilan['duree_h'] < min_duree_h:
        manques.append(f"étalement {bilan['duree_h']} h < {min_duree_h} h")
    if bilan['echecs_testlab']:
        verdict = 'INSTABLE : échec(s) du TestLab à analyser'
    elif manques:
        verdict = 'INSUFFISANT : ' + '; '.join(manques)
    else:
        verdict = 'SEUIL ATTEINT (revue indépendante requise avant toute promotion)'
    bilan['verdict'] = verdict
    return bilan


def _gh(chemin):
    r = subprocess.run(['gh', 'api', chemin], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def collecter(depot, depuis):
    runs = _gh(f'repos/{depot}/actions/workflows/{WORKFLOW}/runs?per_page=100')['workflow_runs']
    sortie = []
    for r in runs:
        if r['status'] != 'completed' or r['created_at'] < depuis:
            continue
        jobs = _gh(f"repos/{depot}/actions/runs/{r['id']}/jobs?per_page=100")['jobs']
        sortie.append({'id': r['id'], 'created_at': r['created_at'], 'head_sha': r['head_sha'], 'jobs': jobs})
    return sortie


def main(arguments=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--depot', default='denamiel/Mirivue-kde')
    a.add_argument('--depuis', default='2026-11-11T16:00:00Z',
                   help='date ISO de la première exécution du scénario Mirivue complet (1f19f7a)')
    a.add_argument('--espacement-h', type=float, default=2.0)
    a.add_argument('--min-essais', type=int, default=30)
    a.add_argument('--min-duree-h', type=float, default=24.0)
    a.add_argument('--json', type=argparse.FileType('r'), help='données déjà collectées (sinon : API GitHub via gh)')
    o = a.parse_args(arguments)
    executions = json.load(o.json) if o.json else collecter(o.depot, o.depuis)
    b = evaluer(executions, o.espacement_h, o.min_essais, o.min_duree_h)
    print(json.dumps(b, indent=2, ensure_ascii=False))
    return 0 if b['verdict'].startswith(('INSUFFISANT', 'SEUIL')) else 1


if __name__ == '__main__':
    sys.exit(main())
