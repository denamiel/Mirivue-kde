#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Démarre une VM Fedora KDE Live jetable sous QEMU/KVM et en tire des preuves.

Frontière de confiance : l'invité n'a ni réseau (restrict=on), ni dossier de
l'hôte partagé, ni secret. Seuls entrent : l'ISO vérifiée et un ISO de scripts
(et, pour le scénario Mirivue, un dépôt RPM hors ligne). Seuls sortent : la
console série, des captures QMP et les rapports.

Codes : 0 preuves complètes ; 1 preuves invalides ; 2 KVM/QEMU indisponible ;
3 invité muet, délai dépassé ou pilote en erreur. Jamais de « skipped ».
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
ATTENDUS_PROCESSUS = ['plasmashell', 'kwin_wayland', 'xdg-desktop-portal', 'xdg-desktop-portal-kde']
ATTENDUS_DBUS = ['org.kde.KWin', 'org.freedesktop.portal.Desktop', 'org.freedesktop.impl.portal.desktop.kde']
JALONS_CAPTURE = ('session', 'mirivue-ouvert', 'interaction')
ANSI = re.compile(r'\x1b(\[[0-9;?]*[ -/]*[@-~]|\][^\x07\x1b]*(\x07|\x1b\\)|[@-Z\\-_])')


class ErreurPilote(RuntimeError):
    pass


def nettoyer(texte):
    """Retire les séquences ANSI/OSC et les retours chariot de la console série."""
    return ANSI.sub('', texte).replace('\r', '')


def analyser(texte):
    """Extrait les lignes `clé=valeur` du bloc de l'invité (le dernier bloc complet)."""
    texte = nettoyer(texte)
    if 'TESTLAB-INVITE-DEBUT' not in texte:
        return {}
    bloc = texte.rsplit('TESTLAB-INVITE-DEBUT', 1)[-1].split('TESTLAB-INVITE-FIN')[0]
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r'^([A-Za-z][A-Za-z0-9_.:-]*)=(.*)$', bloc, re.M)}


def _entier(texte, defaut=0):
    try:
        return int(texte)
    except (TypeError, ValueError):
        return defaut


def verdict_session(m):
    """Preuves de la session Plasma Wayland (indépendantes de Mirivue)."""
    erreurs = []
    if m.get('session_Type') != 'wayland':
        erreurs.append(f"session_Type={m.get('session_Type')!r} ≠ wayland")
    if m.get('plasmashell_XDG_SESSION_TYPE') != 'wayland':
        erreurs.append('plasmashell sans XDG_SESSION_TYPE=wayland')
    for p in ATTENDUS_PROCESSUS:
        if not m.get(f'proc_{p}', '').startswith('present'):
            erreurs.append(f'processus {p} absent')
    for n in ATTENDUS_DBUS:
        if m.get(f'dbus_{n}') != 'present':
            erreurs.append(f'nom D-Bus {n} absent')
    r = re.search(r'qt_wayland_maps=(\d+) qt_xcb_maps=(\d+)', m.get('proc_plasmashell', ''))
    if not (r and int(r[1]) > 0 and int(r[2]) == 0):
        erreurs.append('plasmashell : greffon Qt Wayland non prouvé ou greffon xcb chargé')
    return erreurs


