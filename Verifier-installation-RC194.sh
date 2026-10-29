#!/usr/bin/env bash
set -euo pipefail

expected='1.0.0-rc194'
share_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
user_target="$share_dir/mirivue-kde"
user_desktop="$share_dir/applications/org.pdenams.Mirivue.Qt.desktop"
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-verification-XXXXXXXX")"
trap 'rm -rf -- "$temporary"' EXIT

failure() {
  printf 'ÉCHEC — %s\n' "$1" >&2
  exit 1
}

if command -v pacman >/dev/null 2>&1 && pacman -Qq mirivue-kde >/dev/null 2>&1; then
  mode='paquet système'
  target='/usr/lib/mirivue-kde'
  launcher='/usr/bin/mirivue-kde'
  desktop='/usr/share/applications/org.pdenams.Mirivue.Qt.desktop'
  icon='/usr/share/icons/hicolor/scalable/apps/org.pdenams.Mirivue.Qt.svg'
  package_version="$(pacman -Q mirivue-kde)"
  [[ "$package_version" == 'mirivue-kde 1.0.0rc194-1' ]] || \
    failure "paquet installé inattendu : $package_version"
  [[ ! -e "$user_desktop" ]] || \
    failure 'un lanceur utilisateur masque encore celui du paquet système'
else
  mode='installation utilisateur'
  target="$user_target"
  launcher="$target/Lancer.sh"
  desktop="$user_desktop"
  icon="$share_dir/icons/hicolor/scalable/apps/org.pdenams.Mirivue.Qt.svg"
fi

[[ -x "$launcher" ]] || failure "lanceur absent pour le mode : $mode"
version="$("$launcher" --version)"
[[ "$version" == "$expected" ]] || failure "version installée $version au lieu de $expected"
printf 'RÉUSSI — version installée : %s (%s)\n' "$version" "$mode"

[[ -f "$desktop" ]] || failure 'entrée du menu Plasma absente'
if [[ "$mode" == 'paquet système' ]]; then
  grep -Fq 'Exec=/usr/bin/mirivue-kde %U' "$desktop" || failure 'commande du lanceur système incorrecte'
else
  grep -Fq "Exec=\"$target/Lancer.sh\" %U" "$desktop" || failure 'commande du lanceur utilisateur incorrecte'
fi
grep -Fq 'Icon=org.pdenams.Mirivue.Qt' "$desktop" || failure 'identité d’icône incorrecte'
grep -Fq 'GenericName=Gestionnaire de fichiers' "$desktop" || failure 'type d’application incorrect'
grep -Fq 'Categories=Qt;KDE;System;FileTools;FileManager;' "$desktop" || failure 'catégories de gestionnaire de fichiers absentes'
grep -Fq 'MimeType=inode/directory;' "$desktop" || failure 'prise en charge des dossiers non déclarée'
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$desktop" || failure 'entrée Plasma non conforme'
fi
mime_cache="$(dirname -- "$desktop")/mimeinfo.cache"
if [[ -f "$mime_cache" ]]; then
  grep -Eq '^inode/directory=.*org\.pdenams\.Mirivue\.Qt\.desktop(;|$)' "$mime_cache" || \
    failure 'Mirivue est absent du cache des applications capables d’ouvrir un dossier'
fi
[[ -f "$icon" ]] || failure 'icône Plasma absente'
if [[ "$mode" == 'paquet système' ]]; then
  png_icon='/usr/share/icons/hicolor/256x256/apps/org.pdenams.Mirivue.Qt.png'
  [[ -f "$png_icon" ]] || failure 'icône PNG du paquet absente'
  cmp -s "$source_dir/mirivue/icons/mirivue.svg" "$icon" || \
    failure 'icône SVG installée différente de la RC194'
  cmp -s "$source_dir/mirivue/icons/mirivue-256.png" "$png_icon" || \
    failure 'icône PNG installée différente de la RC194'
  for local_dir in "$share_dir/icons" "$HOME/.icons"; do
    [[ -d "$local_dir" ]] || continue
    local_icon="$(find "$local_dir" -type f \( -name 'org.pdenams.Mirivue.Qt.png' -o -name 'org.pdenams.Mirivue.Qt.svg' \) -print -quit)"
    [[ -z "$local_icon" ]] || failure "une ancienne icône locale peut masquer celle du paquet : $local_icon"
  done
