#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
#
# Environnements GitHub protégeant chaque publication de Mirivue.
#
#   environnements-publication.sh --verifier   lecture seule ; code 1 si non conforme
#   environnements-publication.sh --appliquer  crée ou corrige les environnements
#
# Règle de chaque environnement : approbation obligatoire du mainteneur
# connecté à gh, déploiement limité à la branche main, sans délai.
# prevent_self_review reste désactivé : avec un seul mainteneur, celui qui lance
# la publication doit pouvoir l'approuver. L'approbation reste une seconde action
# explicite, distincte du lancement.
set -euo pipefail

cibles=(
  'denamiel/Mirivue-kde publication-copr'
  'denamiel/Mirivue-kde publication-arch'
  'denamiel/mirivue-arch publication-pacman'
)

mode="${1:-}"
[[ "$mode" == --verifier || "$mode" == --appliquer ]] || { sed -n 5,7p "$0"; exit 2; }
command -v gh >/dev/null || { echo 'gh (GitHub CLI) est requis.' >&2; exit 2; }
login="$(gh api user --jq .login)"
id="$(gh api user --jq .id)"

verifier() {
    local depot="$1" nom="$2" donnees
    if ! donnees="$(gh api "repos/$depot/environments/$nom" 2>/dev/null)"; then
        echo "✖ $depot/$nom : environnement absent (il ne protège rien)"; return 1
    fi
    python3 - "$depot/$nom" "$id" "$donnees" "$(gh api "repos/$depot/environments/$nom/deployment-branch-policies" 2>/dev/null || echo '{}')" <<'PY'
import json, sys
cible, attendu, env, branches = sys.argv[1], int(sys.argv[2]), json.loads(sys.argv[3]), json.loads(sys.argv[4])
erreurs = []
regles = {r['type']: r for r in env.get('protection_rules', [])}
relecture = regles.get('required_reviewers')
if not relecture:
    erreurs.append('aucune approbation obligatoire')
else:
    ids = {r['reviewer'].get('id') for r in relecture.get('reviewers', []) if r.get('type') == 'User'}
    if attendu not in ids:
        erreurs.append('le mainteneur ne figure pas parmi les approbateurs')
    if relecture.get('prevent_self_review'):
        erreurs.append('prevent_self_review actif : un mainteneur unique ne pourra pas approuver')
politique = env.get('deployment_branch_policy') or {}
noms = sorted(p['name'] for p in branches.get('branch_policies', []))
if not politique.get('custom_branch_policies') or noms != ['main']:
    erreurs.append(f'branches autorisées : {noms or "toutes"} (attendu : main seulement)')
print(('✔ ' if not erreurs else '✖ ') + cible + (' : conforme' if not erreurs else ' : ' + ' ; '.join(erreurs)))
sys.exit(1 if erreurs else 0)
PY
}

appliquer() {
    local depot="$1" nom="$2"
    gh api -X PUT "repos/$depot/environments/$nom" --input - >/dev/null <<EOF
{"wait_timer": 0, "prevent_self_review": false,
 "reviewers": [{"type": "User", "id": $id}],
 "deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
EOF
    if ! gh api "repos/$depot/environments/$nom/deployment-branch-policies" --jq '.branch_policies[].name' | grep -qx main; then
        gh api -X POST "repos/$depot/environments/$nom/deployment-branch-policies" -f name=main -f type=branch >/dev/null
    fi
}

echo "Mainteneur approbateur : $login"
statut=0
for cible in "${cibles[@]}"; do
    read -r depot nom <<<"$cible"
    [[ "$mode" == --appliquer ]] && appliquer "$depot" "$nom"
    verifier "$depot" "$nom" || statut=1
done
exit "$statut"
