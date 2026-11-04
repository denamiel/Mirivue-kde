#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
[[ $(id -u) != 0 ]] || { echo 'Lancer sans sudo.' >&2; exit 1; }
source /etc/os-release
[[ $ID == fedora && $VERSION_ID =~ ^(44|45)$ && ! -e /run/ostree-booted ]] || { echo 'Fedora 44 ou 45 classique requis.' >&2; exit 1; }
dist=".fc${VERSION_ID}"
package_id="$(rpmspec -q --srpm --define "dist $dist" --qf '%{NAME}-%{VERSION}-%{RELEASE}' mirivue-kde.spec)"
source_rpm="$PWD/SRPM/${package_id}.src.rpm"
if [[ ! -f "$source_rpm" ]]; then bash Construire-RPM.sh --source-only; fi
sudo dnf install mock mock-core-configs
result_dir="$(mktemp -d "$PWD/verification-mock-XXXXXXXX")"
# Mock ne recoit que le SRPM, sans montage du kit ni ses sources externes.
sudo mock -r "fedora-${VERSION_ID}-$(uname -m)" --uniqueext="mirivue-beta-$(date +%s)-$$" --resultdir="$result_dir" --rebuild "$source_rpm"
binary="$result_dir/${package_id}.$(uname -m).rpm"
[[ -f "$binary" ]]
rpm -K "$binary"
mkdir -p RPM
cp "$binary" RPM/
printf '\nReconstruction depuis le SRPM seul reussie : %s\n' "$binary"
printf 'Les journaux Mock sont conserves dans %s\n' "$result_dir"
