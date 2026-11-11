"""Régressions du pilote TestLab Plasma VM : analyse du journal, verdict, captures, échecs."""
import importlib.util
import json
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / 'tests' / 'testlab' / 'plasma_vm'
_spec = importlib.util.spec_from_file_location('pilote_plasma_vm', DOSSIER / 'pilote.py')
pilote = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilote)

ATTENDU = {'commit': 'abc', 'rpm_nevra': 'mirivue-kde-1.0.0-1.fc45.x86_64', 'rpm_sha256': 'f' * 64}
CAPTURES = [{'jalon': j, 'valide': True, 'detail': 'ok', 't_s': 1.0} for j in pilote.JALONS_CAPTURE]


def mesures_ok():
    m = {'session_Type': 'wayland', 'plasmashell_XDG_SESSION_TYPE': 'wayland', 'selinux': 'Enforcing',
         'proc_plasmashell': 'present pid=1 qt_wayland_maps=4 qt_xcb_maps=0',
         'reseau': 'absent', 'dnf_install_code': '0', 'rpm_sha256_media': ATTENDU['rpm_sha256'],
         'mirivue_nevra': ATTENDU['rpm_nevra'], 'mirivue_fenetre': 'pid=7 class=mirivue caption=alpha — Mirivue',
         'mirivue_pid': '7', 'mirivue_env_DISPLAY': '', 'mirivue_XDG_SESSION_TYPE': 'wayland',
         'mirivue_qt_wayland_maps': '4', 'mirivue_qt_xcb_maps': '0', 'mirivue_sockets_x11': '0',
         'mirivue_sockets_wayland': '2', 'fm1_pid': '7', 'mirivue_bus_instance': '1', 'interaction_ok': 'oui',
         'interaction_env_DISPLAY': '', 'interaction_qt_wayland_maps': '4', 'interaction_qt_xcb_maps': '0',
         'interaction_sockets_x11': '0', 'interaction_sockets_wayland': '1'}
    for p in pilote.ATTENDUS_PROCESSUS:
        m.setdefault(f'proc_{p}', 'present pid=2 qt_wayland_maps=0 qt_xcb_maps=0')
    for n in pilote.ATTENDUS_DBUS:
        m[f'dbus_{n}'] = 'present'
    return m


class TestAnalyse(unittest.TestCase):
    def test_ignore_ansi_osc_et_prend_le_dernier_bloc(self):
        brut = ('ancien\n=== TESTLAB-INVITE-DEBUT ===\nselinux=Permissive\n=== TESTLAB-INVITE-FIN ===\n'
                '\x1b]3008;start=x\x1b\\\x1b[0;32m=== TESTLAB-INVITE-DEBUT ===\r\n'
                'selinux=\x1b[1mEnforcing\x1b[0m\r\nmirivue_fenetre=pid=7 class=x caption=a=b\r\n'
                'Nov 11 12:00 ligne=ignorée\n=== TESTLAB-INVITE-FIN ===\n')
        m = pilote.analyser(brut)
        self.assertEqual(m['selinux'], 'Enforcing')
        self.assertEqual(m['mirivue_fenetre'], 'pid=7 class=x caption=a=b')
        self.assertNotIn('Nov', ' '.join(m))

    def test_sans_marqueur_aucune_mesure(self):
        self.assertEqual(pilote.analyser('selinux=Enforcing'), {})