fi
printf '%s\n' 'RÉUSSI — lanceur, icône et déclaration de gestionnaire de fichiers cohérents'
[[ "$(XDG_CURRENT_DESKTOP=GNOME "$launcher" --file-manager-activation-check)" == nautilus ]] || \
  failure 'FileManager1 ne délègue pas à Nautilus sous GNOME'
[[ "$(XDG_CURRENT_DESKTOP=KDE "$launcher" --file-manager-activation-check)" == mirivue ]] || \
  failure 'FileManager1 ne lance pas Mirivue sous Plasma'
[[ "$(XDG_CURRENT_DESKTOP=GNOME:KDE "$launcher" --file-manager-activation-check)" == nautilus ]] || \
  failure 'FileManager1 privilégie KDE alors que GNOME est présent'
printf '%s\n' 'RÉUSSI — activation FileManager1 orientée par la session GNOME ou Plasma'

for helper in list open applications empty-trash places preview service transfer; do
  [[ -x "$target/tools/mirivue-kio-$helper" ]] || \
    failure "assistant KIO absent ou non exécutable : mirivue-kio-$helper"
done
printf '%s\n' 'RÉUSSI — huit assistants KIO disponibles'
# Exercise the service used by the interface, not its compatibility helper.
# The Python harness bounds waiting for an invisible confirmation dialog.
/usr/bin/python3 "$source_dir/Verifier-service-KIO.py" \
  "$target/tools/mirivue-kio-service" "$temporary" || \
  failure 'le service KIO principal n’a pas pu mettre le fichier jetable à la corbeille'
[[ -x "$target/tools/mirivue-job-progress" ]] || \
  failure 'assistant de progression Plasma absent ou non exécutable'
if ! ldd "$target/tools/mirivue-job-progress" 2>&1 | grep -Fq 'libKF6JobWidgets'; then
  failure 'assistant de progression non lié à KF6 JobWidgets'
fi
printf '%s\n' 'RÉUSSI — progression des transferts reliée à Plasma'

[[ -r "$target/tools/libmirivue-item-presentation.so" ]] || \
  failure 'module natif de présentation des fichiers absent'
[[ -r "$target/tools/libmirivue-dolphin-view.so" ]] || \
  failure 'moteur de vues de Dolphin absent'
QT_QPA_PLATFORM=offscreen /usr/bin/python3 - "$target" <<'PYCODE' || \
  failure 'moteur de vues de Dolphin non fonctionnel'
import sys
sys.path.insert(0, sys.argv[1])
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QApplication
from mirivue.item_presentation import presentation_model
from mirivue.dolphin_view import DetailsView
app = QApplication([])
table = DetailsView()
source = QStandardItemModel()
source.appendRow(QStandardItem('initial'))
cache = presentation_model(source, table)
assert cache is not source, 'le modèle natif de présentation est absent'
table.setModel(cache)
table.resize(500, 300)
table.show()
app.processEvents()
assert table._backend.query()['engine'] == 'KStandardItemListView'
assert table._backend.query()['count'] == 1
source.item(0).setText('modifié')
app.processEvents()
assert table._backend.query(op='item', row=0)['text'] == 'modifié'
table.close()
PYCODE
printf '%s\n' 'RÉUSSI — moteur KItemListView et KStandardItemListWidget de Dolphin disponible'

if [[ "$mode" == 'paquet système' ]]; then
  places_widget="$target/tools/libmirivue-kio-places-widget.so"
  [[ -r "$places_widget" ]] || failure 'panneau Emplacements KDE natif absent'
  QT_QPA_PLATFORM=offscreen /usr/bin/python3 - "$places_widget" <<'PY' || \
    failure 'bibliothèque du panneau Emplacements KDE non chargeable'
import ctypes
import sys
from PySide6 import QtWidgets
library = ctypes.CDLL(sys.argv[1])
assert library.mirivue_places_create
assert library.mirivue_places_set_url
assert library.mirivue_navigator_create
assert library.mirivue_navigator_set_url
assert library.mirivue_icon_theme_init
assert library.mirivue_application_style_init
assert library.mirivue_toolbar_create
app = QtWidgets.QApplication([])
library.mirivue_semantic_foreground.argtypes = [ctypes.c_int, ctypes.c_int]
library.mirivue_semantic_foreground.restype = ctypes.c_uint
assert all(library.mirivue_semantic_foreground(role, inactive)
           for inactive in (0, 1) for role in range(4))
library.mirivue_format_byte_size.argtypes = [ctypes.c_double, ctypes.c_void_p, ctypes.c_size_t]
library.mirivue_format_byte_size.restype = ctypes.c_int
output = ctypes.create_string_buffer(128)
assert library.mirivue_format_byte_size(1024, output, len(output)) > 0
assert output.value.decode('utf-8')
PY
  printf '%s\n' 'RÉUSSI — panneau Emplacements KDE natif disponible'
