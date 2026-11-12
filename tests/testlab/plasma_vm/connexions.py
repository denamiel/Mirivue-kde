#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compte les connexions socket Unix d'un processus vers un autre processus (par nom).

`ss -xpn` n'affiche pas le chemin du socket Wayland côté client : on relie donc l'inode
PAIR de chaque socket du processus cible à l'inode LOCAL d'un socket détenu par un
processus nommé (kwin_wayland pour Wayland, Xwayland pour X11).
Usage : connexions.py <pid> <nom-du-processus-serveur>   →   nombre de connexions.
"""
import re
import subprocess
import sys
from pathlib import Path


def comm(pid):
    try:
        return Path(f'/proc/{pid}/comm').read_text().strip()
    except OSError:
        return ''


def compter(pid, serveur):
    sortie = subprocess.run(['ss', '-xpnH'], capture_output=True, text=True).stdout
    proprietaires, paires = {}, []
    for ligne in sortie.splitlines():
        champs = ligne.split()
        if len(champs) < 8:
            continue
        locale, pair = champs[5], champs[7]
        pids = set(re.findall(r'pid=(\d+)', ligne))
        proprietaires.setdefault(locale, set()).update(pids)
        if str(pid) in pids:
            paires.append(pair)
    return sum(1 for p in paires if any(comm(x) == serveur for x in proprietaires.get(p, ())))


if __name__ == '__main__':
    print(compter(sys.argv[1], sys.argv[2]))
