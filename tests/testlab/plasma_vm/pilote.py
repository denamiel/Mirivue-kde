#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Démarre une VM Fedora KDE Live jetable sous QEMU/KVM et en tire des preuves.

Frontière de confiance : l'invité n'a ni réseau (restrict=on), ni dossier de
l'hôte partagé, ni secret. Seuls entrent : l'ISO vérifiée et un ISO de scripts.
Seuls sortent : la console série, des captures QMP et les rapports.

Codes : 0 session Plasma Wayland prouvée ; 1 preuves invalides ; 2 KVM/QEMU
indisponible ; 3 invité muet ou délai dépassé. Jamais de « skipped ».
"""
import argparse, json, os, re, shutil, socket, subprocess, sys, time
from pathlib import Path

ICI = Path(__file__).resolve().parent
ATTENDUS_PROCESSUS = ['plasmashell', 'kwin_wayland', 'xdg-desktop-portal', 'xdg-desktop-portal-kde']
ATTENDUS_DBUS = ['org.kde.KWin', 'org.freedesktop.portal.Desktop', 'org.freedesktop.impl.portal.desktop.kde']


class Serie:
    """Console série de l'invité : journalisée, et pilotée (connexion liveuser)."""
    def __init__(self, chemin, journal, delai=30, proc=None):
        fin = time.time() + delai
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX); self.sock.connect(str(chemin)); break
            except OSError:
                if proc is not None and proc.poll() is not None:
                    raise RuntimeError('QEMU a quitté avant d’ouvrir la console série')
                if time.time() > fin: raise
                time.sleep(0.5)
        self.sock.setblocking(False); self.journal = open(journal, 'wb'); self.texte = ''
        self.connecte = False; self.lance = False; self.depuis_login = None
        self.t0 = time.time(); self.jalons = {}

    def pomper(self):
        try:
            while True:
                octets = self.sock.recv(65536)
                if not octets: break
                self.journal.write(octets); self.journal.flush()
                self.texte += octets.decode(errors='replace')
                for nom, motif in (('noyau', 'Linux version'), ('virtio_gpu', 'Initialized virtio_gpu'),
                                   ('gestionnaire_connexion', 'Started plasmalogin'), ('invite_login', 'login: '),
                                   ('script_debut', 'TESTLAB-INVITE-DEBUT'), ('script_fin', 'TESTLAB-INVITE-FIN')):
                    if nom not in self.jalons and motif in self.texte:
                        self.jalons[nom] = round(time.time() - self.t0, 1)
        except BlockingIOError:
            pass
        if not self.connecte and 'login: ' in self.texte[-200:]:
            self.sock.send(b'liveuser\n'); self.connecte = True; self.depuis_login = time.time()
        if self.connecte and not self.lance and time.time() - self.depuis_login > 8:
            cmd = 'sudo mkdir -p /mnt/t && sudo mount -L TESTLAB /mnt/t && sudo bash /mnt/t/invite.sh\n'
            self.sock.send(cmd.encode()); self.lance = True


class Qmp:
    def __init__(self, chemin, delai=30, proc=None):
        fin = time.time() + delai
        while True:
            try:
                self.sock = socket.socket(socket.AF_UNIX); self.sock.connect(str(chemin)); break
            except OSError:
                if proc is not None and proc.poll() is not None:
                    raise RuntimeError(f'QEMU a quitté (code {proc.returncode}) avant d’ouvrir QMP')
                if time.time() > fin: raise
                time.sleep(0.5)
        self.f = self.sock.makefile('rw'); self.f.readline()
        self.commande('qmp_capabilities')

    def commande(self, nom, **args):
        self.f.write(json.dumps({'execute': nom, 'arguments': args}) + '\n'); self.f.flush()
        while True:
            ligne = json.loads(self.f.readline())
            if 'return' in ligne or 'error' in ligne: return ligne


