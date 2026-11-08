#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Environnements GitHub qui protègent chaque publication de Mirivue.

  environnements-publication.py --verifier   lecture seule ; code 1 si non conforme
  environnements-publication.py --appliquer  crée un environnement absent ou complète
                                             un environnement sûr ; refuse sinon

Règle attendue : seul le mainteneur connecté à gh approuve, déploiement limité à
la branche main, aucun délai, auto-approbation permise (mainteneur unique),
aucun contournement par les administrateurs.

--appliquer ne supprime jamais rien : s'il trouve d'autres approbateurs ou
d'autres règles de branche ou de tag, il les liste et refuse d'agir.
"""
import json
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
    if not any(item.get('type') == 'User' and item.get('reviewer', {}).get('id') == maintainer_id for item in reviewers):
        fixable.append('approbation du mainteneur non obligatoire')
    if rules.get('required_reviewers', {}).get('prevent_self_review'):
        fixable.append('prevent_self_review actif : un mainteneur unique ne pourrait pas approuver')
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
        'reviewers': [{'type': 'User', 'id': maintainer_id}],
        'deployment_branch_policy': {'protected_branches': False, 'custom_branch_policies': True},
    })
    _environment, branches = read(repository, name)
    if not any(item.get('name') == 'main' for item in (branches or {}).get('branch_policies', [])):
        gh('-X', 'POST', f'repos/{repository}/environments/{name}/deployment-branch-policies',
           '-f', 'name=main', '-f', 'type=branch')


def main(argv):
    if len(argv) != 2 or argv[1] not in ('--verifier', '--appliquer'):
        print(__doc__.split('\n\n')[1], file=sys.stderr)
        return 2
    try:
        user = gh('user')
    except (LookupError, OSError) as error:
        print(f'gh indisponible ou non connecté : {error}', file=sys.stderr)
        return 2
    print(f"Mainteneur approbateur : {user['login']}")
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
            apply(repository, name, user['id'])
            environment, branches = read(repository, name)
            blocking, fixable = analyse(environment, branches, user['id'])
        problems = blocking + fixable
        if not problems:
            print(f'✔ {repository} / {name} : conforme')
            continue
        status = 1
        print(f"✖ {repository} / {name} : {' ; '.join(problems)}")
        if blocking and argv[1] == '--appliquer':
            print('  Rien n’a été modifié : vérifiez et retirez ces éléments vous-même dans Settings > Environments.')
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv))
