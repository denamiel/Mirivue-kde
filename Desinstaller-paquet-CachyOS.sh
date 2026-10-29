#!/usr/bin/env bash
set -euo pipefail

# Run as the account that uses Mirivue; pacman cannot clean files in a user's
# home directory. Only remove a service file that Mirivue itself owns.
if (( $# )); then
    printf '%s\n' 'Usage : ./Desinstaller-paquet-CachyOS.sh' >&2
    exit 2
fi
if pacman -Qq mirivue-kde >/dev/null 2>&1; then
    sudo pacman -R mirivue-kde
fi
activation="${XDG_DATA_HOME:-$HOME/.local/share}/dbus-1/services/org.freedesktop.FileManager1.service"
if [[ -f "$activation" ]] &&
   grep -Fxq '# Managed by Mirivue KDE' "$activation" &&
   grep -Fxq 'Name=org.freedesktop.FileManager1' "$activation" &&
   grep -Eq '^Exec=.*mirivue-kde.* --file-manager-service$' "$activation"; then
    rm -- "$activation"
    printf '%s\n' 'Service FileManager1 de Mirivue supprimé pour cet utilisateur.'
fi
printf '%s\n' 'Désinstallation du paquet terminée.'