def verdict_mirivue(m, attendu):
    """Preuves du scénario Mirivue : RPM du commit, Wayland natif, interaction."""
    e = []
    if m.get('reseau') != 'absent':
        e.append(f"réseau de l'invité non prouvé absent ({m.get('reseau')!r})")
    if m.get('dnf_install_code') != '0':
        e.append(f"installation hors ligne en échec (code {m.get('dnf_install_code')!r})")
    if not attendu:
        e.append('valeurs attendues du RPM absentes : identité du paquet non vérifiable')
    else:
        if m.get('rpm_sha256_media') != attendu.get('rpm_sha256'):
            e.append('SHA-256 du RPM du média ≠ RPM construit par ce workflow')
        if m.get('mirivue_nevra') != attendu.get('rpm_nevra'):
            e.append(f"NEVRA installé {m.get('mirivue_nevra')!r} ≠ attendu {attendu.get('rpm_nevra')!r}")
    if not m.get('mirivue_fenetre', '').startswith('pid='):
        e.append('aucune fenêtre Mirivue vue par KWin')
    if m.get('mirivue_env_DISPLAY', 'inconnu') != '':
        e.append(f"DISPLAY défini pour Mirivue ({m.get('mirivue_env_DISPLAY', 'inconnu')!r})")
    if m.get('mirivue_XDG_SESSION_TYPE') != 'wayland':
        e.append('Mirivue sans XDG_SESSION_TYPE=wayland')
    if not (_entier(m.get('mirivue_qt_wayland_maps')) > 0 and _entier(m.get('mirivue_qt_xcb_maps'), 1) == 0):
        e.append('Mirivue : greffon Qt Wayland non prouvé ou greffon xcb chargé')
    if _entier(m.get('mirivue_sockets_x11'), 1) != 0:
        e.append('Mirivue connecté à un socket X11 (XWayland)')
    if _entier(m.get('mirivue_sockets_wayland')) < 1:
        e.append('aucune connexion Wayland observée pour Mirivue')
    if not m.get('mirivue_pid') or m.get('fm1_pid') != m.get('mirivue_pid'):
        e.append('org.freedesktop.FileManager1 n’appartient pas au processus Mirivue')
    if _entier(m.get('mirivue_bus_instance')) < 1:
        e.append('nom D-Bus d’instance Mirivue absent')
    if m.get('interaction_ok') != 'oui':
        e.append(f"interaction FileManager1 non constatée ({m.get('interaction_titre', '?')!r})")
    return e


def verdict_captures(captures, exigees):
    """Au moins une capture valide pour chaque jalon exigé."""
    e = []
    for jalon in exigees:
        if not any(c['jalon'] == jalon and c['valide'] for c in captures):
            e.append(f'aucune capture valide pour le jalon « {jalon} »')
    return e


def verdict(m, attendu, mirivue=True, selinux='enforcing', captures=(), jalons_exiges=None):
    erreurs = verdict_session(m)
    if selinux == 'enforcing' and m.get('selinux') != 'Enforcing':
        erreurs.append(f"SELinux {m.get('selinux')!r} ≠ Enforcing")
    if mirivue:
        erreurs += verdict_mirivue(m, attendu)
    exigees = jalons_exiges if jalons_exiges is not None else (JALONS_CAPTURE if mirivue else ('session',))
    erreurs += verdict_captures(list(captures), exigees)
    return erreurs


