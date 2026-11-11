#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Mesure, sans rien présumer, ce qu'un hôte offre pour une VM QEMU/KVM jetable.
# Écrit un rapport Markdown (stdout) et un JSON ($1, défaut sonde-kvm.json).
# Code de sortie : 0 si KVM est utilisable, 2 sinon (jamais de « skipped » masquant).
set -u
json=${1:-sonde-kvm.json}
kvm_present=false; kvm_rw=false; kvm_api=""
[ -e /dev/kvm ] && kvm_present=true
[ -r /dev/kvm ] && [ -w /dev/kvm ] && kvm_rw=true
module=$(lsmod 2>/dev/null | awk '/^kvm_(amd|intel)/{print $1; exit}')
flags=$(grep -m1 -oE '\b(vmx|svm)\b' /proc/cpuinfo || true)
nested=$(cat /sys/module/kvm_*/parameters/nested 2>/dev/null | head -n1)
mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
cpus=$(nproc)
disk_gb=$(df -BG --output=avail "${RUNNER_TEMP:-/tmp}" | tail -n1 | tr -dc 0-9)
qemu=$(command -v qemu-system-x86_64 >/dev/null && qemu-system-x86_64 --version | head -n1)
ovmf=$(ls /usr/share/OVMF/OVMF_CODE*.fd /usr/share/edk2/ovmf/OVMF_CODE*.fd 2>/dev/null | head -n1)
hypervisor=$(systemd-detect-virt 2>/dev/null || echo inconnu)
ioctl_ok=false
if $kvm_rw; then
  # KVM_GET_API_VERSION == 12 est la preuve minimale que l'ioctl répond.
  kvm_api=$(python3 - <<'PY' 2>/dev/null
import fcntl, os
fd = os.open('/dev/kvm', os.O_RDWR)
print(fcntl.ioctl(fd, 0xAE00))
PY
)
  [ "$kvm_api" = 12 ] && ioctl_ok=true
fi
cat > "$json" <<JSON
{"hote_virtualise_par": "$hypervisor", "dev_kvm_present": $kvm_present, "dev_kvm_rw": $kvm_rw,
 "kvm_api": "${kvm_api}", "kvm_ioctl_ok": $ioctl_ok, "module_kvm": "${module}", "indicateur_cpu": "${flags}",
 "nested": "${nested}", "cpus": $cpus, "memoire_mo": $mem_mb, "disque_libre_go": ${disk_gb:-0},
 "qemu": "${qemu}", "ovmf": "${ovmf}"}
JSON
echo '### Sonde KVM'
echo '| Mesure | Valeur |'; echo '|---|---|'
echo "| Hôte virtualisé par | $hypervisor |"
echo "| /dev/kvm présent / lisible+écrivable | $kvm_present / $kvm_rw |"
echo "| ioctl KVM_GET_API_VERSION | ${kvm_api:-n/a} |"
echo "| Module / indicateur CPU / nested | ${module:-aucun} / ${flags:-aucun} / ${nested:-n/a} |"
echo "| CPU / mémoire (Mo) / disque libre (Go) | $cpus / $mem_mb / ${disk_gb:-?} |"
echo "| QEMU / OVMF | ${qemu:-absent} / ${ovmf:-absent} |"
$ioctl_ok && exit 0
echo 'KVM inutilisable sur cet hôte : aucune VM accélérée ne sera tentée.' >&2
exit 2
