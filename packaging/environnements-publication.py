#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Environnements GitHub qui protègent chaque publication de Mirivue.

  environnements-publication.py --verifier   lecture seule ; code 1 si non conforme
  environnements-publication.py --appliquer  crée un environnement absent ou complète
                                             un environnement sûr ; refuse sinon

Règle attendue : publication automatique après qualification, déploiement limité à
la branche main, aucun délai ni approbation manuelle supplémentaire,
aucun contournement par les administrateurs.

--appliquer ne supprime jamais rien : s'il trouve d'autres approbateurs ou
d'autres règles de branche ou de tag, il les liste et refuse d'agir.
"""
import json
from pathlib import Path
import subprocess
import sys

TARGETS = (
    ('denamiel/Mirivue-kde', 'publication-copr'),
    ('denamiel/Mirivue-kde', 'publication-arch'),
    ('denamiel/mirivue-arch', 'publication-pacman'),
)


def analyse(environment, branch_policies, maintainer_id):
    """Return (blocking problems, problems --appliquer may fix) for one environment.

    environment: GET /environments/{name} JSON, or None when absent.
    branch_policies: GET .../deployment-branch-policies JSON (or None).
    """
    if environment is None:
        return [], ['environnement absent']
    blocking, fixable = [], []
    rules = {rule.get('type'): rule for rule in environment.get('protection_rules', [])}
    reviewers = rules.get('required_reviewers', {}).get('reviewers', [])
    others = [f"{item.get('type')} {item.get('reviewer', {}).get('login') or item.get('reviewer', {}).get('slug') or item.get('reviewer', {}).get('id')}"
              for item in reviewers
              if not (item.get('type') == 'User' and item.get('reviewer', {}).get('id') == maintainer_id)]
    if others:
        blocking.append('autres approbateurs : ' + ', '.join(others))
    if reviewers:
        fixable.append('approbation manuelle à retirer pour le circuit automatique')
    if rules.get('wait_timer', {}).get('wait_timer'):
        fixable.append(f"délai d’attente de {rules['wait_timer']['wait_timer']} min")
    if environment.get('can_admins_bypass'):
        blocking.append('contournement par les administrateurs autorisé : le décocher dans Settings > Environments')
    policy = environment.get('deployment_branch_policy') or {}
    names = [(item.get('type', 'branch'), item.get('name')) for item in (branch_policies or {}).get('branch_policies', [])]
    extra = [f'{kind} {name}' for kind, name in names if (kind, name) != ('branch', 'main')]
    if extra:
        blocking.append('autres règles de déploiement : ' + ', '.join(extra))
    if not policy.get('custom_branch_policies') or policy.get('protected_branches'):
        fixable.append('déploiement non limité à des branches nommées')
    if ('branch', 'main') not in names:
        fixable.append('branche main non déclarée')
    return blocking, fixable


def gh(*arguments, body=None):
    result = subprocess.run(['gh', 'api', *arguments], input=None if body is None else json.dumps(body),
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise LookupError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout or '{}')


def read(repository, name):
    """Only an HTTP 404 means "absent"; any other failure stops the tool."""
    try:
        environment = gh(f'repos/{repository}/environments/{name}')
    except LookupError as error:
        if 'HTTP 404' in str(error):
            return None, None
        raise
    return environment, gh(f'repos/{repository}/environments/{name}/deployment-branch-policies')


def apply(repository, name, maintainer_id):
    gh('-X', 'PUT', f'repos/{repository}/environments/{name}', '--input', '-', body={
        'wait_timer': 0, 'prevent_self_review': False,
        'reviewers': [],
        'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True},
    })
    _environment, branches = read(repository, name)
    if not any(item.get('name') == 'main' for item in (branches or {}).get('branch_policies', [])):
        gh('-X', 'POST', f'repos/{repository}/environments/{name}/deployment-branch-policies',
           '-f', 'name=main', '-f', 'type=branch')


def branch_problems(rules):
    types = {rule['type'] for rule in rules}
    problems = [kind + ' manquant' for kind in ('pull_request', 'deletion', 'non_fast_forward') if kind not in types]
    checks = [r['parameters'] for r in rules if r['type'] == 'required_status_checks']
    if not any(c.get('strict_required_status_checks_policy') and any(
            item.get('context') == 'Validation du dépôt signé' and item.get('integration_id') == 15368
            for item in c.get('required_status_checks', [])) for c in checks):
        problems.append('validation stricte « Validation du dépôt signé » manquante')
    return problems


def main(argv):
    if len(argv) != 2 or argv[1] not in ('--verifier', '--appliquer'):
        print(__doc__.split('\n\n')[1], file=sys.stderr)
        return 2
    try:
        user = gh('user')
    except (LookupError, OSError) as error:
        print(f'gh indisponible ou non connecté : {error}', file=sys.stderr)
        return 2
    print(f"Mainteneur : {user['login']}")
    status = 0
    for repository, name in TARGETS:
        try:
            environment, branches = read(repository, name)
        except LookupError as error:
            print(f'✖ {repository} / {name} : lecture impossible ({error}) ; rien n’a été modifié')
            status = 1
            continue
        blocking, fixable = analyse(environment, branches, user['id'])
        if argv[1] == '--appliquer' and fixable and not blocking:
            try:
                apply(repository, name, user['id'])
                environment, branches = read(repository, name)
                blocking, fixable = analyse(environment, branches, user['id'])
            except LookupError as error:
                print(f'✖ {repository} / {name} : modification refusée ({error})')
                status = 1
                continue
        problems = blocking + fixable
        if not problems:
            print(f'✔ {repository} / {name} : conforme')
            continue
        status = 1
        print(f"✖ {repository} / {name} : {' ; '.join(problems)}")
        if blocking and argv[1] == '--appliquer':
            print('  Rien n’a été modifié : vérifiez et retirez ces éléments vous-même dans Settings > Environments.')
    try:
        repository = 'denamiel/mirivue-arch'
        branch = gh(f'repos/{repository}/branches/main')
        if not branch['protected']:
            if argv[1] == '--appliquer':
                ruleset = json.loads((Path(__file__).parent / 'protection-mirivue-arch.json').read_text())
                gh('-X', 'POST', f'repos/{repository}/rulesets', '--input', '-', body=ruleset)
                branch = gh(f'repos/{repository}/branches/main')
            if not branch['protected']:
                print('✖ mirivue-arch/main : protection PR et validation obligatoire à activer')
                status = 1
        if branch['protected']:
            problems = branch_problems(gh(f'repos/{repository}/rules/branches/main'))
            if problems:
                print('✖ mirivue-arch/main : ' + ' ; '.join(problems))
                status = 1
            else:
                print('✔ mirivue-arch/main : PR, validation stricte et historique protégés')
    except LookupError as error:
        print(f'✖ Protection mirivue-arch/main : {error}')
        status = 1
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv))
