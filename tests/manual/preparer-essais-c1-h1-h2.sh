#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
#
# Prépare les fichiers d'essai de la validation manuelle C1/H1/H2.
# Tout est créé dans un seul dossier dédié ; aucun autre fichier n'est touché.
#
#   preparer-essais-c1-h1-h2.sh            crée le dossier d'essai
#   preparer-essais-c1-h1-h2.sh --verifier affiche son état (blancs finaux visibles)
#   preparer-essais-c1-h1-h2.sh --nettoyer supprime CE dossier après confirmation
set -euo pipefail
racine="${MIRIVUE_ESSAIS:-$HOME/Mirivue-essais-C1H1H2}"

afficher() {
    [[ -d "$racine" ]] || { echo "Aucun dossier d'essai : $racine"; return 1; }
    echo "État de $racine (les noms sont entre crochets pour montrer les espaces finaux) :"
    (cd -- "$racine" && find . -mindepth 1 | LC_ALL=C sort | while IFS= read -r entree; do
        if [[ -L "$entree" ]]; then
            printf '  [%s] -> lien vers [%s]\n' "${entree#./}" "$(readlink -- "$entree")"
        elif [[ -d "$entree" ]]; then
            printf '  [%s]/\n' "${entree#./}"
        else
            printf '  [%s] contient « %s »\n' "${entree#./}" "$(head -c 40 -- "$entree")"
        fi
    done)
}

case "${1:-}" in
    --verifier)
        afficher
        exit ;;
    --nettoyer)
        [[ -d "$racine" ]] || { echo "Rien à nettoyer : $racine"; exit 0; }
        afficher
        read -r -p "Supprimer définitivement le dossier d'essai « $racine » et lui seul ? Tapez oui : " reponse
        [[ "$reponse" == oui ]] || { echo 'Abandon : rien supprimé.'; exit 1; }
        rm -rf -- "$racine"
        echo "Dossier d'essai supprimé. Les éléments d'essai mis à la corbeille y restent : supprimez-les un par un."
        exit ;;
    '') ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
esac

if [[ -e "$racine" ]]; then
    echo "Le dossier d'essai existe déjà : $racine" >&2
    echo "Utilisez --verifier, ou --nettoyer avant de recommencer." >&2
    exit 1
fi

l="$racine/local"
mkdir -p -- "$l/Dossier" "$l/Dossier " "$l/Photos" "$l/Destination"
# Tailles différentes : la colonne Taille distingue « photo » et « photo␠ ».
printf 'AUTRE\n' > "$l/photo"
printf 'CIBLE : ce fichier porte un espace à la fin de son nom.\n' > "$l/photo "
printf 'CIBLE2 : ce fichier porte aussi un espace final.\n' > "$l/photo2 "
printf 'INTRUS\n' > "$l/Dossier/intrus.txt"
printf 'ATTENDU\n' > "$l/Dossier /attendu.txt"
printf 'SOURCE\n' > "$l/source.txt"
printf 'CIBLE DU LIEN\n' > "$l/cible.txt"
printf 'A\n' > "$l/Photos/a.jpg"
printf 'B\n' > "$l/Photos/b.jpg"
ln -s cible.txt "$l/lien-fichier.txt"
ln -s Photos "$l/lien-dossier"
ln -s fichier-absent "$l/lien-casse"
echo "Dossier d'essai créé."
afficher
