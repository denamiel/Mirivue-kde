#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
share_dir="${XDG_DATA_HOME:-$HOME/.local/share}"
applications_dir="$share_dir/applications"
icons_dir="$share_dir/icons/hicolor"
target="$share_dir/mirivue-kde"
previous="$share_dir/mirivue-kde-previous"
desktop_id="org.pdenams.Mirivue.Qt"
launcher="$applications_dir/$desktop_id.desktop"
staging=""
previous_target=""
installed_new=false
missing_components=()
missing_packages=()

package_family() {
  if command -v pacman >/dev/null 2>&1; then
    printf '%s\n' arch
  elif command -v dnf >/dev/null 2>&1; then
    printf '%s\n' fedora
  else
    printf '%s\n' unknown
  fi
}

add_missing() {
  local label="$1" arch_package="$2" fedora_package="$3" package
  missing_components+=("$label")
  case "$(package_family)" in
    arch) package="$arch_package" ;;
    fedora) package="$fedora_package" ;;
    *) package="" ;;
  esac
  if [[ -n "$package" ]] && [[ ! " ${missing_packages[*]-} " =~ " $package " ]]; then
    missing_packages+=("$package")
  fi
}

python_imports() {
  /usr/bin/python3 -c "$1" >/dev/null 2>&1
}

