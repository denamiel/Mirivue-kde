# TestLab — Session Plasma Wayland complète (étude)

**Statut :** preuve de faisabilité obtenue, **job informatif** (pas un contrôle obligatoire). Une VM
Fedora KDE jetable démarre une vraie session Plasma Wayland et y lance le RPM Mirivue du commit testé
(trois essais verts sur un même commit, voir « Résultats »). Ce n'est pas encore un banc validé :
interaction clavier/souris seulement à l'état de prototype (un essai), stabilité non établie
(verdict « INSUFFISANT », voir « Mesure de stabilité ») (voir « Limites connues »).

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
| Chemin d'échec et diagnostic | Job `vm-echec-force` : `plasmashell` est arrêté dans l'invité ; le pilote doit sortir en **code 1**, avec rapport, captures valides et journal ; le job n'est vert que si c'est le cas (code 3 ⇒ rouge : cela s'est produit lors de la mise au point). Codes : 0 prouvé, 1 preuves invalides, 2 KVM indisponible, 3 invité muet/délai/pilote. Tests unitaires (`tests/test_testlab_plasma_vm.py`, 20 tests ; un test de bout en bout des captures est ignoré si `netpbm` est absent et s'exécute dans le job CI) : analyse du journal, verdict sur chaque altération, captures (PPM/PNG/QMP/`pnmtopng`), codes 2 et 3. Runs rouges réels de mise au point conservés dans l'historique. |
| Nettoyage / hôte | Chaque job VM vérifie après coup : aucun QEMU restant, répertoire temporaire de la VM effacé, arbre de travail inchangé, `/dev/kvm` avant/après (`660`→`666`, seule modification). Aucun nœud DRM de l'hôte n'est utilisé (`virtio-vga` est émulé par QEMU) ; ces vérifications sont dans `etat-hote.md`. |
| Durée / coût | 3 essais : 190 s, 198 s, 191 s de pilotage (login série ~91–100 s, fenêtre Mirivue ~151–159 s), plus construction du RPM, dépôt hors ligne et ISO (en cache ou 3,5 Go). Minutes de runner standard (dépôt public). |
| Stabilité | **3 essais sur 3 verts, lancés en parallèle sur un seul commit (`1f19f7a`).** Les runs précédents du scénario Mirivue (commits `85014f6`, `2eee0aa`, `1b8be71`) étaient rouges pour des défauts de mise au point, corrigés depuis. Une seule série verte ne suffit pas pour conclure sur les intermittences : à répéter sur plusieurs commits et plusieurs jours avant toute promotion. |

## Saisie clavier/souris (prototype)

**Mécanisme.** L'**hôte** injecte les entrées par QMP : `send-key` (clavier PS/2 virtuel) et
`input-send-event` (pointeur absolu d'une tablette USB virtuelle `usb-tablet`, ajoutée seulement avec
`--saisie`). Aucun `KWIN_WAYLAND_NO_PERMISSION_CHECKS`, aucun `fake_input` : l'invité voit un vrai clavier et
une vraie tablette, comme avec du matériel (garde dans les tests). La synchronisation passe par le marqueur
série `TESTLAB-ATTENTE-SAISIE` ; l'hôte capture l'écran avant (`saisie-avant`), injecte, puis l'invité attend
l'effet.

**Opération réelle.** Clic au centre (focus), `Entrée` (ferme « Premiers pas »), `Ctrl+L`, `Échap`,
`Ctrl+Maj+N`, saisie de « Dossier TestLab 1 », `Entrée` : la même séquence que le scénario X11. Le script de
l'invité (root) **ne crée jamais** le dossier (test de garde) ; il constate qu'il existe, que son propriétaire
est `liveuser` (donc créé par Mirivue et KIO), que le contenu du dossier jetable est exactement
`Dossier TestLab 1` + `a.txt` et que `a.txt` est intact (SHA-256). Captures valides avant/après exigées.

