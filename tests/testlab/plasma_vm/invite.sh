#!/bin/bash
# SPDX-License-Identifier: MIT
# Exécuté EN ROOT dans l'invité jetable, sortie sur la console série.
# 1. Attend la session Plasma de liveuser et relève des preuves de session.
# 2. Si un dépôt RPM hors ligne est monté (/mnt/t/repo) : installe Mirivue,
#    le lance sans DISPLAY, prouve son backend Wayland natif et interagit avec
#    lui par org.freedesktop.FileManager1.
# 3. Éteint l'invité. Aucun secret ; rien n'est lu hors de l'invité.
echo '=== TESTLAB-INVITE-DEBUT ==='
media=/mnt/t
uid=$(id -u liveuser)
rt=/run/user/$uid
dans_session() { runuser -u liveuser -- env XDG_RUNTIME_DIR=$rt DBUS_SESSION_BUS_ADDRESS=unix:path=$rt/bus "$@"; }
jalon() { echo "TESTLAB-JALON $1"; sleep "${2:-6}"; }
proc_pid() { pgrep -u liveuser -f "(^|/)$1( |\$)" | head -n1; }
env_de() { tr '\0' '\n' < "/proc/$1/environ" | sed -n "s/^$2=//p"; }

debut=$SECONDS
dans_session kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock false 2>&1
sleep 5
echo '--- travaux systemd en attente ---'; systemctl list-jobs --no-pager 2>&1 | head -20
echo '--- unités en échec ---'; systemctl --failed --no-pager --plain 2>&1 | head -20
while (( SECONDS - debut < 420 )); do
  pgrep -x plasmashell >/dev/null && pgrep -x kwin_wayland >/dev/null && [ -S $rt/bus ] && break
  sleep 3
done
echo "attente_s=$((SECONDS-debut))"
sleep 20   # laisser les services de session se stabiliser
if [ -f $media/FORCER_ECHEC ]; then
  # Test négatif : l'échec doit être DÉTECTÉ par le pilote (job rouge + rapport).
  echo "forcer_echec=$(cat $media/FORCER_ECHEC)"
  dans_session systemctl --user stop plasma-plasmashell.service 2>&1
  pkill -u liveuser -f '(^|/)plasmashell( |$)'; sleep 3
fi
echo "os=$(. /etc/os-release; echo "$PRETTY_NAME")"
echo "noyau=$(uname -r)"
echo "selinux=$(getenforce 2>&1)"
sid=$(loginctl list-sessions --no-legend | awk '$3=="liveuser"{print $1; exit}')
echo "session_id=${sid:-aucune}"
[ -n "$sid" ] && for p in Type Class State Remote Desktop; do echo "session_$p=$(loginctl show-session "$sid" -p $p --value)"; done
for proc in plasmashell kwin_wayland xdg-desktop-portal xdg-desktop-portal-kde kded6 ksmserver Xwayland; do
  pid=$(proc_pid "$proc")
  if [ -n "$pid" ]; then
    maps=/proc/$pid/maps
    echo "proc_$proc=present pid=$pid qt_wayland_maps=$(grep -c 'libqwayland' $maps 2>/dev/null) qt_xcb_maps=$(grep -c 'libqxcb' $maps 2>/dev/null)"
  else
    echo "proc_$proc=absent"
  fi
done
pid=$(proc_pid plasmashell)
if [ -n "$pid" ]; then
  echo "plasmashell_XDG_SESSION_TYPE=$(env_de "$pid" XDG_SESSION_TYPE)"
  echo "plasmashell_WAYLAND_DISPLAY=$(env_de "$pid" WAYLAND_DISPLAY)"
  echo "plasmashell_DISPLAY=$(env_de "$pid" DISPLAY)"
fi
for nom in org.kde.KWin org.kde.plasmashell org.freedesktop.portal.Desktop org.freedesktop.impl.portal.desktop.kde org.kde.kded6 org.freedesktop.Notifications; do
  if dans_session busctl --user status "$nom" >/dev/null 2>&1; then echo "dbus_$nom=present"; else echo "dbus_$nom=absent"; fi
done
echo "plasma_workspace_rpm=$(rpm -q plasma-workspace 2>&1)"
echo "qt6_wayland_rpm=$(rpm -q qt6-qtwayland 2>&1)"
echo "kwin_version=$(kwin_wayland --version 2>&1 | head -n1)"
jalon session 4

