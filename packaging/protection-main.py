#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Règle GitHub (ruleset) qui rend les tests obligatoires avant toute intégration dans main.

  protection-main.py --verifier   lecture seule ; code 1 si la règle manque ou diffère
  protection-main.py --appliquer  crée la règle « Mirivue — contrôles obligatoires »
                                  seulement si elle est absente ET si chaque contrôle
                                  requis a réussi sur le dernier commit de main

Règle attendue sur la branche par défaut (main) :
  - passage obligatoire par une pull request (aucune approbation exigée : mainteneur unique) ;
  - contrôles obligatoires réussis, produits par GitHub Actions, branche à jour ;
  - ni suppression de main, ni réécriture de son historique ;
  - aucun contournement, y compris pour les administrateurs.

Sécurité : --appliquer ne remplace, ne modifie et ne supprime jamais une règle
existante. Si une règle du même nom existe et diffère, même par un paramètre
inconnu ou une contrainte plus stricte, il affiche chaque différence et refuse
d'agir : la correction se fait à la main dans Settings > Rules. Il refuse aussi
d'exiger un contrôle que main ne produit pas encore (TestLab avant la fusion de
la PR qui l'ajoute), ce qui bloquerait toutes les fusions.

Ordre d'intégration : fusionner la PR qui introduit les contrôles, vérifier
qu'ils réussissent sur main, puis seulement appliquer la règle.
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
# Reported on every PR but not yet required: the Wayland lab becomes mandatory
# once its CI runs are stable (docs/TESTLAB-WAYLAND.md).
INFORMATIVE_CHECKS = (
    'TestLab Wayland — KWin virtuel (Fedora 45)',
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
                # GitHub includes these canonical defaults in the GET response.
                # Keep them explicit rather than silently dropping any fields.
                'required_reviewers': [],
                'allowed_merge_methods': ['merge', 'squash', 'rebase'],
                'require_extra_approval_for_unattributed_changes': True,
                'require_code_owner_review': False,
                'require_last_push_approval': False,
                'required_review_thread_resolution': False,
            }},
            {'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': True,
                'do_not_enforce_on_create': False,
                'required_status_checks': [{'context': name, 'integration_id': GITHUB_ACTIONS_APP}
                                           for name in REQUIRED_CHECKS],
            }},
        ],
    }


def normalise(ruleset):
    """Keep every rule and every parameter, in a comparable order."""
    rules = {}
    for rule in ruleset.get('rules', []):
        parameters = dict(rule.get('parameters') or {})
        checks = parameters.get('required_status_checks')
        if isinstance(checks, list):
            parameters['required_status_checks'] = sorted(
                checks, key=lambda item: (str(item.get('context')), str(item.get('integration_id'))))
        rules.setdefault(str(rule.get('type')), []).append(parameters)
    return {
        'target': ruleset.get('target'),
        'enforcement': ruleset.get('enforcement'),
        'conditions': ruleset.get('conditions'),
        'bypass_actors': ruleset.get('bypass_actors') or [],
        'rules': rules,
    }


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def differences(ruleset):
    """Every field-by-field difference between an existing ruleset and the expected one."""
    actual, expected = normalise(ruleset), normalise(expected_ruleset())
    found = []
    for key in ('target', 'enforcement', 'conditions', 'bypass_actors'):
        if actual[key] != expected[key]:
            found.append(f'{key} : actuel {dump(actual[key])} ; attendu {dump(expected[key])}')
    for kind in sorted(set(actual['rules']) | set(expected['rules'])):
        have, want = actual['rules'].get(kind), expected['rules'].get(kind)
        if want is None:
            found.append(f'règle supplémentaire {kind} : {dump(have)}')
        elif have is None:
            found.append(f'règle {kind} absente')
        elif len(have) != 1:
            found.append(f'règle {kind} présente {len(have)} fois')
        elif have[0] != want[0]:
            for name in sorted(set(have[0]) | set(want[0])):
                if have[0].get(name) != want[0].get(name):
                    found.append(f'{kind}.{name} : actuel {dump(have[0].get(name))} ; attendu {dump(want[0].get(name))}')
    return found