def valider_ppm(donnees):
    """Une capture est valide si c'est un PPM P6 complet et non uniforme."""
    m = re.match(rb'P6\s+(\d+)\s+(\d+)\s+(\d+)\s', donnees)
    if not m:
        return False, 'en-tête PPM absent'
    largeur, hauteur = int(m[1]), int(m[2])
    corps = donnees[m.end():]
    if largeur < 320 or hauteur < 200:
        return False, f'dimensions invalides {largeur}x{hauteur}'
    if len(corps) < largeur * hauteur * 3:
        return False, 'image tronquée'
    pas = max(3, (len(corps) // 4096) // 3 * 3)
    if len({corps[i:i + 3] for i in range(0, len(corps) - 2, pas)}) < 8:
        return False, 'image quasi uniforme (écran vide)'
    return True, f'{largeur}x{hauteur}'


def valider_png(chemin):
    donnees = Path(chemin).read_bytes() if Path(chemin).exists() else b''
    if len(donnees) < 2000 or not donnees.startswith(b'\x89PNG\r\n\x1a\n'):
        return False, f'PNG invalide ({len(donnees)} octets)'
    return True, f'{len(donnees)} octets'


class Serie:
    """Console série de l'invité : journalisée, et pilotée (connexion liveuser)."""

    def __init__(self, chemin, journal, delai=30, proc=None):
        fin = time.time() + delai
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.connect(str(chemin))
                break
            except OSError:
                if proc is not None and proc.poll() is not None:
                    raise ErreurPilote('QEMU a quitté avant d’ouvrir la console série')
                if time.time() > fin:
                    raise
                time.sleep(0.5)
        self.sock.setblocking(False)
        self.journal = open(journal, 'wb')
        self.texte = ''
        self.connecte = False
        self.lance = False
        self.depuis_login = None
        self.t0 = time.time()
        self.jalons = {}

    def pomper(self):
        try:
            while True:
                octets = self.sock.recv(65536)
                if not octets:
                    break
                self.journal.write(octets)
                self.journal.flush()
                self.texte += octets.decode(errors='replace')
                for nom, motif in (('noyau', 'Linux version'), ('virtio_gpu', 'Initialized virtio_gpu'),
                                   ('gestionnaire_connexion', 'Started plasmalogin'), ('invite_login', 'login: '),
                                   ('script_debut', 'TESTLAB-INVITE-DEBUT'),
                                   ('mirivue_ouvert', 'TESTLAB-JALON mirivue-ouvert'),
                                   ('script_fin', 'TESTLAB-INVITE-FIN')):
                    if nom not in self.jalons and motif in self.texte:
                        self.jalons[nom] = round(time.time() - self.t0, 1)
        except BlockingIOError:
            pass
        if not self.connecte and 'login: ' in self.texte[-200:]:
            self.sock.send(b'liveuser\n')
            self.connecte = True
            self.depuis_login = time.time()
        if self.connecte and not self.lance and time.time() - self.depuis_login > 8:
            cmd = 'sudo mkdir -p /mnt/t && sudo mount -o ro -L TESTLAB /mnt/t && sudo bash /mnt/t/invite.sh\n'
            self.sock.send(cmd.encode())
            self.lance = True


class Qmp:
    def __init__(self, chemin, delai=30, proc=None):
        fin = time.time() + delai
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.connect(str(chemin))
                break
            except OSError:
                if proc is not None and proc.poll() is not None:
                    raise ErreurPilote(f'QEMU a quitté (code {proc.returncode}) avant d’ouvrir QMP')
                if time.time() > fin:
                    raise
                time.sleep(0.5)
        self.f = self.sock.makefile('rw')
        self.f.readline()
        self.commande('qmp_capabilities')

    def commande(self, nom, **args):
        """Exécute une commande QMP ; toute réponse `error` est une exception."""
        self.f.write(json.dumps({'execute': nom, 'arguments': args}) + '\n')
        self.f.flush()
        while True:
            ligne = json.loads(self.f.readline())
            if 'error' in ligne:
                raise ErreurPilote(f"QMP {nom} : {ligne['error']}")
            if 'return' in ligne:
                return ligne


def capturer(qmp, tmp, art, jalon, rang, t0, captures):
    """Prend une capture QMP, la valide (PPM puis PNG) et la consigne, valide ou non."""
    info = {'jalon': jalon, 't_s': round(time.time() - t0, 1), 'valide': False, 'detail': ''}
    captures.append(info)
    ppm = tmp / f'c{rang:03d}.ppm'
    try:
        qmp.commande('screendump', filename=str(ppm))
        ok, detail = valider_ppm(ppm.read_bytes() if ppm.exists() else b'')
        if not ok:
            info['detail'] = detail
            return info
        png = art / f'capture-{rang:03d}-{jalon}-{int(info["t_s"]):04d}s.png'
        with open(png, 'wb') as sortie:
            r = subprocess.run(['pnmtopng', str(ppm)], stdout=sortie, stderr=subprocess.PIPE)
        if r.returncode != 0:
            info['detail'] = f'pnmtopng code {r.returncode} : {r.stderr.decode(errors="replace")[:200]}'
            png.unlink(missing_ok=True)
            return info
        ok, detail = valider_png(png)
        info.update(valide=ok, detail=f'{detail} ; {png.name}')
        if not ok:
            png.unlink(missing_ok=True)
    except Exception as exc:  # une capture ratée ne doit pas masquer le reste
        info['detail'] = f'{type(exc).__name__}: {exc}'
    finally:
        ppm.unlink(missing_ok=True)
    return info


def extraire_noyau(iso, tmp, art):
    for src in ('/images/pxeboot/vmlinuz', '/boot/x86_64/loader/linux'):
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract', src, str(tmp / 'vmlinuz')], capture_output=True)
        if (tmp / 'vmlinuz').exists():
            break
    for src in ('/images/pxeboot/initrd.img', '/boot/x86_64/loader/initrd'):
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(iso), '-extract', src, str(tmp / 'initrd')], capture_output=True)
        if (tmp / 'initrd').exists():
            break
    if not (tmp / 'vmlinuz').exists() or not (tmp / 'initrd').exists():
        listing = subprocess.run(['xorriso', '-indev', str(iso), '-find', '/', '-maxdepth', '3'], capture_output=True, text=True).stdout
        (art / 'iso-listing.txt').write_text(listing)
        raise ErreurPilote('noyau/initrd introuvables dans l’ISO (voir iso-listing.txt)')


