#!/usr/bin/env bash
# Install and verify the maintained guides without touching application settings.
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
source_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
destination="${1:?Usage: install_docs.sh DESTINATION}"
documents=(
  'README.md'
  'LISEZ-MOI-KDE.txt'
  'CHANGELOG.md'
  'packaging/README.md'
  'packaging/fedora/README.md'
  'packaging/fedora/PUBLICATION.md'
  'docs/historique/LISEZ-MOI-KDE-RC194.txt'
)
for document in "${documents[@]}"; do
  install -Dm644 "$source_root/$document" "$destination/$document"
  cmp -- "$source_root/$document" "$destination/$document"
done
printf '%s guides installés et vérifiés dans %s\n' "${#documents[@]}" "$destination"
