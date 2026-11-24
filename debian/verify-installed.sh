#!/usr/bin/env bash
set -euo pipefail
report=/tmp/mirivue-validation
exec > >(tee "$report/installation.log") 2>&1
dpkg-query -W mirivue-kde
mirivue-kde --version
export PYTHONFAULTHANDLER=1
export XDG_RUNTIME_DIR
XDG_RUNTIME_DIR=$(mktemp -d)
QT_QPA_PLATFORM=offscreen timeout --signal=ABRT --kill-after=5 45 mirivue-kde --smoke-test
gtk-launch org.pdenams.Mirivue.Qt
timeout 40 xdotool search --sync --onlyvisible --name 'Mirivue'
import -window root "$report/fenetre.png"