def construire_media(tmp, paquets, forcer_echec):
    """ISO de scripts en lecture seule : invite.sh, éventuellement repo/ et un drapeau d'échec."""
    scripts = tmp / 'scripts'
    scripts.mkdir()
    shutil.copy(ICI / 'invite.sh', scripts / 'invite.sh')
    shutil.copy(ICI / 'fenetres.py', scripts / 'fenetres.py')
    if paquets:
        shutil.copytree(paquets, scripts / 'repo')
    if forcer_echec:
        (scripts / 'FORCER_ECHEC').write_text(forcer_echec + '\n')
    subprocess.run(['xorriso', '-as', 'mkisofs', '-V', 'TESTLAB', '-r', '-o', str(tmp / 'scripts.iso'), str(scripts)],
                   check=True, capture_output=True)
    shutil.rmtree(scripts)


def main(arguments=None):
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('--iso', required=True, type=Path)
    a.add_argument('--artefacts', required=True, type=Path)
    a.add_argument('--delai', type=int, default=1200)
    a.add_argument('--memoire', default='8G')
    a.add_argument('--paquets', type=Path, help='dossier du dépôt RPM hors ligne (repo/) ; sans lui, pas de scénario Mirivue')
    a.add_argument('--attendu', type=Path, help='JSON : commit, rpm_nevra, rpm_sha256 du RPM construit')
    a.add_argument('--forcer-echec', default='', choices=['', 'plasma'],
                   help='test négatif : sabote volontairement l’invité ; l’échec doit être détecté')
    a.add_argument('--selinux', choices=['enforcing', 'permissif'], default='enforcing')
    o = a.parse_args(arguments)
    art = o.artefacts
    art.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rapport = {'delai_max_s': o.delai, 'selinux_demande': o.selinux, 'forcer_echec': o.forcer_echec or None,
               'scenario_mirivue': bool(o.paquets)}
    etat = {}

    def fin(code, motif):
        rapport.update(code=code, motif=motif, duree_s=round(time.time() - t0, 1))
        (art / 'rapport.json').write_text(json.dumps(rapport, indent=2, ensure_ascii=False))
        (art / 'resume.md').write_text(f'### VM Plasma — code {code}\n\n{motif}\n')
        print(f'[pilote] code {code} : {motif}', flush=True)
        sys.exit(code)

    if not os.access('/dev/kvm', os.R_OK | os.W_OK) or not shutil.which('qemu-system-x86_64'):
        fin(2, 'KVM ou QEMU indisponible : aucun essai (pas de repli sans accélération).')
    attendu = json.loads(o.attendu.read_text()) if o.attendu else {}
    rapport['attendu'] = attendu
    tmp = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / f'plasma-vm-{os.getpid()}'
    tmp.mkdir(parents=True)
    captures, erreur_pilote, proc = [], None, None
    try:
        extraire_noyau(o.iso, tmp, art)
        info = subprocess.run(['xorriso', '-indev', str(o.iso), '-pvd_info'], capture_output=True, text=True)
        label = re.search(r'Volume Id\s*:\s*(\S+)', info.stdout + info.stderr)[1]
        rapport['iso_volume_id'] = label
        construire_media(tmp, o.paquets, o.forcer_echec)
        append = (f'root=live:CDLABEL={label} rd.live.image rd.live.overlay.overlayfs=1 console=ttyS0,115200 '
                  + ('enforcing=0' if o.selinux == 'permissif' else 'enforcing=1'))
        serie = art / 'console-serie.log'
        qemu = ['qemu-system-x86_64', '-machine', 'q35,accel=kvm', '-cpu', 'host', '-smp', '4', '-m', o.memoire,
                '-kernel', str(tmp / 'vmlinuz'), '-initrd', str(tmp / 'initrd'), '-append', append,
                '-drive', f'file={o.iso},media=cdrom,readonly=on,if=none,id=live', '-device', 'ide-cd,drive=live,bus=ide.0',
                '-drive', f'file={tmp / "scripts.iso"},media=cdrom,readonly=on,if=none,id=scr', '-device', 'ide-cd,drive=scr,bus=ide.1',
                '-device', 'virtio-vga', '-display', 'none', '-nic', 'user,model=virtio-net-pci,restrict=on',
                '-serial', f'unix:{tmp / "serie.sock"},server=on,wait=off',
                '-qmp', f'unix:{tmp / "qmp.sock"},server=on,wait=off', '-no-reboot', '-name', 'testlab-plasma']
        (art / 'commande-qemu.txt').write_text(' '.join(qemu) + '\n')
        proc = subprocess.Popen(qemu, stderr=open(art / 'qemu-stderr.log', 'w'))
        console = Serie(tmp / 'serie.sock', serie, proc=proc)
        etat['console'] = console
        qmp = Qmp(tmp / 'qmp.sock', proc=proc)
        rang, derniere, faits, fini_a = 0, 0, set(), None
        while time.time() - t0 < o.delai:
            if proc.poll() is not None:
                break
            console.pomper()
            texte = nettoyer(console.texte)
            for jalon in JALONS_CAPTURE:
                if f'TESTLAB-JALON {jalon}' in texte and jalon not in faits:
                    faits.add(jalon)
                    rang += 1
                    capturer(qmp, tmp, art, jalon, rang, t0, captures)
            if 'TESTLAB-INVITE-FIN' in texte and 'fin' not in faits:
                faits.add('fin')
                fini_a = time.time()
            if fini_a is None and time.time() - derniere > 30:
                derniere = time.time()
                rang += 1
                capturer(qmp, tmp, art, 'periodique', rang, t0, captures)
            if fini_a and time.time() - fini_a > 20:
                break
            time.sleep(1)
    except Exception as exc:  # le rapport doit toujours exister
        erreur_pilote = f'{type(exc).__name__}: {exc}'
    finally:
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            rapport['qemu_code_retour'] = proc.returncode
        shutil.rmtree(tmp, ignore_errors=True)  # invité jetable : tout est effacé
    console = etat.get('console')
    texte = nettoyer((art / 'console-serie.log').read_text(errors='replace')) if (art / 'console-serie.log').exists() else ''
    rapport['jalons_s'] = console.jalons if console else {}
    rapport['console_octets'] = len(texte)
    rapport['captures'] = captures
    rapport['captures_valides'] = sum(1 for c in captures if c['valide'])
    if erreur_pilote:
        rapport['erreur_pilote'] = erreur_pilote
    if 'TESTLAB-INVITE-FIN' not in texte:
        fin(3, f'invité muet ou délai dépassé après {round(time.time() - t0)} s (marqueur final absent ; '
               f'voir console-serie.log et captures)' + (f' ; erreur pilote : {erreur_pilote}' if erreur_pilote else ''))
    mesures = analyser(texte)
    rapport['mesures'] = mesures
    erreurs = verdict(mesures, attendu, mirivue=bool(o.paquets), selinux=o.selinux, captures=captures)
    rapport['erreurs'] = erreurs
    if erreurs:
        fin(1, 'preuves insuffisantes : ' + '; '.join(erreurs))
    fin(0, 'session Plasma Wayland réelle' + (', RPM Mirivue installé hors ligne, fenêtre Wayland native et interaction D-Bus prouvés'
                                              if o.paquets else '') + ' (voir rapport.json)')


if __name__ == '__main__':
    main()
