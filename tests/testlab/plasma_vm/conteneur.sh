#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Exécute une commande dans un conteneur Fedora 45 jetable, SANS apt (les miroirs Ubuntu
# des runners ont été indisponibles) : QEMU, xorriso et netpbm viennent de dnf.
# Le conteneur ne reçoit que /dev/kvm (pas de --privileged), le dépôt, le cache ISO en
# lecture seule et RUNNER_TEMP. Il ne contient aucun secret ni jeton.
set -euo pipefail
: "${RUNNER_TEMP:?RUNNER_TEMP requis}"
cache=${ISO_CACHE_DIR:-$HOME/iso-cache}
mkdir -p "$cache"
exec docker run --rm --device /dev/kvm \
  -e RUNNER_TEMP -e PAQUETS="qemu-system-x86-core qemu-device-display-virtio-vga qemu-device-display-virtio-gpu xorriso netpbm-progs python3 kmod systemd edk2-ovmf" \
  -v "$PWD:$PWD" -v "$cache:$cache:ro" -v "$RUNNER_TEMP:$RUNNER_TEMP" -w "$PWD" \
  fedora:45 bash -euo pipefail -c 'dnf -y -q --setopt=install_weak_deps=False install $PAQUETS >/dev/null && exec "$@"' _ "$@"
