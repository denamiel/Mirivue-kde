#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Télécharge l'ISO Fedora KDE épinglée et la vérifie : signature GPG du fichier
# CHECKSUM par la clé d'empreinte épinglée, puis SHA-256 identique dans le
# CHECKSUM signé ET dans image.env. Échec (code 1) à la moindre divergence.
set -euo pipefail
ici=$(cd "$(dirname "$0")" && pwd)
dest=${1:?usage: recuperer_image.sh <dossier>}
. "$ici/image.env"
mkdir -p "$dest"; cd "$dest"
gnupg=$(mktemp -d); chmod 700 "$gnupg"; export GNUPGHOME=$gnupg
[ -s "$CHECKSUM_NOM" ] || curl -fsSL --retry 3 -o "$CHECKSUM_NOM" "$CHECKSUM_URL"
curl -fsSL --retry 3 -o fedora.gpg "$CLE_URL"
gpg --batch --import fedora.gpg 2>/dev/null
# La clé importée doit être celle qui est épinglée.
gpg --batch --with-colons --fingerprint | grep -q "^fpr:::::::::${CLE_EMPREINTE}:" \
  || { echo "clé épinglée absente du trousseau Fedora" >&2; exit 1; }
sig=$(gpg --batch --status-fd 1 --verify "$CHECKSUM_NOM" 2>/dev/null || true)
echo "$sig" | grep -q "^\[GNUPG:\] VALIDSIG ${CLE_EMPREINTE} " \
  || { echo "signature du CHECKSUM invalide ou d'une autre clé" >&2; exit 1; }
attendu=$(sed -n "s/^SHA256 (${ISO_NOM}) = //p" "$CHECKSUM_NOM")
[ "$attendu" = "$ISO_SHA256" ] || { echo "SHA-256 signé ($attendu) ≠ SHA-256 épinglé" >&2; exit 1; }
[ -s "$ISO_NOM" ] || curl -fL --retry 3 -o "$ISO_NOM" "$ISO_URL"
calcule=$(sha256sum "$ISO_NOM" | cut -d' ' -f1)
[ "$calcule" = "$ISO_SHA256" ] || { echo "SHA-256 de l'ISO ($calcule) invalide" >&2; rm -f "$ISO_NOM"; exit 1; }
echo "OK : $ISO_NOM vérifiée (signature clé $CLE_EMPREINTE, SHA-256 $ISO_SHA256)"