def analyser(texte):
    bloc = texte.split('=== TESTLAB-INVITE-DEBUT ===')[-1].split('=== TESTLAB-INVITE-FIN ===')[0]
    return {m.group(1): m.group(2) for m in re.finditer(r'^([A-Za-z_.-]+)=(.*)$', bloc, re.M)}


def verdict(mesures):
    erreurs = []
    if mesures.get('session_Type') != 'wayland': erreurs.append(f"session_Type={mesures.get('session_Type')!r} ≠ wayland")
    if mesures.get('plasmashell_XDG_SESSION_TYPE') != 'wayland': erreurs.append('plasmashell sans XDG_SESSION_TYPE=wayland')
    for p in ATTENDUS_PROCESSUS:
        if not mesures.get(f'proc_{p}', '').startswith('present'): erreurs.append(f'processus {p} absent')
    for n in ATTENDUS_DBUS:
        if mesures.get(f'dbus_{n}') != 'present': erreurs.append(f'nom D-Bus {n} absent')
    for p in ('plasmashell', 'kwin_wayland'):
        m = re.search(r'qt_wayland_maps=(\d+) qt_xcb_maps=(\d+)', mesures.get(f'proc_{p}', ''))
        if p == 'plasmashell' and not (m and int(m[1]) > 0 and int(m[2]) == 0):
            erreurs.append('plasmashell : greffon Qt Wayland non prouvé ou greffon xcb chargé')
    return erreurs


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--iso', required=True, type=Path)
    a.add_argument('--artefacts', required=True, type=Path)
    a.add_argument('--delai', type=int, default=900)
    a.add_argument('--memoire', default='6G')
    o = a.parse_args()
    art = o.artefacts; art.mkdir(parents=True, exist_ok=True)
    rapport = {'delai_max_s': o.delai}
    def fin(code, motif):
        rapport.update(code=code, motif=motif, duree_s=round(time.time() - t0, 1))
        (art / 'rapport.json').write_text(json.dumps(rapport, indent=2, ensure_ascii=False))
        (art / 'resume.md').write_text(f"### VM Plasma — code {code}\n\n{motif}\n")
        print(f'[pilote] code {code} : {motif}', flush=True); sys.exit(code)
    t0 = time.time()
    if not os.access('/dev/kvm', os.R_OK | os.W_OK) or not shutil.which('qemu-system-x86_64'):
        fin(2, 'KVM ou QEMU indisponible : aucun essai (pas de repli sans accélération).')
    tmp = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / f'plasma-vm-{os.getpid()}'
    tmp.mkdir(parents=True)
    # Noyau et initrd extraits de l'ISO vérifiée ; l'ISO reste en lecture seule.
    for src in ('/images/pxeboot/vmlinuz', '/boot/x86_64/loader/linux'):
        r = subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(o.iso), '-extract', src, str(tmp / 'vmlinuz')], capture_output=True)
        if (tmp / 'vmlinuz').exists(): break
    for src in ('/images/pxeboot/initrd.img', '/boot/x86_64/loader/initrd'):
        subprocess.run(['xorriso', '-osirrox', 'on', '-indev', str(o.iso), '-extract', src, str(tmp / 'initrd')], capture_output=True)
        if (tmp / 'initrd').exists(): break
    if not (tmp / 'vmlinuz').exists() or not (tmp / 'initrd').exists():
        listing = subprocess.run(['xorriso', '-indev', str(o.iso), '-find', '/', '-maxdepth', '3'], capture_output=True, text=True).stdout
        (art / 'iso-listing.txt').write_text(listing)
        fin(3, 'noyau/initrd introuvables dans l’ISO (voir iso-listing.txt)')
    info = subprocess.run(['xorriso', '-indev', str(o.iso), '-pvd_info'], capture_output=True, text=True)
    label = re.search(r'Volume Id\s*:\s*(\S+)', info.stdout + info.stderr)[1]
    rapport['iso_volume_id'] = label
    scripts = tmp / 'scripts'; scripts.mkdir(); shutil.copy(ICI / 'invite.sh', scripts / 'invite.sh')
    subprocess.run(['xorriso', '-as', 'mkisofs', '-V', 'TESTLAB', '-o', str(tmp / 'scripts.iso'), str(scripts)], check=True, capture_output=True)
    append = (f'root=live:CDLABEL={label} rd.live.image rd.live.overlay.overlayfs=1 console=ttyS0,115200 '
              f'enforcing=0')
    serie = art / 'console-serie.log'
    qemu = ['qemu-system-x86_64', '-machine', 'q35,accel=kvm', '-cpu', 'host', '-smp', '4', '-m', o.memoire,
            '-kernel', str(tmp / 'vmlinuz'), '-initrd', str(tmp / 'initrd'), '-append', append,
            '-drive', f'file={o.iso},media=cdrom,readonly=on,if=none,id=live', '-device', 'ide-cd,drive=live,bus=ide.0',
            '-drive', f'file={tmp / "scripts.iso"},media=cdrom,readonly=on,if=none,id=scr', '-device', 'ide-cd,drive=scr,bus=ide.1',
            '-device', 'virtio-vga', '-display', 'none', '-nic', 'user,model=virtio-net-pci,restrict=on',
            '-serial', f'unix:{tmp / "serie.sock"},server=on,wait=off', '-qmp', f'unix:{tmp / "qmp.sock"},server=on,wait=off',
            '-no-reboot', '-name', 'testlab-plasma']
    (art / 'commande-qemu.txt').write_text(' '.join(qemu) + '\n')
    proc = subprocess.Popen(qemu, stderr=open(art / 'qemu-stderr.log', 'w'))
    capt = 0; derniere = 0; sortie_vue = None
    erreur_pilote = None
    try:
        console = Serie(tmp / 'serie.sock', serie, proc=proc)
        qmp = Qmp(tmp / 'qmp.sock', proc=proc)
        while time.time() - t0 < o.delai:
            if proc.poll() is not None: break
            console.pomper(); texte = console.texte
            if time.time() - derniere > 30 or ('TESTLAB-INVITE-FIN' in texte and sortie_vue is None):
                derniere = time.time(); capt += 1
                ppm = tmp / f'c{capt:03d}.ppm'
                qmp.commande('screendump', filename=str(ppm))
                if ppm.exists():
                    png = art / f'capture-{capt:03d}-{int(time.time() - t0):04d}s.png'
                    with open(png, 'wb') as out:
                        subprocess.run(['pnmtopng', str(ppm)], stdout=out, stderr=subprocess.DEVNULL)
            if 'TESTLAB-INVITE-FIN' in texte and sortie_vue is None:
                sortie_vue = time.time() - t0
                time.sleep(3)
            if sortie_vue and time.time() - t0 > sortie_vue + 25: break
            time.sleep(2)
    except Exception as exc:   # le rapport doit toujours exister
        erreur_pilote = f'{type(exc).__name__}: {exc}'
    finally:
        if proc.poll() is None: proc.kill()
        proc.wait()
        shutil.rmtree(tmp, ignore_errors=True)   # invité jetable : tout est effacé
    texte = serie.read_text(errors='replace') if serie.exists() else ''
    rapport['jalons_s'] = console.jalons if 'console' in dir() else {}
    rapport['console_octets'] = len(texte); rapport['captures'] = capt
    if erreur_pilote: rapport['erreur_pilote'] = erreur_pilote
    rapport['qemu_code_retour'] = proc.returncode
    if 'TESTLAB-INVITE-FIN' not in texte:
        fin(3, f'invité muet ou délai dépassé après {round(time.time()-t0)} s (marqueur final absent ; voir console-serie.log et captures)' + (f' ; erreur pilote : {erreur_pilote}' if erreur_pilote else ''))
    mesures = analyser(texte); rapport['mesures'] = mesures
    erreurs = verdict(mesures); rapport['erreurs'] = erreurs
    if erreurs: fin(1, 'preuves insuffisantes : ' + '; '.join(erreurs))
    fin(0, 'session Plasma Wayland réelle prouvée dans l’invité (voir rapport.json)')

if __name__ == '__main__':
    main()
