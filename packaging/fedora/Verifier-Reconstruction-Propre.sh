#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
[[ $(id -u) != 0 ]] || { echo 'Lancer sans sudo.' >&2; exit 1; }
source_rpm="$PWD/SRPM/mirivue-kde-1.0.0-0.195.rc195.3.fc44.src.rpm"
if [[ ! -f "$source_rpm" ]]; then bash Construire-RPM.sh --source-only; fi
sudo dnf install mock mock-core-configs
result_dir="$(mktemp -d "$PWD/verification-mock-XXXXXXXX")"
# Mock ne recoit que le SRPM, sans montage du kit ni ses sources externes.
sudo mock -r "fedora-44-$(uname -m)" --uniqueext="mirivue-rc195-r2-$(date +%s)-$$" --resultdir="$result_dir" --rebuild "$source_rpm"
binary="$result_dir/mirivue-kde-1.0.0-0.195.rc195.3.fc44.$(uname -m).rpm"
[[ -f "$binary" ]]
rpm -K "$binary"
mkdir -p RPM
cp "$binary" RPM/
printf '\nReconstruction depuis le SRPM seul reussie : %s\n' "$binary"
printf 'Les journaux Mock sont conserves dans %s\n' "$result_dir"
