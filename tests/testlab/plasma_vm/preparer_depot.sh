#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Prépare, SUR L'HÔTE CI, le dépôt RPM hors ligne remis à l'invité :
#  - dépendances de mirivue-kde = delta entre le RPM du commit et la base RPM de l'ISO Fedora KDE
#    (calculé par dnf avec --installroot sur une copie de la rpmdb de l'ISO) ;
#  - tous les paquets Fedora téléchargés doivent avoir une signature valide (clé Fedora 45) ;
#  - le RPM de Mirivue vient UNIQUEMENT du dossier fourni (artefact de ce workflow).
# Sortie : <sortie>/repo (avec métadonnées) et <sortie>/attendu.json.
set -euo pipefail
iso=${1:?usage: preparer_depot.sh <iso> <dossier-rpm-mirivue> <sortie>}
rpmdir=${2:?}; sortie=${3:?}
commit=${GITHUB_SHA:-inconnu}
. "$(dirname "$0")/image.env"
travail=$(mktemp -d); mkdir -p "$sortie/repo"
cleanup() { for m in rootfs squash iso; do sudo umount "$travail/$m" 2>/dev/null || true; done; sudo rm -rf "$travail"; }
trap cleanup EXIT
mkdir -p "$travail"/{iso,squash,rootfs,iso-root}
sudo mount -o loop,ro "$iso" "$travail/iso"
squash=$(sudo find "$travail/iso" -iname 'squashfs.img' | head -n1)
[ -n "$squash" ] || { echo "squashfs.img introuvable dans l'ISO" >&2; exit 1; }
echo "type de l'image : $(file -b "$squash" 2>/dev/null || true) ; $(sudo head -c 4 "$squash" | xxd -p)"
# squashfs ou erofs selon l'image : le noyau détecte le type.
sudo mount -o loop,ro "$squash" "$travail/squash" || { sudo modprobe erofs 2>&1 || true; sudo mount -o loop,ro "$squash" "$travail/squash"; }
rootfs=$(sudo find "$travail/squash" -iname 'rootfs.img' | head -n1)
if [ -n "$rootfs" ]; then sudo mount -o loop,ro "$rootfs" "$travail/rootfs"; racine=$travail/rootfs
else racine=$travail/squash; fi          # image sans couche ext4 intermédiaire
bd=$(sudo find "$racine/usr/lib/sysimage/rpm" "$racine/var/lib/rpm" -maxdepth 0 -type d 2>/dev/null | head -n1)
[ -n "$bd" ] || { echo "base RPM de l'ISO introuvable" >&2; exit 1; }
sudo mkdir -p "$travail/iso-root/usr/lib/sysimage" "$travail/iso-root/etc"
sudo cp -a "$bd" "$travail/iso-root/usr/lib/sysimage/rpm"
sudo cp -a "$racine/etc/os-release" "$travail/iso-root/etc/os-release" 2>/dev/null || true
nb=$(ls "$rpmdir"/mirivue-kde-*.rpm | wc -l); [ "$nb" = 1 ] || { echo "il faut exactement 1 RPM mirivue-kde, trouvé $nb" >&2; exit 1; }
sudo mkdir -p "$travail/out" "$travail/meta"
# Clé Fedora 45 épinglée : extraite du trousseau déjà contrôlé par recuperer_image.sh (empreinte vérifiée).
gnupg=$(mktemp -d); chmod 700 "$gnupg"
GNUPGHOME=$gnupg gpg --batch --import "$(dirname "$iso")/fedora.gpg" 2>/dev/null
GNUPGHOME=$gnupg gpg --batch --armor --export "$CLE_EMPREINTE" > "$travail/cle.gpg"
[ -s "$travail/cle.gpg" ] || { echo "clé épinglée $CLE_EMPREINTE absente de fedora.gpg" >&2; exit 1; }
rm -rf "$gnupg"
sudo docker run --rm -e CLE_EMPREINTE="$CLE_EMPREINTE" -v "$travail/iso-root:/iso-root" -v "$rpmdir:/in:ro" -v "$travail/out:/out" -v "$travail/meta:/meta" -v "$travail/cle.gpg:/cle.gpg:ro" fedora:45 bash -euo pipefail -c '
  dnf -y install createrepo_c rpm >/dev/null
  mkdir -p /cache
  dnf -y --installroot=/iso-root --use-host-config --releasever=45 --setopt=install_weak_deps=False \
      --setopt=keepcache=1 --setopt=cachedir=/cache install --downloadonly /in/mirivue-kde-*.rpm 2>&1 | tail -n 40
  # dnf5 range les RPM téléchargés dans son cache : on les rassemble à plat.
  { find /cache /iso-root/var/cache /var/cache -name "*.rpm" -type f 2>/dev/null || true; } | while read -r f; do [ -e "/out/$(basename "$f")" ] || cp "$f" /out/; done
  n=$(ls /out/*.rpm 2>/dev/null | wc -l); echo "RPM téléchargés (hors Mirivue) : $n"
  [ "$n" -ge 1 ] || { echo "dépendances attendues non téléchargées ($n)" >&2; exit 1; }
  ls /out | head -n 60
  # Signatures : toute RPM Fedora doit être signée par la clé Fedora 45 épinglée (image.env) ; seule Mirivue est non signée.
  rpmkeys --import /cle.gpg
  id_cle=$(echo "$CLE_EMPREINTE" | tail -c 17 | tr A-F a-f)
  for f in /out/*.rpm; do
    case "$f" in */mirivue-kde-*) continue;; esac
    rpmkeys -K "$f" | grep -q "digests signatures OK" || { echo "signature invalide : $f" >&2; exit 1; }
    rpm -qp --qf "%{RSAHEADER:pgpsig}\n" "$f" 2>/dev/null | grep -qi "$id_cle" || { echo "$f : pas signé par la clé épinglée $id_cle" >&2; exit 1; }
  done
  cp /in/mirivue-kde-*.rpm /out/
  rpm -qp --qf "%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}" /out/mirivue-kde-*.rpm > /meta/nevra
  echo "paquets installes dans la base de lISO : $(rpm --dbpath /iso-root/usr/lib/sysimage/rpm -qa | wc -l)"
  createrepo_c --quiet /out
'
sudo cp -a "$travail"/out/. "$sortie/repo/"
nevra=$(cat "$travail/meta/nevra")
sudo chown -R "$(id -u):$(id -g)" "$sortie"
rpm_file=$(ls "$sortie"/repo/mirivue-kde-*.rpm)
ls "$sortie"/repo/mirivue-kde-*.rpm | wc -l | grep -qx 1
python3 - "$rpm_file" "$commit" "$sortie" "$nevra" <<'PY'
import hashlib, json, sys
f, commit, sortie, nevra = sys.argv[1:]
json.dump({'commit': commit, 'rpm_nevra': nevra, 'rpm_sha256': hashlib.sha256(open(f, 'rb').read()).hexdigest()},
          open(f'{sortie}/attendu.json', 'w'), indent=2)
PY
cat "$sortie/attendu.json"
echo "dépôt : $(ls "$sortie"/repo/*.rpm | wc -l) RPM, $(du -sh "$sortie/repo" | cut -f1)"
