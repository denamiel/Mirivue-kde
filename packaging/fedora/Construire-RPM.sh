#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
[[ $(id -u) != 0 ]] || { echo 'Lancer sans sudo.' >&2; exit 1; }
source /etc/os-release
[[ $ID == fedora && $VERSION_ID == 44 && ! -e /run/ostree-booted ]] || { echo 'Fedora 44 classique requis.' >&2; exit 1; }
mode="${1:-binaire}"
[[ $mode == binaire || $mode == --source-only ]] || { echo 'Argument inconnu.' >&2; exit 1; }
sha256sum -c SOURCE.sha256
python3 valider-appstream.py --self-test
sudo dnf install rpm-build rpmdevtools dnf-plugins-core
if [[ $mode == binaire ]]; then sudo dnf builddep ./mirivue-kde.spec; fi
buildtop="$(mktemp -d "$PWD/construction-XXXXXXXX")"
mkdir -p "$buildtop"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cp Mirivue-1.0.0-beta.1-KDE.tar.gz valider-appstream.py LICENSE-KIT.txt "$buildtop/SOURCES/"
cp mirivue-kde.spec "$buildtop/SPECS/"
option=-ba
if [[ $mode == --source-only ]]; then option=-bs; fi
rpmbuild "$option" --define "_topdir $buildtop" --define 'dist .fc44' "$buildtop/SPECS/mirivue-kde.spec"
source_rpm="$buildtop/SRPMS/mirivue-kde-1.0.0-0.196.beta1.3.fc44.src.rpm"
# Verifier les fichiers effectivement inclus, pas seulement les declarations.
rpm -qpl "$source_rpm" > "$buildtop/sources-incluses.txt"
grep -Fxq 'Mirivue-1.0.0-beta.1-KDE.tar.gz' "$buildtop/sources-incluses.txt"
grep -Fxq 'valider-appstream.py' "$buildtop/sources-incluses.txt"
grep -Fxq 'mirivue-kde.spec' "$buildtop/sources-incluses.txt"
grep -Fxq 'LICENSE-KIT.txt' "$buildtop/sources-incluses.txt"
mkdir -p SRPM
cp "$source_rpm" SRPM/
rpm -K "$source_rpm"
if [[ $mode == binaire ]]; then
 mkdir -p RPM
 cp "$buildtop/RPMS/$(uname -m)/mirivue-kde-1.0.0-0.196.beta1.3.fc44.$(uname -m).rpm" RPM/
 rpm -K RPM/mirivue-kde-1.0.0-0.196.beta1.3.fc44.*.rpm
fi
printf '\nConstruction terminee. Sources autonomes : %s/SRPM\n' "$PWD"