class TestVerdict(unittest.TestCase):
    def verdict(self, m, **kw):
        kw.setdefault('captures', CAPTURES)
        return pilote.verdict(m, ATTENDU, **kw)

    def test_cas_nominal(self):
        self.assertEqual(self.verdict(mesures_ok()), [])

    def test_chaque_alteration_est_detectee(self):
        cas = {
            'DISPLAY défini': ({'mirivue_env_DISPLAY': ':0'}, 'DISPLAY'),
            'greffon xcb': ({'mirivue_qt_xcb_maps': '2'}, 'xcb'),
            'socket X11': ({'mirivue_sockets_x11': '1'}, 'X11'),
            'aucun wayland': ({'mirivue_sockets_wayland': '0'}, 'Wayland'),
            'FileManager1 autre pid': ({'fm1_pid': '99'}, 'FileManager1'),
            'sha256 différent': ({'rpm_sha256_media': '0' * 64}, 'SHA-256'),
            'nevra différent': ({'mirivue_nevra': 'mirivue-kde-0.9-1.fc45.x86_64'}, 'NEVRA'),
            'dnf en échec': ({'dnf_install_code': '1'}, 'installation'),
            'réseau présent': ({'reseau': 'present'}, 'réseau'),
            'interaction non': ({'interaction_ok': 'non'}, 'interaction'),
            'interaction xcb': ({'interaction_qt_xcb_maps': '1'}, 'interaction'),
            'interaction x11': ({'interaction_sockets_x11': '1'}, 'XWayland'),
            'interaction DISPLAY': ({'interaction_env_DISPLAY': ':0'}, 'DISPLAY'),
            'pas de fenêtre': ({'mirivue_fenetre': ''}, 'fenêtre'),
            'selinux permissif': ({'selinux': 'Permissive'}, 'SELinux'),
            'session x11': ({'session_Type': 'x11'}, 'wayland'),
            'portail absent': ({'proc_xdg-desktop-portal': 'absent'}, 'xdg-desktop-portal'),
            'plasmashell xcb': ({'proc_plasmashell': 'present pid=1 qt_wayland_maps=4 qt_xcb_maps=1'}, 'plasmashell'),
        }
        for nom, (changement, attendu) in cas.items():
            with self.subTest(nom):
                m = mesures_ok()
                m.update(changement)
                erreurs = self.verdict(m)
                self.assertTrue(any(attendu in e for e in erreurs), erreurs)

    def test_mesure_manquante_est_un_echec_pas_un_succes(self):
        m = mesures_ok()
        for cle in ('mirivue_env_DISPLAY', 'mirivue_sockets_x11', 'interaction_ok'):
            del m[cle]
        self.assertTrue(self.verdict(m))

    def test_valeurs_attendues_absentes(self):
        self.assertTrue(any('attendues' in e for e in pilote.verdict(mesures_ok(), {}, captures=CAPTURES)))

    def test_capture_exigee_valide(self):
        invalides = [dict(c, valide=False) for c in CAPTURES]
        self.assertEqual(len(self.verdict(mesures_ok(), captures=invalides)), 3)
        self.assertEqual(len(self.verdict(mesures_ok(), captures=[])), 3)

    def test_session_seule_sans_mirivue(self):
        m = {k: v for k, v in mesures_ok().items() if not k.startswith(('mirivue', 'fm1', 'dnf', 'rpm_', 'reseau', 'interaction'))}
        self.assertEqual(pilote.verdict(m, {}, mirivue=False, captures=CAPTURES[:1]), [])


