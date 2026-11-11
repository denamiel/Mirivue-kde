# TestLab — Session Plasma Wayland complète (étude)

**Statut :** étude et preuve de faisabilité à réaliser. Aucun banc Plasma complet n'est encore validé.

Suivi : [issue #12](https://github.com/denamiel/Mirivue-kde/issues/12).

## Point de départ

Les suites X11/Xvfb (PR #9) et KWin Wayland virtuel (PR #10) sont intégrées dans
`main`. Elles n'exécutent **pas** une session Plasma complète. Elles ne valident
pas `plasmashell`, les portails KDE, les services de session, ni les périphériques
de l'utilisateur. Les 19 essais manuels historiques ne sont pas à rejouer.

## Phase 1 — Prouver la faisabilité avant de modifier les workflows

- [x] Vérifier les ressources, coûts, permissions et capacités KVM du runner
  envisagé, **sans supposer** que `/dev/kvm` est disponible.
- [x] Choisir une image Fedora KDE vérifiable et documenter sa provenance
  (version, somme de contrôle et méthode de vérification de l'éditeur).
- [x] Construire un hôte et un invité entièrement jetables, sans secrets ni
  répertoires personnels montés, avec des délais et un nettoyage bornés.
- [x] Démarrer une session Plasma Wayland réelle, et relever la présence
  effective des services requis : `plasmashell`, `kwin_wayland`,
  `xdg-desktop-portal-kde` et composants pertinents.
- [x] Vérifier que Mirivue utilise le greffon Qt Wayland et non XWayland,
  en collectant des preuves reproductibles, pas seulement des variables.
- [x] Démontrer un scénario minimal nouveau, indépendant des 19 anciens essais.
- [x] Démontrer qu'un échec réel du guest rend le job non vert et laisse des
  journaux/captures permettant son diagnostic.
- [ ] Mesurer la durée, le coût et les éventuels échecs intermittents (**partiel** : 3 essais
  consécutifs verts sur un seul commit ; durée mesurée ; intermittences à surveiller sur plus de runs).

## Critères de sécurité et de revue

Aucun test de PR non fiable sur un runner personnel. Pas d'accès SSH permanent,
pas de partage du HOME réel, pas de clé privée COPR/Pacman, pas de publication.
Aucune utilisation de `KWIN_WAYLAND_NO_PERMISSION_CHECKS` dans une session
personnelle ; tout mécanisme privilégié doit être limité à l'invité jetable.

Les tests de VM sont d'abord **informatifs** ou déclenchés manuellement. Leur
promotion en contrôle obligatoire exige des exécutions reproductibles et une
revue séparée. Les protections de `main` et des publications restent inchangées.

## Résultats

À partir d'exécutions réelles et d'artefacts CI uniquement.

**Dernier résultat complet :** run [43054343497](https://github.com/denamiel/Mirivue-kde/actions/runs/43054343497)
(`1f19f7a`, workflow informatif `testlab-plasma-vm.yml`) : sonde KVM, tests du pilote, RPM, **trois essais
Mirivue** et test négatif tous verts. Le checkout de ce workflow est la référence de fusion de la PR
(`refs/pull/13/merge`, commit `d8d28ee`), identique pour le job RPM et les jobs VM.

| Mesure | Résultat |
|---|---|
| Hôte / capacités KVM | `ubuntu-latest` (Hyper-V, `kvm_amd`, nested=1, 4 vCPU, ~16 Go RAM, 86 Go disque). `/dev/kvm` en `660 root:kvm` par défaut ; une règle udev l'ouvre en `666` **sur le seul runner éphémère** (état avant/après consigné). `KVM_GET_API_VERSION` = 12. |
| Provenance de l'image | `Fedora-KDE-Desktop-Live-45-1.4.x86_64.iso` ; CHECKSUM signé par la clé « Fedora (45) » `4F50 A611 4CD5 C697 6A7F 1179 655A 4B02 F577 861E` (épinglée dans `image.env`) ; SHA-256 recoupé (signé, dépôt, fichier). Échec ⇒ aucune VM. |
| Session Plasma Wayland réelle | **Prouvée** : `loginctl` `Type=wayland`/`Desktop=KDE`/`active` ; `plasmashell` Wayland (Qt Wayland, sans `xcb`) ; `kwin_wayland` 6.8.1, `xdg-desktop-portal`, `xdg-desktop-portal-kde` ; noms D-Bus KWin, plasmashell, portails. **SELinux `Enforcing`** (plus de `enforcing=0`). |
| RPM du commit, hors ligne | `mirivue-kde-1.0.0-0.201.beta6.1.fc45.x86_64` construit par le job `rpm` du même workflow ; SHA-256 du RPM remis à l'invité = SHA-256 attendu ; NEVRA installé = NEVRA attendu. Dépendances manquantes calculées par `dnf` **contre la base RPM de l'ISO** : 7 paquets Fedora (`kf6-kio`, `mediainfo`, `mkvtoolnix`, `python3-mutagen`, `perl-Image-ExifTool`, `libebml`, `libmatroska`, ~12 Mio), tous signés par la clé Fedora 45 épinglée (vérifié sur l'hôte avant la mise en média). Installation dans l'invité par `dnf` avec `reposdir` vide et dépôt `file://` (`gpgcheck=0` **dans l'invité seulement** : l'intégrité est établie sur l'hôte). |
| Invité sans réseau | `reseau=absent` constaté dans l'invité (`curl` en échec) ; `-nic user,restrict=on`. |
| Mirivue lancé en Wayland natif | Lancé **sans `DISPLAY`, `XAUTHORITY` ni `QT_QPA_PLATFORM`** dans l'environnement exact de la session. Fenêtre `alpha — Mirivue` (classe `org.pdenams.Mirivue.Qt`) vue par KWin (interface publique KRunner + `getWindowInfo`, sans script ni droit particulier). Processus : `XDG_SESSION_TYPE=wayland`, 4 mappings `libqwayland`, 0 `libqxcb`, **1 connexion vers `kwin_wayland`, 0 vers `Xwayland`** (inodes pairs). |
| Scénario graphique (fichiers jetables) | Dossiers `~/testlab-mirivue/{alpha,beta}` dans l'invité. Mirivue, gestionnaire par défaut **de cette session jetable**, possède `org.freedesktop.FileManager1` (PID = celui de Mirivue). Un appel `ShowFolders` d'un autre client de la session ouvre la fenêtre `beta — Mirivue` (aussi Wayland natif : 0 `xcb`, 0 socket X11, 1 connexion `kwin_wayland`). Arrêt par `SIGTERM` : processus terminé. Captures valides pour les jalons `session`, `mirivue-ouvert`, `interaction`. |
| Chemin d'échec et diagnostic | Job `vm-echec-force` : `plasmashell` est arrêté dans l'invité ; le pilote doit sortir en **code 1**, avec rapport, captures valides et journal ; le job n'est vert que si c'est le cas (code 3 ⇒ rouge : cela s'est produit lors de la mise au point). Codes : 0 prouvé, 1 preuves invalides, 2 KVM indisponible, 3 invité muet/délai/pilote. Tests unitaires (`tests/test_testlab_plasma_vm.py`, 20 tests) : analyse du journal, verdict sur chaque altération, captures (PPM/PNG/QMP/`pnmtopng`), codes 2 et 3. Runs rouges réels de mise au point conservés dans l'historique. |
| Nettoyage / hôte | Chaque job VM vérifie après coup : aucun QEMU restant, répertoire temporaire de la VM effacé, arbre de travail inchangé, `/dev/kvm` avant/après (`660`→`666`, seule modification). Aucun nœud DRM de l'hôte n'est utilisé (`virtio-vga` est émulé par QEMU) ; ces vérifications sont dans `etat-hote.md`. |
| Durée / coût | 3 essais : 190 s, 198 s, 191 s de pilotage (login série ~91–100 s, fenêtre Mirivue ~151–159 s), plus construction du RPM, dépôt hors ligne et ISO (en cache ou 3,5 Go). Minutes de runner standard (dépôt public). |
| Stabilité | **3/3 verts sur un même commit ; chemin positif jamais rouge une fois les défauts de mise au point corrigés.** Insuffisant pour conclure sur les intermittences : à répéter sur plusieurs commits/jours avant toute promotion. |

## Architecture et frontière de confiance

- Hôte : runner GitHub éphémère ; **aucun `apt`** (les miroirs Ubuntu ont été injoignables pendant plus de
  30 minutes : `Temporary failure resolving 'security.ubuntu.com'`). Les outils viennent de `dnf` dans un
  conteneur `fedora:45` jetable (`conteneur.sh`) qui ne reçoit que `/dev/kvm`, le dépôt, le cache ISO en
  lecture seule et `RUNNER_TEMP` (pas de `--privileged`, aucun secret).
- Invité : ISO officielle vérifiée en lecture seule, noyau et initrd extraits de cette ISO ; **pas de
  réseau**, aucun dossier de l'hôte, aucun secret ni jeton, aucun `HOME` réel. Le média de scripts (ISO
  en lecture seule) contient `invite.sh`, `fenetres.py`, `connexions.py` et le dépôt RPM.
- Sortent : console série, captures QMP, rapports. Le pilote efface son répertoire temporaire ; le
  runner est détruit ensuite.
- Pilotage par la console série (connexion `liveuser`, `sudo`) : aucune injection, aucun
  `KWIN_WAYLAND_NO_PERMISSION_CHECKS` (test de garde dans la suite).
- Workflow distinct, **informatif**, déclenché par ses propres fichiers ou à la main ; aucun lien avec
  COPR/Pacman ni les contrôles obligatoires.

## Limites connues

- **Session live** (`liveuser`, autologin) et non une installation Fedora ; démarrage direct du noyau de
  l'ISO (chargeur et UEFI non testés) ; verrouillage d'écran désactivé dans l'invité.
- Mirivue est rendu gestionnaire de fichiers par défaut **dans l'invité** pour posséder `FileManager1` ;
  ce n'est pas le comportement d'une session où Dolphin reste le défaut.
- **Aucune interaction clavier/souris** : le scénario vérifie l'ouverture de fenêtres, l'appartenance du
  service D-Bus et l'ouverture d'un dossier par `FileManager1`, pas les actions de fichiers de Mirivue.
  Aucune injection d'entrée n'est utilisée (frontière de confiance).
- La boîte « Premiers pas avec Mirivue » (première exécution) reste affichée sur les captures.
- Les paquets du dépôt hors ligne sont **vérifiés sur l'hôte** ; dans l'invité, `gpgcheck=0` s'applique au
  dépôt local (le RPM de Mirivue n'est pas signé).
- Le checkout du workflow est la référence de fusion de la PR, pas le seul commit de tête.
- Le verdict ne vérifie pas le fonctionnement des portails au-delà de leur présence.
- 3 essais verts sur un commit : pas de mesure d'intermittence à long terme ; `clocksource`/délais non exclus.
- Les workflows existants `fedora-package.yml` (jobs Python) utilisent `apt` et ont échoué pendant la
  panne DNS ; hors périmètre de cette PR, signalé tel quel.

Cette documentation ne revendique pas de validation de Mirivue au-delà de ce scénario minimal.