def analyse(ruleset):
    """Problems of a ruleset (GET JSON, or None) against the expected rule."""
    if ruleset is None:
        return ['règle absente : main n’exige aucun contrôle']
    return differences(ruleset)


def missing_checks_on_main(check_runs):
    """Required contexts without a successful GitHub Actions run on main's head commit."""
    succeeded = {run.get('name') for run in check_runs
                 if (run.get('app') or {}).get('id') == GITHUB_ACTIONS_APP and run.get('conclusion') == 'success'}
    return [name for name in REQUIRED_CHECKS if name not in succeeded]


def decide(ruleset, check_runs):
    """What --appliquer may do: ('rien' | 'creer' | 'refuser', messages)."""
    problems = analyse(ruleset)
    if not problems:
        return 'rien', []
    if ruleset is not None:
        return 'refuser', ['une règle du même nom existe et diffère ; elle ne sera ni remplacée ni modifiée :',
                           *problems]
    missing = missing_checks_on_main(check_runs)
    if missing:
        return 'refuser', ['contrôles requis jamais réussis sur le dernier commit de main ; fusionner d’abord la '
                           'PR qui les introduit et vérifier la CI de main : ' + ', '.join(missing)]
    return 'creer', problems


def gh(*arguments, body=None):
    result = subprocess.run(['gh', 'api', *arguments], input=None if body is None else json.dumps(body),
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise LookupError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout or 'null')


def find():
    matches = [summary for summary in gh(f'repos/{REPOSITORY}/rulesets?includes_parents=false') or []
               if summary.get('name') == NAME]
    if len(matches) > 1:
        raise LookupError(f'{len(matches)} règles portent le nom « {NAME} » ; corrigez-les à la main.')
    return gh(f"repos/{REPOSITORY}/rulesets/{matches[0]['id']}") if matches else None


def main_check_runs():
    return (gh(f'repos/{REPOSITORY}/commits/main/check-runs?per_page=100') or {}).get('check_runs', [])


def main(argv):
    if len(argv) != 2 or argv[1] not in ('--verifier', '--appliquer'):
        print(__doc__.split('\n\n')[1], file=sys.stderr)
        return 2
    try:
        ruleset, check_runs = find(), main_check_runs()
    except (LookupError, OSError) as error:
        print(f'Lecture impossible ({error}) ; rien n’a été modifié.', file=sys.stderr)
        return 2
    missing = missing_checks_on_main(check_runs)
    if missing:
        print('ℹ contrôles requis sans réussite sur le dernier commit de main : ' + ', '.join(missing))
    if argv[1] == '--verifier':
        problems = analyse(ruleset)
        if not problems:
            print(f'✔ {REPOSITORY} / main : règle conforme ({len(REQUIRED_CHECKS)} contrôles obligatoires)')
            return 0
        print(f'✖ {REPOSITORY} / main :\n  ' + '\n  '.join(problems))
        return 1
    action, messages = decide(ruleset, check_runs)
    if action == 'rien':
        print(f'✔ {REPOSITORY} / main : règle déjà conforme ; rien n’a été modifié')
        return 0
    if action == 'refuser':
        print('✖ Refus :\n  ' + '\n  '.join(messages) + '\n  Rien n’a été modifié.')
        return 1
    gh('-X', 'POST', f'repos/{REPOSITORY}/rulesets', '--input', '-', body=expected_ruleset())
    problems = analyse(find())
    if problems:
        print('✖ Règle créée mais différente de l’attendu :\n  ' + '\n  '.join(problems))
        return 1
    print(f'✔ {REPOSITORY} / main : règle créée ({len(REQUIRED_CHECKS)} contrôles obligatoires)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
