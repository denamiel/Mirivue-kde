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
travail=$(mktemp -d); mkdir -p "$sortie/repo"
cleanup() { for m in rootfs squash iso; do sudo umount "$travail/$m" 2>/dev/null || true; done; sudo rm -rf "$travail"; }
trap cleanup EXIT
mkdir -p "$travail"/{iso,squash,rootfs,iso-root}
sudo mount -o loop,ro "$iso" "$travail/iso"
squash=$(sudo find "$travail/iso" -iname 'squashfs.img' | head -n1)
[ -n "$squash" ] || { echo "squashfs.img introuvable dans l'ISO" >&2; exit 1; }
sudo mount -t squashfs -o loop,ro "$squash" "$travail/squash"
rootfs=$(sudo find "$travail/squash" -iname 'rootfs.img' | head -n1)
if [ -n "$rootfs" ]; then sudo mount -o loop,ro "$rootfs" "$travail/rootfs"; racine=$travail/rootfs
else racine=$travail/squash; fi          # image sans couche ext4 intermédiaire
bd=$(sudo find "$racine/usr/lib/sysimage/rpm" "$racine/var/lib/rpm" -maxdepth 0 -type d 2>/dev/null | head -n1)
[ -n "$bd" ] || { echo "base RPM de l'ISO introuvable" >&2; exit 1; }
sudo mkdir -p "$travail/iso-root/usr/lib/sysimage" "$travail/iso-root/etc"
sudo cp -a "$bd" "$travail/iso-root/usr/lib/sysimage/rpm"
sudo cp -a "$racine/etc/os-release" "$travail/iso-root/etc/os-release" 2>/dev/null || true
echo "paquets installés dans l'ISO : $(sudo rpm --dbpath "$travail/iso-root/usr/lib/sysimage/rpm" -qa 2>/dev/null | wc -l || true)"
nb=$(ls "$rpmdir"/mirivue-kde-*.rpm | wc -l); [ "$nb" = 1 ] || { echo "il faut exactement 1 RPM mirivue-kde, trouvé $nb" >&2; exit 1; }
sudo mkdir -p "$travail/out"
sudo docker run --rm -v "$travail/iso-root:/iso-root" -v "$rpmdir:/in:ro" -v "$travail/out:/out" fedora:45 bash -euo pipefail -c '
  dnf -y install createrepo_c rpm >/dev/null
  dnf -y --installroot=/iso-root --use-host-config --releasever=45 --setopt=install_weak_deps=False \
      install --downloadonly --destdir=/out /in/mirivue-kde-*.rpm 2>&1 | tail -n 25
  find /out -name "*.rpm" -exec mv -t /out {} + 2>/dev/null || true
  # Signatures : toute RPM Fedora doit être signée par la clé Fedora 45 ; seule Mirivue est non signée.
  rpmkeys --import /etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-45-primary
  for f in /out/*.rpm; do
    case "$f" in */mirivue-kde-*) continue;; esac
    rpmkeys -K "$f" | grep -q "digests signatures OK" || { echo "signature invalide : $f" >&2; exit 1; }
  done
  cp /in/mirivue-kde-*.rpm /out/
  createrepo_c --quiet /out
'
sudo cp -a "$travail"/out/. "$sortie/repo/"
sudo chown -R "$(id -u):$(id -g)" "$sortie"
rpm_file=$(ls "$sortie"/repo/mirivue-kde-*.rpm)
ls "$sortie"/repo/mirivue-kde-*.rpm | wc -l | grep -qx 1
python3 - "$rpm_file" "$commit" "$sortie" <<'PY'
import hashlib, json, subprocess, sys
f, commit, sortie = sys.argv[1:]
nevra = subprocess.check_output(['rpm', '-qp', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}', f], text=True)
json.dump({'commit': commit, 'rpm_nevra': nevra, 'rpm_sha256': hashlib.sha256(open(f, 'rb').read()).hexdigest()},
          open(f'{sortie}/attendu.json', 'w'), indent=2)
PY
cat "$sortie/attendu.json"
echo "dépôt : $(ls "$sortie"/repo/*.rpm | wc -l) RPM, $(du -sh "$sortie/repo" | cut -f1)"