if [ -d $media/repo ]; then
  echo '--- scénario Mirivue ---'
  echo "reseau=$(timeout 6 curl -sS -o /dev/null -m 4 https://fedoraproject.org >/dev/null 2>&1 && echo present || echo absent)"
  echo "rpm_sha256_media=$(sha256sum $media/repo/mirivue-kde-*.rpm | cut -d' ' -f1)"
  dnf -y --setopt=reposdir=/nonexistent --repofrompath=lab,file://$media/repo \
      --setopt=lab.gpgcheck=0 --setopt=install_weak_deps=False install mirivue-kde > /tmp/dnf-install.log 2>&1
  echo "dnf_install_code=$?"
  echo '--- fin du journal dnf ---'; tail -n 15 /tmp/dnf-install.log
  echo "mirivue_nevra=$(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' mirivue-kde 2>&1)"
  echo "mirivue_version=$(dans_session mirivue-kde --version 2>&1 | tail -n1)"

  # Dossiers jetables de l'invité, sans lien avec aucune donnée réelle.
  base=/home/liveuser/testlab-mirivue
  dans_session mkdir -p $base/alpha $base/beta
  dans_session sh -c "echo alpha > $base/alpha/a.txt; echo beta > $base/beta/b.txt"
  # Mirivue devient le gestionnaire de fichiers par défaut DE CETTE SESSION JETABLE :
  # c'est la condition pour qu'il possède org.freedesktop.FileManager1.
  dans_session xdg-mime default org.pdenams.Mirivue.Qt.desktop inode/directory
  echo "gestionnaire_defaut=$(dans_session xdg-mime query default inode/directory)"

  # Environnement de la session réelle, SANS DISPLAY/XAUTHORITY/QT_QPA_PLATFORM :
  # aucun repli XWayland n'est possible ; Qt choisit lui-même son backend.
  mapfile -d '' -t env_session < /proc/$(proc_pid plasmashell)/environ
  env_app=()
  for v in "${env_session[@]}"; do
    case $v in DISPLAY=*|XAUTHORITY=*|QT_QPA_PLATFORM=*) ;; *) env_app+=("$v");; esac
  done
  runuser -u liveuser -- env -i "${env_app[@]}" sh -c \
    "nohup mirivue-kde $base/alpha > /tmp/mirivue.out 2>&1 &"

  fenetres() {  # lignes TESTLAB-WIN de l'état courant de KWin (interface publique KRunner)
    dans_session python3 $media/fenetres.py "$@" 2>&1
  }
  ligne=''
  for _ in $(seq 1 30); do
    ligne=$(fenetres Mirivue | grep '^TESTLAB-WIN' | head -n1)
    [ -n "$ligne" ] && break
    sleep 3
  done
  echo '--- diagnostic Mirivue ---'
  pgrep -af 'mirivue' | cut -c1-200
  echo "sortie de Mirivue :"; tail -n 20 /tmp/mirivue.out
  dans_session busctl --user list --no-legend 2>/dev/null | grep -i -e mirivue -e FileManager1 | cut -c1-160
  fenetres Mirivue
  echo '--- fin du diagnostic ---'
  echo "mirivue_fenetre=${ligne#TESTLAB-WIN }"
  mpid=$(echo "$ligne" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p')
  [ -n "$mpid" ] || mpid=$(pgrep -u liveuser -f 'python.*mirivue' | head -n1)
  echo "mirivue_pid=$mpid"
  if [ -n "$mpid" ]; then
    echo "mirivue_cmdline=$(tr '\0' ' ' < /proc/$mpid/cmdline)"
    echo "mirivue_env_DISPLAY=$(env_de "$mpid" DISPLAY)"
    echo "mirivue_env_QT_QPA_PLATFORM=$(env_de "$mpid" QT_QPA_PLATFORM)"
    echo "mirivue_XDG_SESSION_TYPE=$(env_de "$mpid" XDG_SESSION_TYPE)"
    echo "mirivue_qt_wayland_maps=$(grep -c 'libqwayland' /proc/$mpid/maps)"
    echo "mirivue_qt_xcb_maps=$(grep -c 'libqxcb' /proc/$mpid/maps)"
    echo "mirivue_sockets_x11=$(python3 $media/connexions.py "$mpid" Xwayland)"
    echo "mirivue_sockets_wayland=$(python3 $media/connexions.py "$mpid" kwin_wayland)"
    echo "mirivue_bus_instance=$(dans_session busctl --user list --no-legend 2>/dev/null | grep -c 'org.pdenams.Mirivue.Instance')"
    echo "fm1_pid=$(dans_session busctl --user status org.freedesktop.FileManager1 2>/dev/null | sed -n 's/^PID=//p')"
  fi
  jalon mirivue-ouvert 8

  # Saisie clavier/souris (prototype, seulement si le média porte le drapeau SAISIE) : l'HÔTE
  # injecte les entrées par QMP (tablette USB + clavier virtuels). Ce script ne crée JAMAIS le
  # dossier : il attend, puis constate l'existence et le propriétaire (liveuser = Mirivue).
  if [ -f $media/SAISIE ]; then
    nom=$(cat $media/SAISIE)
    dossier="$base/alpha/$nom"
    echo "saisie_a_txt_sha_avant=$(sha256sum $base/alpha/a.txt | cut -d' ' -f1)"
    echo 'TESTLAB-ATTENTE-SAISIE'
    for _ in $(seq 1 60); do [ -d "$dossier" ] && break; sleep 1; done
    echo "saisie_dossier_cree=$([ -d "$dossier" ] && echo oui || echo non)"
    echo "saisie_proprietaire=$(stat -c %U "$dossier" 2>/dev/null)"
    echo "saisie_contenu_alpha=$(LC_ALL=C ls -1 $base/alpha | LC_ALL=C sort | tr '\n' ' ' | sed 's/ $//')"
    echo "saisie_fichier_intact=$([ "$(sha256sum $base/alpha/a.txt | cut -d' ' -f1)" = "$(echo alpha | sha256sum | cut -d' ' -f1)" ] && echo oui || echo non)"
    dans_session sh -c "ls -la $base/alpha" 2>&1
    jalon saisie-apres 6
  fi

  # Interaction : une autre application de la session demande à son gestionnaire de
  # fichiers (Mirivue, propriétaire de FileManager1) d'ouvrir le dossier « beta ».
  echo "interaction_avant=$(fenetres | grep -i 'caption=.*Mirivue' | head -n1)"
  proprio=$(dans_session busctl --user status org.freedesktop.FileManager1 2>/dev/null | sed -n 's/^PID=//p')
  if [ -n "$mpid" ] && [ "$proprio" = "$mpid" ]; then
    dans_session busctl --user call org.freedesktop.FileManager1 /org/freedesktop/FileManager1 \
        org.freedesktop.FileManager1 ShowFolders ass 1 "file://$base/beta" "" 2>&1
    echo "interaction_appel_code=$?"
  else
    echo "interaction_appel_code=non-tente (FileManager1 appartient à pid=${proprio:-aucun}, Mirivue pid=${mpid:-aucun})"
  fi
  titre=''
  for _ in $(seq 1 15); do
    titre=$(fenetres | grep -i 'caption=beta.*Mirivue' | head -n1)
    [ -n "$titre" ] && break
    sleep 2
  done
  echo "interaction_titre=${titre#TESTLAB-WIN }"
  ipid=$(echo "$titre" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p')
  if [ -n "$ipid" ]; then
    # La fenêtre ouverte par l'interaction doit, elle aussi, être Wayland natif.
    echo "interaction_pid=$ipid"
    echo "interaction_env_DISPLAY=$(env_de "$ipid" DISPLAY)"
    echo "interaction_qt_wayland_maps=$(grep -c 'libqwayland' /proc/$ipid/maps)"
    echo "interaction_qt_xcb_maps=$(grep -c 'libqxcb' /proc/$ipid/maps)"
    echo "interaction_sockets_x11=$(python3 $media/connexions.py "$ipid" Xwayland)"
    echo "interaction_sockets_wayland=$(python3 $media/connexions.py "$ipid" kwin_wayland)"
  fi
  [ -n "$titre" ] && echo 'interaction_ok=oui' || echo 'interaction_ok=non'
  jalon interaction 8

  [ -n "$mpid" ] && kill -TERM "$mpid" 2>/dev/null
  sleep 5
  echo "mirivue_vivant_apres_term=$([ -n "$mpid" ] && kill -0 "$mpid" 2>/dev/null && echo oui || echo non)"
  echo '--- sortie de Mirivue ---'; tail -n 15 /tmp/mirivue.out
fi

echo '--- journal utilisateur (erreurs) ---'
journalctl _UID=$uid -p err --no-pager -n 40 2>&1 | cut -c1-220
echo '=== TESTLAB-INVITE-FIN ==='
sleep 15
poweroff -f