def ppm(largeur=640, hauteur=400, motif=True):
    corps = bytearray()
    for i in range(largeur * hauteur):
        corps += bytes((i % 251, (i // 7) % 253, (i // 13) % 255)) if motif else b'\x10\x20\x30'
    return b'P6\n%d %d\n255\n' % (largeur, hauteur) + bytes(corps)


class TestCaptures(unittest.TestCase):
    def test_ppm_valide_et_invalides(self):
        self.assertTrue(pilote.valider_ppm(ppm())[0])
        self.assertFalse(pilote.valider_ppm(ppm(motif=False))[0])
        self.assertFalse(pilote.valider_ppm(ppm()[:-500])[0])
        self.assertFalse(pilote.valider_ppm(b'')[0])
        self.assertFalse(pilote.valider_ppm(ppm(100, 100))[0])

    def test_png(self):
        with tempfile.TemporaryDirectory() as t:
            vide, faux, bon = Path(t, 'v.png'), Path(t, 'f.png'), Path(t, 'b.png')
            vide.write_bytes(b'')
            faux.write_bytes(b'x' * 5000)
            bon.write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 3000)
            self.assertFalse(pilote.valider_png(vide)[0])
            self.assertFalse(pilote.valider_png(faux)[0])
            self.assertFalse(pilote.valider_png(Path(t, 'absent.png'))[0])
            self.assertTrue(pilote.valider_png(bon)[0])

    def faux_qmp(self, contenu, erreur=False):
        class Q:
            def commande(self_, nom, **args):
                if erreur:
                    raise pilote.ErreurPilote('QMP screendump : refus')
                Path(args['filename']).write_bytes(contenu)
        return Q()

    def test_pnmtopng_en_echec_donne_une_capture_invalide(self):
        with tempfile.TemporaryDirectory() as t:
            tmp, art = Path(t, 'tmp'), Path(t, 'art')
            tmp.mkdir(), art.mkdir()
            echec = subprocess.CompletedProcess([], 1, stderr=b'pnmtopng: boom')
            captures = []
            with mock.patch.object(pilote.subprocess, 'run', return_value=echec):
                info = pilote.capturer(self.faux_qmp(ppm()), tmp, art, 'session', 1, 0, captures)
            self.assertFalse(info['valide'])
            self.assertIn('pnmtopng code 1', info['detail'])
            self.assertEqual(list(art.glob('*.png')), [])
            self.assertEqual(captures, [info])

    def test_erreur_qmp_est_consignee_pas_avalee(self):
        with tempfile.TemporaryDirectory() as t:
            tmp, art = Path(t, 'tmp'), Path(t, 'art')
            tmp.mkdir(), art.mkdir()
            info = pilote.capturer(self.faux_qmp(b'', erreur=True), tmp, art, 'session', 1, 0, [])
            self.assertFalse(info['valide'])
            self.assertIn('refus', info['detail'])

    def test_qmp_leve_sur_reponse_error(self):
        a, b = socket.socketpair()
        q = pilote.Qmp.__new__(pilote.Qmp)
        q.f = a.makefile('rw')
        b.sendall(b'{"error": {"class": "GenericError", "desc": "non"}}\n')
        with self.assertRaises(pilote.ErreurPilote):
            q.commande('screendump', filename='/x')

    def test_capture_valide_de_bout_en_bout(self):
        import shutil
        if not shutil.which('pnmtopng'):
            self.skipTest('netpbm absent : couvert par le test précédent avec simulation')
        with tempfile.TemporaryDirectory() as t:
            tmp, art = Path(t, 'tmp'), Path(t, 'art')
            tmp.mkdir(), art.mkdir()
            info = pilote.capturer(self.faux_qmp(ppm()), tmp, art, 'interaction', 3, 0, [])
            self.assertTrue(info['valide'], info)
            self.assertEqual(len(list(art.glob('capture-003-interaction-*.png'))), 1)


class TestEchecs(unittest.TestCase):
    def lancer(self, *args, **patches):
        with tempfile.TemporaryDirectory() as t:
            art = Path(t, 'art')
            with mock.patch.object(pilote.os, 'access', return_value=patches.get('acces', True)), \
                    mock.patch.object(pilote.shutil, 'which', return_value=patches.get('qemu', '/usr/bin/qemu')):
                with self.assertRaises(SystemExit) as sortie:
                    pilote.main(['--iso', '/inexistant.iso', '--artefacts', str(art), *args])
            rapport = json.loads(Path(art, 'rapport.json').read_text())
            return sortie.exception.code, rapport, Path(art, 'resume.md').exists()

    def test_kvm_indisponible_code_2_avec_rapport(self):
        code, rapport, resume = self.lancer(acces=False)
        self.assertEqual((code, rapport['code'], resume), (2, 2, True))

    def test_iso_illisible_code_3_avec_rapport(self):
        with mock.patch.object(pilote.subprocess, 'run', side_effect=FileNotFoundError('xorriso')):
            code, rapport, resume = self.lancer()
        self.assertEqual(code, 3)
        self.assertIn('erreur_pilote', rapport)
        self.assertTrue(resume)


class TestGardesSecurite(unittest.TestCase):
    def test_aucune_permission_kwin_desactivee(self):
        for f in DOSSIER.iterdir():
            if f.suffix in {'.py', '.sh', '.env'} and f.name != 'test':
                code = '\n'.join(l for l in f.read_text().splitlines() if not l.lstrip().startswith('#'))
                self.assertNotIn('NO_PERMISSION_CHECKS', code, f.name)

    def test_invite_sans_display_ni_xwayland_force(self):
        texte = (DOSSIER / 'invite.sh').read_text()
        self.assertIn('DISPLAY=*|XAUTHORITY=*|QT_QPA_PLATFORM=*', texte)
        self.assertNotIn('QT_QPA_PLATFORM=xcb', texte)
        self.assertNotIn('--xwayland', texte)

    def test_scripts_shell_syntaxe(self):
        for nom in ('invite.sh', 'sonde_kvm.sh', 'recuperer_image.sh', 'preparer_depot.sh', 'conteneur.sh'):
            subprocess.run(['bash', '-n', str(DOSSIER / nom)], check=True)

    def test_reseau_invite_restreint_et_selinux_par_defaut(self):
        source = (DOSSIER / 'pilote.py').read_text()
        self.assertIn('restrict=on', source)
        self.assertIn("default='enforcing'", source)


if __name__ == '__main__':
    unittest.main()