**Résultat (run [43067439480](https://github.com/denamiel/Mirivue-kde/actions/runs/43067439480), `16902a5`,
artefact `vm-saisie`) :** code 0, mesures `saisie_dossier_cree=oui`, `saisie_proprietaire=liveuser`,
`saisie_fichier_intact=oui` ; la capture « avant » montre la boîte « Premiers pas » et `a.txt` seul, la
capture « après » montre le dossier créé (barre d'état « 1 dossier, 1 fichier »). **Un seul essai** : ce
prototype n'a pas de mesure de stabilité. Limites : positions en coordonnées d'écran fixes (clic au centre),
pauses fixes côté hôte, une seule opération (création de dossier) ; renommer, copier, supprimer (corbeille)
restent à écrire sur le même modèle. Le job reste **informatif**.

## Mesure de stabilité (protocole)

Outil : `tests/testlab/plasma_vm/stabilite.py`, qui lit les exécutions réelles de l'API GitHub.
Un **essai** est un job `vm-mirivue` ; il est compté seulement s'il a atteint l'étape « Démarrer l'invité »
(une panne avant, par exemple réseau ou cache, est classée **infrastructure**, exclue du taux mais rapportée).
Une **exécution indépendante** est une exécution du workflow espacée d'au moins 2 h de la précédente retenue :
les trois essais parallèles d'une même exécution ne sont pas indépendants. **Seuil proposé** (à faire relire) :
au moins 30 essais comptés issus d'exécutions indépendantes, sur au moins 24 h, sans aucun échec du TestLab
(règle de trois : 0 échec sur 30 ⇒ taux d'échec < 10 % à 95 %). Tout échec doit être analysé
individuellement. Sans données suffisantes, le verdict est « INSUFFISANT ».

**Mesure au 11 novembre 2026 (17 h 40 UTC) :** 4 exécutions du scénario complet (`1f19f7a`, `2bf5c1b`,
`9d7ac36`, `16902a5`) mais seulement **1 indépendante** (toutes dans une fenêtre de 1 h 20) : 3 essais
comptés, 0 échec du TestLab, 0 panne d'infrastructure, étalement 0 h. **Verdict : INSUFFISANT.** La
stabilité n'est donc **pas** établie. Les exécutions doivent s'espacer dans le temps (relances manuelles
`workflow_dispatch` ou push) ; aucune surveillance automatique n'est active.

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
- Pilotage par la console série (connexion `liveuser`, `sudo`) : aucun `KWIN_WAYLAND_NO_PERMISSION_CHECKS`
  (test de garde dans la suite). Les entrées clavier/souris du prototype passent par QMP, côté hôte,
  sans élargir ce que l'invité peut faire ni ce qui en sort.
- Workflow distinct, **informatif**, déclenché par ses propres fichiers ou à la main ; aucun lien avec
  COPR/Pacman ni les contrôles obligatoires.

## Limites connues

- **Session live** (`liveuser`, autologin) et non une installation Fedora ; démarrage direct du noyau de
  l'ISO (chargeur et UEFI non testés) ; verrouillage d'écran désactivé dans l'invité.
- Mirivue est rendu gestionnaire de fichiers par défaut **dans l'invité** pour posséder `FileManager1` ;
  ce n'est pas le comportement d'une session où Dolphin reste le défaut.
- **Clavier/souris : prototype informatif seulement** (job `vm-saisie`, option `--saisie`). Le scénario
  standard (`vm-mirivue`) n'injecte aucune entrée et ne vérifie pas d'action de fichier de Mirivue ; le
  prototype est décrit dans « Saisie clavier/souris (prototype) ».
- La boîte « Premiers pas avec Mirivue » (première exécution) reste affichée sur les captures.
- Les paquets du dépôt hors ligne sont **vérifiés sur l'hôte** ; dans l'invité, `gpgcheck=0` s'applique au
  dépôt local (le RPM de Mirivue n'est pas signé).
- Le checkout du workflow est la référence de fusion de la PR, pas le seul commit de tête.
- Le verdict ne vérifie pas le fonctionnement des portails au-delà de leur présence.
- 3 essais verts sur un commit : pas de mesure d'intermittence à long terme ; `clocksource`/délais non exclus.
- Hors périmètre de cette PR, constaté sans y avoir touché : dans `fedora-package.yml`, les deux jobs
  « Python » installent des bibliothèques par `apt` (lignes 223-224) et ont échoué sur le run
  [43054343691](https://github.com/denamiel/Mirivue-kde/actions/runs/43054343691) avec
  `Temporary failure resolving` (miroirs Ubuntu), alors que les jobs RPM, Xvfb et KWin virtuel de ce
  même run sont verts. Ce workflow est donc rouge pour une raison d'infrastructure indépendante du TestLab Plasma.

Cette documentation ne revendique pas de validation de Mirivue au-delà de ce scénario minimal.
