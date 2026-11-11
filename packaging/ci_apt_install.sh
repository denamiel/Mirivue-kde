#!/bin/bash
# SPDX-License-Identifier: MIT
# Installe des paquets Ubuntu sur un runner GitHub ÉPHÉMÈRE, avec un repli DNS
# strictement conditionnel (constat : le résolveur Azure ne répond pas pour les noms
# Ubuntu, alors que 1.1.1.1 répond ; voir PR n° 14).
#
# - Repli déclenché seulement si la résolution des hôtes APT échoue de façon
#   CONFIRMÉE (plusieurs tentatives espacées). Sinon : aucune modification DNS.
# - La configuration DNS de l'interface est restaurée en sortie, même en cas d'échec.
# - APT garde ses vérifications de signature : aucune option --allow-*, aucun
#   --no-check-*, aucun [trusted=yes].
# - Aucun faux vert : « apt-get update » renvoie 0 même si tous les miroirs
#   échouent ; son journal est donc contrôlé, et tout échec persistant est rouge.
# Usage : ci_apt_install.sh paquet [paquet...]
set -uo pipefail

[ "$#" -ge 1 ] || { echo 'usage : ci_apt_install.sh paquet [paquet...]' >&2; exit 64; }
# Hôtes nécessaires à APT (surchargeable pour les tests de la CI).
read -r -a HOTES <<< "${CI_APT_HOTES:-azure.archive.ubuntu.com security.ubuntu.com archive.ubuntu.com}"
SERVEUR_REPLI=${CI_APT_DNS_REPLI:-1.1.1.1}
TENTATIVES=${CI_APT_DNS_TENTATIVES:-4}
PAUSE=${CI_APT_DNS_PAUSE:-5}
JOURNAL=$(mktemp)

resolution_ok() {
  local h
  for h in "${HOTES[@]}"; do
    getent hosts "$h" >/dev/null 2>&1 || return 1
  done
}

resolution_confirmee_ko() {  # échec uniquement s'il persiste sur toutes les tentatives
  local i
  for ((i = 1; i <= TENTATIVES; i++)); do
    if resolution_ok; then return 1; fi
    echo "  résolution DNS APT en échec (tentative $i/$TENTATIVES)"
    sleep "$PAUSE"
  done
  return 0
}

diagnostic() {
  echo "::group::Diagnostic DNS"
  echo "interface=${IFACE:-inconnue}"
  resolvectl status 2>&1 | head -n 25
  for h in "${HOTES[@]}"; do printf '%s -> ' "$h"; getent hosts "$h" | head -n1 || echo 'non résolu'; done
  echo "::endgroup::"
}

apt_update_strict() {
  timeout 180 sudo apt-get -o Acquire::Retries=2 update > "$JOURNAL" 2>&1
  local code=$?
  tail -n 15 "$JOURNAL"
  # apt-get update sort en 0 malgré des miroirs injoignables : contrôle du journal.
  if grep -q -e '^Err:' -e 'Temporary failure resolving' -e '^W: Failed to fetch' "$JOURNAL"; then
    echo "::error::apt-get update : au moins un miroir est injoignable (échec réel, pas de faux vert)"
    return 1
  fi
  return "$code"
}

REPLI_ACTIF=0
DNS_INITIAL=''
IFACE=''
restaurer() {
  if [ "$REPLI_ACTIF" = 1 ]; then
    echo "Restauration de la configuration DNS initiale de $IFACE : ${DNS_INITIAL:-<aucun>}"
    # shellcheck disable=SC2086
    sudo resolvectl dns "$IFACE" $DNS_INITIAL
    sudo resolvectl flush-caches
    echo "DNS après restauration : $(resolvectl dns "$IFACE" 2>&1)"
  fi
  rm -f "$JOURNAL"
}
trap restaurer EXIT

if resolution_ok; then
  echo 'Résolution DNS APT normale : aucun repli.'
else
  echo 'Résolution DNS APT en échec : confirmation par tentatives espacées...'
  if resolution_confirmee_ko; then
    IFACE=$(ip -o route get "$SERVEUR_REPLI" 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p' | head -n1)
    if [ -z "$IFACE" ]; then
      echo '::error::interface réseau introuvable : repli impossible'
      diagnostic
      exit 1
    fi
    DNS_INITIAL=$(resolvectl dns "$IFACE" 2>/dev/null | sed 's/^[^:]*: *//')
    echo "::warning::REPLI DNS ACTIVÉ : $IFACE passe de « ${DNS_INITIAL:-aucun} » à $SERVEUR_REPLI (runner éphémère, restauré en sortie)"
    REPLI_ACTIF=1
    sudo resolvectl dns "$IFACE" "$SERVEUR_REPLI" || { echo '::error::resolvectl a échoué'; diagnostic; exit 1; }
    sudo resolvectl flush-caches
    if ! resolution_ok; then
      echo '::error::résolution toujours en échec avec le repli : échec persistant'
      diagnostic
      exit 1
    fi
    echo 'Résolution rétablie par le repli.'
  else
    echo 'Résolution rétablie sans repli pendant la confirmation.'
  fi
fi

apt_update_strict || { diagnostic; exit 1; }
sudo apt-get install -y "$@" || { echo '::error::apt-get install a échoué'; diagnostic; exit 1; }
echo 'Installation terminée.'
