#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
#
# Lance la version d'essai des corrections C1/H1/H2 pour la validation manuelle.
#
# À exécuter depuis le dépôt Mirivue, sans sudo :
#   cd ~/Projets/Mirivue-kde
#   git fetch origin
#   bash <(git show origin/collaboration/c1-h1-h2-beta5:tests/manual/lancer-validation-c1-h1-h2.sh)
#
# Le dépôt n'est pas modifié (aucun changement de branche). La version d'essai
# est construite dans /var/tmp/mirivue-validation-$USER ; les fichiers d'essai
# sont créés dans ~/Mirivue-essais-C1H1H2. Le paquet Mirivue installé n'est pas
# touché. Option --nettoyer : supprime ces deux dossiers, et eux seuls.
set -euo pipefail

# Réglages avancés facultatifs (essais du script) : référence Git et dossier de travail.
reference="${MIRIVUE_VALIDATION_REFERENCE:-origin/collaboration/c1-h1-h2-beta5}"
travail="${MIRIVUE_VALIDATION_TRAVAIL:-/var/tmp/mirivue-validation-$(id -un)}"
essais="$HOME/Mirivue-essais-C1H1H2"

etape() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }
stop() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }
question() {
    local reponse
    read -r -p "$1 [o/N] " reponse
    [[ "$reponse" == o || "$reponse" == O || "$reponse" == oui ]]
}

(( EUID != 0 )) || stop 'Lancez ce script avec votre compte habituel, sans sudo.'

if [[ "${1:-}" == --nettoyer ]]; then
    etape 'Nettoyage de la validation'
    if [[ -f "$travail/source/tests/manual/preparer-essais-c1-h1-h2.sh" && -d "$essais" ]]; then
        MIRIVUE_ESSAIS="$essais" bash "$travail/source/tests/manual/preparer-essais-c1-h1-h2.sh" --nettoyer || true
    elif [[ -d "$essais" ]]; then
        echo "Supprimez le dossier d'essai à la main si vous le souhaitez : $essais"
    fi
    if [[ -d "$travail" ]] && question "Supprimer la version d'essai construite dans $travail ?"; then
        rm -rf -- "$travail"
        echo 'Version d’essai supprimée.'
    fi
    echo 'Pensez à supprimer un par un les éléments d’essai restés dans la Corbeille.'
    exit 0
fi

etape 'Vérifications'
grep -q '^ID=fedora' /etc/os-release || stop 'Ce script est prévu pour Fedora.'
[[ "${XDG_CURRENT_DESKTOP:-}" == *KDE* ]] || echo '⚠ Session Plasma non détectée : la validation doit se faire dans Plasma.'
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [[ -f mirivue/__init__.py ]] \
    || stop 'Placez-vous d’abord dans le dépôt : cd ~/Projets/Mirivue-kde'
git rev-parse --verify --quiet "$reference" >/dev/null \
    || stop "Version d'essai introuvable. Lancez d'abord : git fetch origin"
if pgrep -u "$(id -u)" -f 'python3 (-B )?-m mirivue|/usr/lib64/mirivue-kde/' >/dev/null; then
    stop 'Mirivue est ouvert. Fermez toutes ses fenêtres puis relancez ce script.'
fi
echo "Version testée : $(git log -1 --format='%h %s' "$reference")"

etape 'Composants nécessaires à la construction'
source_dir="$travail/source"
rm -rf -- "$source_dir"
mkdir -p -- "$source_dir"
git archive "$reference" | tar -x -C "$source_dir"
mapfile -t paquets < <(sed -n 's/^BuildRequires:[[:space:]]*//p' "$source_dir/packaging/fedora/mirivue-kde.spec" \
    | tr ',' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]].*$//' | grep -v '^$')
paquets+=(python3-pyside6)
manquants=()
for paquet in "${paquets[@]}"; do rpm -q "$paquet" >/dev/null 2>&1 || manquants+=("$paquet"); done
if (( ${#manquants[@]} )); then
    echo "Paquets à installer : ${manquants[*]}"
    question 'Les installer maintenant avec « sudo dnf install » ? Votre mot de passe sera demandé.' \
        || stop 'Construction impossible sans ces paquets.'
    sudo dnf install -y "${manquants[@]}"
else
    echo 'Tous les composants sont présents.'
fi

etape 'Construction de la version d’essai (quelques minutes)'
journal="$travail/construction.log"
if ! { cmake -S "$source_dir/native" -B "$travail/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        && cmake --build "$travail/build" --parallel "$(nproc)"; } >"$journal" 2>&1; then
    tail -n 25 "$journal"
    stop "La construction a échoué. Journal complet : $journal"
fi
mkdir -p -- "$source_dir/tools"
find "$travail/build" -maxdepth 1 -type f \( -name 'mirivue-*' -o -name '*.so' \) -exec cp {} "$source_dir/tools/" \;
echo "Construction réussie ($(ls "$source_dir/tools" | wc -l) composants natifs)."

etape 'Fichiers d’essai'
if [[ -d "$essais" ]]; then
    echo "Le dossier d'essai existe déjà ; il est réutilisé : $essais"
else
    MIRIVUE_ESSAIS="$essais" bash "$source_dir/tests/manual/preparer-essais-c1-h1-h2.sh" >/dev/null
    echo "Dossier d'essai créé : $essais"
fi
cp -- "$source_dir/docs/VALIDATION-MANUELLE-C1-H1-H2.md" "$essais/LISTE-DES-ESSAIS.md"
echo "Liste des essais : $essais/LISTE-DES-ESSAIS.md"

etape 'Lancement de Mirivue (version d’essai)'
echo 'Suivez la liste des essais. Fermez Mirivue pour terminer.'
echo "Pour voir l'état réel des fichiers à tout moment, dans un autre terminal :"
echo "  bash $source_dir/tests/manual/preparer-essais-c1-h1-h2.sh --verifier"
cd -- "$source_dir"
python3 -m mirivue "$essais/local" || true
echo
echo 'Validation terminée. Pour tout nettoyer ensuite :'
echo "  bash $source_dir/tests/manual/lancer-validation-c1-h1-h2.sh --nettoyer"
