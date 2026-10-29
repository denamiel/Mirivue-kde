#!/usr/bin/env bash
set -euo pipefail
file_manager_activation_target() {
    desktop="${XDG_CURRENT_DESKTOP:-${XDG_SESSION_DESKTOP:-}}"
    if [[ -z "$desktop" ]] && command -v systemctl >/dev/null 2>&1; then
        desktop="$(systemctl --user show-environment 2>/dev/null | sed -n 's/^XDG_CURRENT_DESKTOP=//p' | head -n 1)"
    fi
    desktop=":${desktop^^}:"
    if [[ "$desktop" == *:GNOME:* || "$desktop" == *:GNOME-CLASSIC:* || "$desktop" == *:CINNAMON:* ]]; then
        if [[ "$desktop" == *:GNOME:* || "$desktop" == *:GNOME-CLASSIC:* ]]; then
            printf '%s\n' nautilus
        else
            printf '%s\n' unsupported
        fi
        return
    fi
    if [[ "$desktop" == *:KDE:* || "$desktop" == *:PLASMA:* || "$desktop" == *:PLASMAWAYLAND:* || "$desktop" == *:PLASMAX11:* ]]; then
        printf '%s\n' mirivue
    else
        printf '%s\n' unsupported
    fi
}
# The user D-Bus activation file survives desktop changes. Dispatch when the
# bus activates it, using the current session rather than the previous one.
if [[ "${1:-}" == '--file-manager-service' || "${1:-}" == '--file-manager-activation-check' ]]; then
    target="$(file_manager_activation_target)"
    if [[ "${1:-}" == '--file-manager-activation-check' ]]; then
        printf '%s\n' "$target"
        exit 0
    fi
    if [[ "$target" == nautilus ]]; then
        # Use GNOME's own FileManager1 service program; avoid a Mirivue window.
        [[ -x /usr/bin/nautilus ]] || exit 1
        exec /usr/bin/nautilus --gapplication-service
    fi
    [[ "$target" == mirivue ]] || exit 1
fi
# Preserve the caller's directory for local relative paths before entering the
# installed application directory. URLs and options retain their original form.
launch_args=()
for argument in "$@"; do
    if [[ "$argument" != -* && "$argument" != /* && -e "$argument" ]]; then
        launch_args+=("$PWD/$argument")
    else
        launch_args+=("$argument")
    fi
done
set -- "${launch_args[@]}"
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
if [[ "${1:-}" == "--version" || "${1:-}" == "--diagnostic" || "${1:-}" == "--smoke-test" ]]; then
    exec /usr/bin/python3 -m mirivue "$@"
fi
# PipeWire is Plasma’s native audio path. Prefer Qt’s GStreamer backend when
# its plugin is installed; FFmpeg remains the fallback on smaller systems.
if [[ -z "${QT_MEDIA_BACKEND:-}" && -f /usr/lib/qt6/plugins/multimedia/libgstreamermediaplugin.so ]]; then
    export QT_MEDIA_BACKEND=gstreamer
fi
# Give the PipeWire/PulseAudio stream a stable identity.  Plasma can then keep
# Mirivue's routing separate from unrelated programs launched with python3.
if [[ -z "${PULSE_PROP:-}" ]]; then
    export PULSE_PROP='application.name="Mirivue KDE" application.id="org.pdenams.Mirivue.Qt" application.icon_name="org.pdenams.Mirivue.Qt" media.role="video"'
fi
mkdir -p -- "${XDG_STATE_HOME:-$HOME/.local/state}/mirivue"
log_file="${XDG_STATE_HOME:-$HOME/.local/state}/mirivue/dernier-lancement.log"
if ! /usr/bin/python3 -m mirivue "$@" >"$log_file" 2>&1; then
    message="Mirivue n’a pas pu démarrer. Relancez Installer.sh depuis l’archive extraite. Rapport : $log_file"
    if command -v kdialog >/dev/null; then
        kdialog --error "$message"
    elif command -v zenity >/dev/null; then
        zenity --error --text="$message"
    fi
    exit 1
fi
