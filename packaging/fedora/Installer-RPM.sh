#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
[[ $(id -u) != 0 ]] || { echo 'Lancer sans sudo.' >&2; exit 1; }
python3 - <<'PY'
import os, pathlib, sys
for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
    try:
        if p.stat().st_uid != os.getuid(): continue
        args=p.read_bytes().split(b'\0')
        if any(args[i:i+2]==[b'-m',b'mirivue'] for i in range(len(args)-1)):
            sys.exit('Fermez Mirivue avant la migration.')
    except (FileNotFoundError, PermissionError, ProcessLookupError): pass
PY
shopt -s nullglob
packages=("RPM/mirivue-kde-1.0.0-0.196.beta1.1.fc44.$(uname -m).rpm")
[[ ${#packages[@]} == 1 && -f "${packages[0]}" ]] || { echo 'Construire le RPM auparavant avec bash Construire-RPM.sh' >&2; exit 1; }
# Installer d'abord : un echec DNF laisse l'installation personnelle intacte.
sudo dnf install "./${packages[0]}"
/usr/bin/mirivue-kde --version
# Les bibliotheques natives installees doivent toutes etre resolues.
appdir="$(dirname "$(readlink -f /usr/bin/mirivue-kde)")"
for native in "$appdir"/tools/*; do
 if ldd "$native" 2>/dev/null | grep -q 'not found'; then
  printf 'Bibliotheque manquante : %s\n' "$native" >&2; exit 1
 fi
done
sudo appstreamcli refresh-cache --force
if ! appstreamcli get org.pdenams.Mirivue.Qt; then
 echo 'Metadonnees installees, detection AppStream a examiner.' >&2
fi
share="${XDG_DATA_HOME:-$HOME/.local/share}"
backup="${XDG_STATE_HOME:-$HOME/.local/state}/mirivue/migration-rpm-$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$backup"
for relative in mirivue-kde applications/org.pdenams.Mirivue.Qt.desktop; do
 if [[ -e "$share/$relative" ]]; then
  mkdir -p "$backup/$(dirname "$relative")"
  mv -- "$share/$relative" "$backup/$relative"
 fi
done
service="$share/dbus-1/services/org.freedesktop.FileManager1.service"
if [[ -f "$service" ]] && grep -qi mirivue "$service"; then
 cp -a "$service" "$backup/FileManager1.service"
 python3 - "$service" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); s=p.read_text()
s='\n'.join('Exec=/usr/bin/mirivue-kde --file-manager-service' if l.startswith('Exec=') else l for l in s.splitlines())+'\n'
p.write_text(s)
PY
fi
if command -v kbuildsycoca6 >/dev/null; then kbuildsycoca6 --noincremental; fi
printf '\nMigration terminee. Ancienne installation sauvegardee : %s\n' "$backup"
printf 'Demarrage : mirivue-kde\n'