fi

"$source_dir/Installer.sh" --check-dependencies >/dev/null || \
  failure 'un ou plusieurs composants requis sont absents'
printf '%s\n' 'RÉUSSI — dépendances compatibles disponibles'

# Upgrade an RC93 per-user service even when validation runs from GNOME.
( cd -- "$temporary"
  PYTHONPATH="$target" /usr/bin/python3 -c \
    'from mirivue.filemanager1 import ensure_user_activation; ensure_user_activation()'
) || failure 'migration de l’activation FileManager1 impossible'
if [[ "$("$launcher" --file-manager-activation-check)" == mirivue && \
      "$(xdg-mime query default inode/directory 2>/dev/null || true)" == \
      'org.pdenams.Mirivue.Qt.desktop' ]]; then
  activation="$share_dir/dbus-1/services/org.freedesktop.FileManager1.service"
  [[ -f "$activation" ]] || failure 'fichier d’activation FileManager1 absent'
  grep -Fq 'Name=org.freedesktop.FileManager1' "$activation" || \
    failure 'service FileManager1 incorrect'
  grep -Fq '# Managed by Mirivue KDE' "$activation" || \
    failure 'service FileManager1 non identifiable'
  printf '%s\n' 'RÉUSSI — intégration « Afficher dans le dossier » activée'
else
  printf '%s\n' 'INFORMATION — FileManager1 n’est revendiqué par Mirivue que sous Plasma lorsqu’il est le gestionnaire par défaut'
fi

XDG_CONFIG_HOME="$temporary/config" XDG_STATE_HOME="$temporary/state" \
  QT_QPA_PLATFORM=offscreen "$launcher" --smoke-test >/dev/null || \
  failure 'la fenêtre principale ne peut pas être construite'
printf '%s\n' 'RÉUSSI — initialisation réelle de la fenêtre principale'
XDG_CONFIG_HOME="$temporary/ui-config" XDG_STATE_HOME="$temporary/ui-state" \
  QT_QPA_PLATFORM=offscreen timeout --kill-after=5s 65s "$launcher" --ui-contract >/dev/null || {
    [[ ! -f "$temporary/ui-state/mirivue/dernier-lancement.log" ]] || \
      tail -n 80 "$temporary/ui-state/mirivue/dernier-lancement.log" >&2
    failure 'les interactions des vues, de la barre d’outils, des panneaux ou de la recherche ont échoué'
  }
printf '%s\n' 'RÉUSSI — interactions réelles de l’interface avec réglages isolés'
# KF6 initializes its icon theme before QApplication in either session. The
# same configuration dialog must resolve every category icon when launched
# from GNOME, while keeping the installed KDE icon theme configuration.
XDG_CURRENT_DESKTOP=GNOME XDG_CONFIG_HOME="$temporary/gnome-icons-config" \
  XDG_STATE_HOME="$temporary/gnome-icons-state" \
  QT_QPA_PLATFORM=offscreen timeout --kill-after=5s 65s "$launcher" --ui-contract >/dev/null || {
    [[ ! -f "$temporary/gnome-icons-state/mirivue/dernier-lancement.log" ]] || \
      tail -n 80 "$temporary/gnome-icons-state/mirivue/dernier-lancement.log" >&2
    failure 'icônes ou interactions de la configuration KDE indisponibles sous GNOME'
  }
printf '%s\n' 'RÉUSSI — icônes de configuration KDE disponibles en session GNOME simulée'
if [[ -n "${WAYLAND_DISPLAY:-}${DISPLAY:-}" && "${QT_QPA_PLATFORM:-}" != offscreen && "${QT_QPA_PLATFORM:-}" != minimal ]]; then
  ( cd -- "$temporary"
    XDG_CONFIG_HOME="$temporary/native-config" XDG_STATE_HOME="$temporary/native-state" \
      PYTHONPATH="$target" timeout --kill-after=5s 65s \
      /usr/bin/python3 -m mirivue --native-places-contract >/dev/null
  ) || failure 'KFilePlacesView ou KUrlNavigator ne suit pas les panneaux dans cette session graphique'
  printf '%s\n' 'RÉUSSI — fil d’Ariane KDE vérifié dans la session graphique'
fi
printf '%s\n' 'Installation Mirivue KDE 1.0.0 RC194 vérifiée.'
