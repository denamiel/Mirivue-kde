#!/bin/bash
# SPDX-License-Identifier: MIT
# Exécuté EN ROOT dans l'invité jetable (systemd.run), sortie sur la console série.
# Attend la session Plasma de liveuser, relève des preuves, puis éteint l'invité.
exec >/dev/ttyS0 2>&1
echo '=== TESTLAB-INVITE-DEBUT ==='
uid=$(id -u liveuser)
rt=/run/user/$uid
dans_session() { runuser -u liveuser -- env XDG_RUNTIME_DIR=$rt DBUS_SESSION_BUS_ADDRESS=unix:path=$rt/bus "$@"; }
debut=$SECONDS
while (( SECONDS - debut < 420 )); do
  pgrep -x plasmashell >/dev/null && pgrep -x kwin_wayland >/dev/null && [ -S $rt/bus ] && break
  sleep 3
done
echo "attente_s=$((SECONDS-debut))"
sleep 20   # laisser les services de session se stabiliser
echo "os=$(. /etc/os-release; echo "$PRETTY_NAME")"
echo "noyau=$(uname -r)"
echo "selinux=$(getenforce 2>&1)"
sid=$(loginctl list-sessions --no-legend | awk '$3=="liveuser"{print $1; exit}')
echo "session_id=${sid:-aucune}"
[ -n "$sid" ] && for p in Type Class State Remote Desktop; do echo "session_$p=$(loginctl show-session "$sid" -p $p --value)"; done
for proc in plasmashell kwin_wayland xdg-desktop-portal xdg-desktop-portal-kde kded6 ksmserver Xwayland; do
  pid=$(pgrep -x -u liveuser "$proc" | head -n1)
  if [ -n "$pid" ]; then
    maps=/proc/$pid/maps
    qtw=$(grep -c 'libqwayland' $maps 2>/dev/null); qtx=$(grep -c 'libqxcb' $maps 2>/dev/null)
    echo "proc_$proc=present pid=$pid qt_wayland_maps=${qtw:-0} qt_xcb_maps=${qtx:-0}"
  else
    echo "proc_$proc=absent"
  fi
done
pid=$(pgrep -x -u liveuser plasmashell | head -n1)
[ -n "$pid" ] && echo "plasmashell_XDG_SESSION_TYPE=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^XDG_SESSION_TYPE=//p')"
[ -n "$pid" ] && echo "plasmashell_WAYLAND_DISPLAY=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^WAYLAND_DISPLAY=//p')"
[ -n "$pid" ] && echo "plasmashell_DISPLAY=$(tr '\0' '\n' < /proc/$pid/environ | sed -n 's/^DISPLAY=//p')"
for nom in org.kde.KWin org.kde.plasmashell org.freedesktop.portal.Desktop org.freedesktop.impl.portal.desktop.kde org.kde.kded6 org.freedesktop.Notifications; do
  if dans_session busctl --user status "$nom" >/dev/null 2>&1; then echo "dbus_$nom=present"; else echo "dbus_$nom=absent"; fi
done
echo "plasmashell_version=$(dans_session plasmashell --version 2>&1 | head -n1)"
echo "kwin_version=$(kwin_wayland --version 2>&1 | head -n1)"
echo '--- journal utilisateur (erreurs) ---'
journalctl _UID=$uid -p err --no-pager -n 40 2>&1 | cut -c1-220
echo '=== TESTLAB-INVITE-FIN ==='
sleep 15
poweroff -f