check_dependencies() {
  local native_check_dir runtime_helper helper_libraries
  missing_components=()
  missing_packages=()

  python_imports 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 15) else 1)' || \
    add_missing 'Python compatible (3.11 à 3.14)' python python3

  python_imports 'from PySide6 import QtCore, QtGui, QtWidgets, QtNetwork, QtDBus' || \
    add_missing 'Interface Qt/PySide6' pyside6 python3-pyside6
  python_imports 'import PySide6; v=tuple(map(int, PySide6.__version__.split(".")[:2])); raise SystemExit(0 if (6, 8) <= v < (7, 0) else 1)' || \
    add_missing 'Version compatible de PySide6 (6.8 ou version 6 ultérieure)' pyside6 python3-pyside6
  python_imports 'from PySide6 import QtMultimedia, QtMultimediaWidgets' || \
    add_missing 'Lecture audio et vidéo QtMultimedia' qt6-multimedia qt6-qtmultimedia
  python_imports 'from PySide6 import QtPdf' || \
    add_missing 'Aperçu PDF QtPdf' qt6-webengine qt6-qtpdf
  python_imports 'import shiboken6' || \
    add_missing 'Intégration PySide6/Shiboken6' shiboken6 python3-shiboken6
  python_imports 'from PIL import Image, ImageOps' || \
    add_missing 'Aperçus d’images Pillow' python-pillow python3-pillow
  python_imports 'import mutagen; from mutagen.id3 import ID3' || \
    add_missing 'Métadonnées audio Mutagen' python-mutagen python3-mutagen

  command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1 || \
    add_missing 'Analyse et décodage FFmpeg/FFprobe' ffmpeg ffmpeg-free
  command -v mediainfo >/dev/null 2>&1 || \
    add_missing 'Informations multimédias MediaInfo' mediainfo mediainfo
  command -v ark >/dev/null 2>&1 || \
    add_missing 'Création et ouverture d’archives Ark' ark ark
  command -v 7z >/dev/null 2>&1 || command -v 7zz >/dev/null 2>&1 || \
    add_missing 'Création et extraction d’archives 7z' 7zip 7zip
  command -v unar >/dev/null 2>&1 || command -v unrar >/dev/null 2>&1 || \
    add_missing 'Extraction d’archives RAR avec Ark' unrar unar
  if ! command -v exiftool >/dev/null 2>&1 && [[ ! -x /usr/bin/vendor_perl/exiftool ]]; then
    add_missing 'Métadonnées d’images ExifTool' perl-image-exiftool perl-Image-ExifTool
  fi
  command -v mkvpropedit >/dev/null 2>&1 && command -v mkvextract >/dev/null 2>&1 || \
    add_missing 'Métadonnées Matroska MKVToolNix' mkvtoolnix-cli mkvtoolnix

  runtime_helper=''
  if command -v pacman >/dev/null 2>&1 && pacman -Qq mirivue-kde >/dev/null 2>&1; then
    runtime_helper='/usr/lib/mirivue-kde/tools/mirivue-kio-service'
  fi
  if [[ -n "$runtime_helper" ]]; then
    if [[ ! -x "$runtime_helper" ]] || ! helper_libraries="$(ldd "$runtime_helper" 2>&1)" || \
       grep -q 'not found' <<<"$helper_libraries"; then
      add_missing 'Intégration KDE KIO/KF6 du paquet installé' kio kf6-kio
    fi
  else
    command -v cmake >/dev/null 2>&1 || add_missing 'Outil de construction CMake' cmake cmake
    command -v ninja >/dev/null 2>&1 || add_missing 'Outil de construction Ninja' ninja ninja-build
    if command -v cmake >/dev/null 2>&1 && command -v ninja >/dev/null 2>&1; then
      native_check_dir="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-kf6-check-XXXXXXXX")" || return 1
      if ! cmake -S "$source_dir/native" -B "$native_check_dir" -G Ninja \
          -DCMAKE_BUILD_TYPE=Release >/dev/null 2>&1; then
        add_missing 'Bibliothèques de développement Qt 6 et KDE KF6 (dont KColorScheme)' 'extra-cmake-modules kcolorscheme knewstuff kwindowsystem' 'kf6-kio-devel kf6-kcolorscheme-devel kf6-knewstuff-devel kf6-kwindowsystem-devel'
      fi
      rm -rf -- "$native_check_dir"
    fi
  fi

  ((${#missing_components[@]} == 0))
}

dependency_report() {
  if ((${#missing_components[@]} == 0)); then
    printf '%s\n' 'Tous les composants de Mirivue KDE sont disponibles.'
    return
  fi
  printf '%s\n' 'Composants manquants :'
  printf '  - %s\n' "${missing_components[@]}"
  if ((${#missing_packages[@]})); then
    printf '%s\n' 'Paquets proposés :'
    printf '  - %s\n' "${missing_packages[@]}"
  fi
}

mirivue_is_running() {
  local process owner current_uid index
  local -a arguments=()
  current_uid="$(id -u)"
  for process in /proc/[0-9]*; do
    [[ -r "$process/cmdline" ]] || continue
    owner="$(stat -c '%u' -- "$process" 2>/dev/null)" || continue
    [[ "$owner" == "$current_uid" ]] || continue
    arguments=()
    mapfile -d '' -t arguments < "$process/cmdline" || continue
    for ((index = 0; index + 1 < ${#arguments[@]}; index++)); do
      if [[ "${arguments[index]}" == '-m' && "${arguments[index + 1]}" == 'mirivue' ]]; then
        return 0
      fi
    done
  done
  return 1
}

qt_dialog() {
  local kind="$1" title="$2" message="$3"
  /usr/bin/python3 - "$kind" "$title" "$message" <<'PY'
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

application = QApplication.instance() or QApplication([])
kind, title, message = sys.argv[1:4]
if kind == 'information':
    QMessageBox.information(None, title, message)
else:
    QMessageBox.critical(None, title, message)
PY
}

show_error() {
  local message="$1" title='Mise à jour de Mirivue KDE vers 1.0.0 RC194'
  if command -v kdialog >/dev/null 2>&1; then
    kdialog --error "$message" --title "$title"
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title="$title" --text="$message"
  elif qt_dialog error "$title" "$message"; then
    :
  else
    printf '%s\n' "$message" >&2
  fi
}

show_information() {
  local title="$1" message="$2"
  if command -v kdialog >/dev/null 2>&1; then
    kdialog --msgbox "$message" --title "$title"
  elif command -v zenity >/dev/null 2>&1; then
    zenity --info --title="$title" --text="$message"
  else
    qt_dialog information "$title" "$message" || printf '%s\n' "$message"
  fi
}

report_missing_dependencies() {
  local instructions
  instructions=$'\n\nInstallez ces composants avec le gestionnaire de paquets du système, puis relancez Installer.sh. La version installée n’a pas été modifiée.'
  if [[ "$(package_family)" == arch ]] && ((${#missing_packages[@]})); then
    instructions+=$'\n\nSur CachyOS / Arch, effectuez une mise à jour complète avec les paquets requis :\n  sudo pacman -Syu --needed '
    instructions+="${missing_packages[*]}"
  fi
  show_error "$(dependency_report)$instructions"
}

restore_on_failure() {
  [[ -z "$staging" || ! -e "$staging" ]] || rm -rf -- "$staging"
  if [[ "$installed_new" == true && -e "$target" ]]; then
    rm -rf -- "$target"
  fi
  if [[ -n "$previous_target" && -e "$previous_target" && ! -e "$target" ]]; then
    mv -- "$previous_target" "$target"
  fi
}
trap restore_on_failure EXIT

restore_previous_version() {
  local failed="$share_dir/.mirivue-kde-echec-$$"
  if [[ ! -d "$previous" ]]; then
    show_error 'Aucune version précédente de Mirivue KDE n’est disponible.'
    return 1
  fi
  if mirivue_is_running; then
    show_error 'Mirivue fonctionne encore. Fermez complètement sa fenêtre et son icône de zone de notification avant le retour à la version précédente.'
    return 1
  fi
  if [[ -e "$target" ]]; then
    mv -- "$target" "$failed"
  fi
  if ! mv -- "$previous" "$target"; then
    [[ ! -e "$failed" ]] || mv -- "$failed" "$target"
    show_error 'La version précédente n’a pas pu être restaurée.'
    return 1
  fi
  rm -rf -- "$failed"
  install -m 0644 "$target/mirivue/icons/mirivue-256.png" \
    "$icons_dir/256x256/apps/$desktop_id.png"
  install -m 0644 "$target/mirivue/icons/mirivue.svg" \
    "$icons_dir/scalable/apps/$desktop_id.svg"
  # An older rollback target does not implement org.freedesktop.FileManager1.
  # Remove only Mirivue's own activation override in that case.
  activation="$share_dir/dbus-1/services/org.freedesktop.FileManager1.service"
  if [[ ! -f "$target/mirivue/filemanager1.py" ]] && \
     [[ -f "$activation" ]] && grep -Fq '# Managed by Mirivue KDE' "$activation"; then
    rm -f -- "$activation"
  fi
  command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
  show_information 'Retour à la version précédente' 'La version précédente de Mirivue KDE a été restaurée.'
}

if [[ "${1:-}" != '--check-dependencies' ]] && \
   command -v pacman >/dev/null 2>&1 && pacman -Qq mirivue-kde >/dev/null 2>&1; then
  show_error $'Mirivue KDE est déjà géré par pacman. Cette installation utilisateur créerait une seconde copie susceptible de masquer le paquet système.\n\nConstruisez le nouveau paquet avec Construire-paquet-CachyOS.sh, puis installez-le avec sudo pacman -U.'
  exit 1
fi

if [[ "${1:-}" == '--rollback' ]]; then
  mkdir -p -- "$share_dir" "$applications_dir" \
    "$icons_dir/256x256/apps" "$icons_dir/scalable/apps"
  restore_previous_version
  exit $?
fi

if [[ "${1:-}" == '--check-dependencies' ]]; then
  if check_dependencies; then
    dependency_report
    exit 0
  fi
  dependency_report
  exit 1
fi

if mirivue_is_running; then
  show_error 'Mirivue fonctionne encore. Fermez complètement sa fenêtre et son icône de zone de notification, puis relancez la mise à jour. La version installée n’a pas été modifiée.'
  exit 1
fi

if ! check_dependencies; then
  report_missing_dependencies
  exit 1
fi

mkdir -p -- "$share_dir" "$applications_dir" \
  "$icons_dir/256x256/apps" "$icons_dir/scalable/apps"

# Prepare and validate the complete application before replacing anything.
staging="$(mktemp -d "$share_dir/.mirivue-kde-XXXXXXXX")"
cp -a -- "$source_dir/mirivue" "$source_dir/Lancer.sh" "$staging/"
mkdir -p -- "$staging/tools" "$staging/licenses/dolphin-engine"
cp -a -- "$source_dir/native/dolphin-engine/LICENSES/." "$staging/licenses/dolphin-engine/"
cp -- "$source_dir/LICENSE" "$source_dir/LICENCES-TIERS.md" "$source_dir/native/NATURAL-SORT-UPSTREAM.json" "$source_dir/native/DATE-GROUPS-UPSTREAM.json" "$staging/licenses/"
cp -- "$source_dir/native/dolphin-engine/README.md" "$staging/licenses/dolphin-engine/README.md"
cp -a -- "$source_dir/LICENSES" "$staging/licenses/"
# The archive's old helper binaries cannot reflect changes in the native
# sources. Build them for this machine before publishing the new installation.
(
  set -e
  build_dir="$(mktemp -d "${TMPDIR:-/tmp}/mirivue-native-XXXXXXXX")"
  trap 'rm -rf -- "$build_dir"' EXIT
  cmake -S "$source_dir/native" -B "$build_dir" -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build "$build_dir" >/dev/null
  for helper in mirivue-kio-list mirivue-kio-open mirivue-kio-applications mirivue-kio-empty-trash mirivue-kio-places mirivue-kio-preview mirivue-kio-service mirivue-kio-transfer mirivue-job-progress; do
    install -m 0755 "$build_dir/$helper" "$staging/tools/$helper"
  done
  install -m 0755 "$build_dir/libmirivue-kio-places-widget.so" "$staging/tools/"
  install -m 0755 "$build_dir/libmirivue-item-presentation.so" "$staging/tools/"
  install -m 0755 "$build_dir/libmirivue-dolphin-view.so" "$staging/tools/"
) || { show_error 'La compilation des assistants KDE a échoué. Installez cmake, ninja, extra-cmake-modules et les bibliothèques de développement KF6.'; exit 1; }
chmod u+x "$staging/Lancer.sh"
(cd "$staging" && /usr/bin/python3 -m mirivue --version >/dev/null)
(cd "$staging" && QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m mirivue --smoke-test >/dev/null)

if [[ -e "$target" ]]; then
  rm -rf -- "$previous"
  previous_target="$previous"
  mv -- "$target" "$previous_target"
fi
mv -- "$staging" "$target"
staging=""
installed_new=true

# Install a freedesktop icon name rather than an absolute path. Plasma can then
# associate the Wayland/X11 window with its launcher and no longer shows Python.
install -m 0644 "$target/mirivue/icons/mirivue-256.png" \
  "$icons_dir/256x256/apps/$desktop_id.png"
install -m 0644 "$target/mirivue/icons/mirivue.svg" \
  "$icons_dir/scalable/apps/$desktop_id.svg"

launcher_tmp="$applications_dir/.$desktop_id.desktop.$$"
cat > "$launcher_tmp" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Mirivue KDE
GenericName=Gestionnaire de fichiers
Comment=Parcourir, organiser et analyser les fichiers
Exec="$target/Lancer.sh" %U
TryExec=$target/Lancer.sh
Icon=$desktop_id
Terminal=false
StartupNotify=true
StartupWMClass=$desktop_id
Categories=Qt;KDE;System;FileTools;FileManager;
MimeType=inode/directory;
Keywords=media;video;audio;image;files;
EOF
chmod 0644 "$launcher_tmp"
mv -- "$launcher_tmp" "$launcher"

# Remove only the launchers and application folders used by earlier Qt/KDE
# test versions. Mirivue GNOME/GTK and user settings are deliberately untouched.
for old_launcher in \
  "$applications_dir/org.pdenams.Mirivue.098Essai.desktop" \
  "$applications_dir/org.pdenams.Mirivue.099Essai.desktop" \
  "$applications_dir/org.pdenams.Mirivue.0910Essai.desktop" \
  "$applications_dir/org.pdenams.Mirivue.0911Essai.desktop" \
  "$applications_dir/org.pdenams.Mirivue.0912Essai.desktop"; do
  rm -f -- "$old_launcher"
done

# A generic launcher may belong to the GTK edition. Delete it only when its
# command clearly points to an old KDE/Qt installation.
generic_launcher="$applications_dir/org.pdenams.Mirivue.desktop"
if [[ -f "$generic_launcher" ]] && grep -Eq '/mirivue-0\.9\.(8|9|10|11|12)-essai/|/mirivue-kde/' "$generic_launcher"; then
  rm -f -- "$generic_launcher"
fi

shopt -s nullglob
old_qt_directories=(
  "$share_dir/mirivue-0.9.8-essai"
  "$share_dir/mirivue-0.9.9-essai"
  "$share_dir/mirivue-0.9.10-essai"
  "$share_dir/mirivue-0.9.11-essai"
  "$share_dir/mirivue-0.9.12-essai"
  "$share_dir/mirivue-0.9.13-essai"
  "$share_dir/mirivue-0.9.14-essai"
  "$share_dir/mirivue-0.9.15-essai"
  "$share_dir/mirivue-0.9.16-essai"
  "$share_dir/mirivue-0.9.17-essai"
  "$share_dir/mirivue-0.9.18-essai"
  "$share_dir/mirivue-0.9.19-essai"
  "$share_dir/mirivue-0.9.20-essai"
  "$share_dir/mirivue-0.9.21-essai"
  "$share_dir/mirivue-0.9.22-essai"
  "$share_dir/mirivue-0.9.23-essai"
  "$share_dir/mirivue-0.9.24-essai"
  "$share_dir/mirivue-0.9.25-essai"
  "$share_dir/mirivue-0.9.26-essai"
  "$share_dir/mirivue-0.9.27-essai"
  "$share_dir/mirivue-0.9.28-essai"
  "$share_dir/mirivue-0.9.29-essai"
  "$share_dir/mirivue-0.9.30-essai"
  "$share_dir/mirivue-0.9.31-essai"
  "$share_dir/mirivue-0.9.32-essai"
  "$share_dir/mirivue-0.9.33-essai"
  "$share_dir/mirivue-0.9.34-essai"
  "$share_dir/mirivue-0.9.35-essai"
  "$share_dir/mirivue-0.9.36-essai"
  "$share_dir/mirivue-0.9.37-essai"
  "$share_dir"/mirivue-0.9.*-essai-sauvegarde-*
)
for old_directory in "${old_qt_directories[@]}"; do
  [[ "$old_directory" == "$target" ]] || rm -rf -- "$old_directory"
done
shopt -u nullglob

# Keep one known-good version.  It can be restored with Installer.sh
# --rollback if a problem appears only during real use.
previous_target=""
installed_new=false

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$icons_dir" >/dev/null 2>&1 || true
fi
if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

trap - EXIT
show_information 'Mise à jour de Mirivue KDE' 'Mirivue KDE a été mis à jour vers 1.0.0 RC194. Tous les composants nécessaires ont été vérifiés. Les anciennes versions Qt ont été supprimées ; la version GNOME, les réglages et les fichiers personnels sont conservés.'
