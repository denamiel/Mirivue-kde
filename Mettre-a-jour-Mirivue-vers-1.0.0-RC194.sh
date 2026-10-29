#!/usr/bin/env bash
# Mise à jour sur place vers Mirivue KDE 1.0.0 RC194 : les réglages sont conservés.
set -u

script_dir="$(cd -- "$(dirname -- "$0")" && pwd -P)"
installer="$script_dir/Installer.sh"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/mirivue"
log_file="$state_dir/derniere-mise-a-jour.log"
mkdir -p -- "$state_dir"

qt_error() {
  local message="$1"
  /usr/bin/python3 - "$message" <<'PY'
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

application = QApplication.instance() or QApplication([])
QMessageBox.critical(None, 'Mise à jour de Mirivue KDE vers 1.0.0 RC194', sys.argv[1])
PY
}

show_error() {
  local message="$1"
  if command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$message" --title 'Mise à jour de Mirivue KDE vers 1.0.0 RC194'
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title='Mise à jour de Mirivue KDE vers 1.0.0 RC194' --text="$message"
  elif qt_error "$message"; then
    :
  else
    printf '%s\n' "$message" >&2
  fi
}

if [[ ! -f "$installer" ]]; then
  show_error $'Installer.sh est introuvable.\n\nExtrayez entièrement Mirivue-1.0.0-RC194-KDE.tar.gz dans Dolphin, ouvrez le dossier Mirivue-1.0.0-RC194-KDE obtenu, puis relancez ce fichier. Il ne peut pas être exécuté directement depuis l’archive.'
  exit 1
fi

if /usr/bin/bash "$installer" >"$log_file" 2>&1; then
  exit 0
else
  status=$?
  show_error $'La mise à jour n’a pas abouti. La version déjà installée a été conservée.\n\nRapport : '"$log_file"
  exit "$status"
fi
