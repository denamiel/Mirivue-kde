#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Règle GitHub (ruleset) qui rend les tests obligatoires avant toute intégration dans main.

  protection-main.py --verifier   lecture seule ; code 1 si la règle manque ou diffère
  protection-main.py --appliquer  crée ou met à jour uniquement la règle nommée
                                  « Mirivue — contrôles obligatoires »

Règle attendue sur la branche par défaut (main) :
  - passage obligatoire par une pull request (aucune approbation exigée : mainteneur unique) ;
  - contrôles obligatoires réussis, produits par GitHub Actions, branche à jour ;
  - ni suppression de main, ni réécriture de son historique ;
  - aucun contournement, y compris pour les administrateurs.

Les autres rulesets ne sont jamais modifiés ni supprimés. La publication reste
séparée : elle exige toujours un lancement manuel, la confirmation PUBLIER et
l'approbation dans l'environnement protégé.
"""
import json
import subprocess
import sys

REPOSITORY = 'denamiel/Mirivue-kde'
NAME = 'Mirivue — contrôles obligatoires'
GITHUB_ACTIONS_APP = 15368
# Check runs of the non-experimental jobs (Rawhide stays informative).
REQUIRED_CHECKS = (
    'RPM KDE Fedora 44',
    'RPM KDE Fedora 45',
    'Python 3.11 — imports et fichiers',
    'Python 3.x — imports et fichiers',
    'TestLab — vraie fenêtre sous Xvfb (Fedora 45)',
    'build',
)


def expected_ruleset():
    return {
        'name': NAME,
        'target': 'branch',
        'enforcement': 'active',
        'conditions': {'ref_name': {'include': ['~DEFAULT_BRANCH'], 'exclude': []}},
        'bypass_actors': [],
        'rules': [
            {'type': 'deletion'},
            {'type': 'non_fast_forward'},
            {'type': 'pull_request', 'parameters': {
                'required_approving_review_count': 0,
                'dismiss_stale_reviews_on_push': False,
                'require_code_owner_review': False,
                'require_last_push_approval': False,
                'required_review_thread_resolution': False,
            }},
            {'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': True,
                'required_status_checks': [{'context': name, 'integration_id': GITHUB_ACTIONS_APP}
                                           for name in REQUIRED_CHECKS],
            }},
        ],
    }


def analyse(ruleset):
    """Return the differences between a ruleset (GET JSON, or None) and the expected rule."""
    if ruleset is None:
        return ['règle absente : main n’exige aucun contrôle']
    problems = []
    if ruleset.get('enforcement') != 'active':
        problems.append(f"règle non appliquée (enforcement={ruleset.get('enforcement')})")
    if ruleset.get('target') != 'branch' or '~DEFAULT_BRANCH' not in (
            ruleset.get('conditions', {}).get('ref_name', {}).get('include', [])):
        problems.append('règle non ciblée sur la branche par défaut')
    if ruleset.get('bypass_actors'):
        problems.append('contournement autorisé : ' + ', '.join(
            f"{actor.get('actor_type')} {actor.get('actor_id')}" for actor in ruleset['bypass_actors']))
    rules = {rule.get('type'): rule.get('parameters', {}) for rule in ruleset.get('rules', [])}
    for kind in ('deletion', 'non_fast_forward', 'pull_request', 'required_status_checks'):
        if kind not in rules:
            problems.append(f'règle {kind} absente')
    checks = rules.get('required_status_checks', {})
    present = {(item.get('context'), item.get('integration_id'))
               for item in checks.get('required_status_checks', [])}
    missing = [name for name in REQUIRED_CHECKS if (name, GITHUB_ACTIONS_APP) not in present]
    if missing:
        problems.append('contrôles obligatoires manquants : ' + ', '.join(missing))
    if 'required_status_checks' in rules and not checks.get('strict_required_status_checks_policy'):
        problems.append('branche à jour non exigée avant fusion')
    return problems


def gh(*arguments, body=None):
    result = subprocess.run(['gh', 'api', *arguments], input=None if body is None else json.dumps(body),
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise LookupError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout or 'null')


def find():
    for summary in gh(f'repos/{REPOSITORY}/rulesets?includes_parents=false') or []:
        if summary.get('name') == NAME:
            return gh(f"repos/{REPOSITORY}/rulesets/{summary['id']}")
    return None


def main(argv):
    if len(argv) != 2 or argv[1] not in ('--verifier', '--appliquer'):
        print(__doc__.split('\n\n')[1], file=sys.stderr)
        return 2
    try:
        ruleset = find()
    except (LookupError, OSError) as error:
        print(f'Lecture impossible ({error}) ; rien n’a été modifié.', file=sys.stderr)
        return 2
    problems = analyse(ruleset)
    if problems and argv[1] == '--appliquer':
        if ruleset is None:
            gh('-X', 'POST', f'repos/{REPOSITORY}/rulesets', '--input', '-', body=expected_ruleset())
        else:
            gh('-X', 'PUT', f"repos/{REPOSITORY}/rulesets/{ruleset['id']}", '--input', '-', body=expected_ruleset())
        problems = analyse(find())
    if not problems:
        print(f'✔ {REPOSITORY} / main : {len(REQUIRED_CHECKS)} contrôles obligatoires, pull request exigée, '
              'aucun contournement')
        return 0
    print(f"✖ {REPOSITORY} / main : {' ; '.join(problems)}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
