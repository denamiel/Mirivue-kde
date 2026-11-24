#!/usr/bin/env bash
set -euo pipefail
report=/tmp/mirivue-validation
exec > >(tee "$report/installation.log") 2>&1
collect_launch_log() {
  for log in "$HOME"/.local/state/mirivue/*.log; do
    if [[ -f "$log" ]]; then
      cp "$log" "$report/"
      tail -n 70 "$log"
    fi
  done
}
trap collect_launch_log EXIT
dpkg-query -W mirivue-kde
mirivue-kde --version
stat -c '%A %n' /usr/lib/mirivue-kde/tools/libmirivue-*.so
ldd /usr/lib/mirivue-kde/tools/libmirivue-dolphin-view.so
export PYTHONFAULTHANDLER=1
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR=$(mktemp -d)
QT_QPA_PLATFORM=offscreen timeout --signal=TERM --kill-after=5 20 mirivue-kde --smoke-test
gtk-launch org.pdenams.Mirivue.Qt
timeout 40 xdotool search --sync --onlyvisible --name 'Mirivue'
import -window root "$report/fenetre.png"
