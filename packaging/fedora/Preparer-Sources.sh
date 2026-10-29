#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
repo_root="$(git rev-parse --show-toplevel)"
git -C "$repo_root" archive --format=tar --prefix=Mirivue-1.0.0-RC195-KDE/ HEAD | gzip -n > Mirivue-1.0.0-RC195-KDE-r4.tar.gz
sha256sum Mirivue-1.0.0-RC195-KDE-r4.tar.gz valider-appstream.py LICENSE-KIT.txt mirivue-kde.spec > SOURCE.sha256
printf 'Sources preparees depuis le commit %s\n' "$(git -C "$repo_root" rev-parse HEAD)"
