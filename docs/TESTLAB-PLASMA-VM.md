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
- [ ] Construire un hôte et un invité entièrement jetables, sans secrets ni
  répertoires personnels montés, avec des délais et un nettoyage bornés.
- [x] Démarrer une session Plasma Wayland réelle, et relever la présence
  effective des services requis : `plasmashell`, `kwin_wayland`,
  `xdg-desktop-portal-kde` et composants pertinents.
- [ ] Vérifier que Mirivue utilise le greffon Qt Wayland et non XWayland,
  en collectant des preuves reproductibles, pas seulement des variables.
- [ ] Démontrer un scénario minimal nouveau, indépendant des 19 anciens essais.
- [x] Démontrer qu'un échec réel du guest rend le job non vert et laisse des
  journaux/captures permettant son diagnostic.
- [ ] Mesurer la durée, le coût et les éventuels échecs intermittents.

## Critères de sécurité et de revue

Aucun test de PR non fiable sur un runner personnel. Pas d'accès SSH permanent,
pas de partage du HOME réel, pas de clé privée COPR/Pacman, pas de publication.
Aucune utilisation de `KWIN_WAYLAND_NO_PERMISSION_CHECKS` dans une session
personnelle ; tout mécanisme privilégié doit être limité à l'invité jetable.

Les tests de VM sont d'abord **informatifs** ou déclenchés manuellement. Leur
promotion en contrôle obligatoire exige des exécutions reproductibles et une
revue séparée. Les protections de `main` et des publications restent inchangées.

## Résultats

À compléter uniquement à partir d'exécutions réelles et d'artefacts CI :

| Mesure | Résultat |
|---|---|
| Hôte / capacités KVM (faisabilité de la virtualisation **uniquement**) | **Mesuré** (run [43011438021](https://github.com/denamiel/Mirivue-kde/actions/runs/43011438021)) : `ubuntu-latest`, hôte Hyper-V (`microsoft`), `kvm_amd`, indicateur `svm`, nested=1, 4 vCPU, ~16 Go de RAM, 86 Go de disque. `/dev/kvm` **existe mais n'est pas accessible** au compte du runner par défaut ; une règle udev (`MODE=0666`, VM éphémère uniquement) l'ouvre, après quoi `KVM_GET_API_VERSION` = 12. QEMU 8.2.2 et OVMF installés par `apt` en ~24 s. |
| Provenance de l'image | `Fedora-KDE-Desktop-Live-45-1.4.x86_64.iso` (miroir `dl.fedoraproject.org`). Fichier CHECKSUM signé par la clé « Fedora (45) » `4F50 A611 4CD5 C697 6A7F 1179 655A 4B02 F577 861E` (empreinte épinglée dans `image.env`) ; SHA-256 `79703d9f…97a5` identique dans le CHECKSUM signé, dans le dépôt et recalculé sur le fichier téléchargé. Aucune VM n'est lancée si l'une des vérifications échoue. |
| Session Plasma Wayland réelle | **Démontrée dans l'invité** (run [43020867755](https://github.com/denamiel/Mirivue-kde/actions/runs/43020867755), vert) : Fedora 45 KDE Plasma Desktop Edition, noyau 7.2.11, `plasma-workspace` 6.8.1, KWin 6.8.1 ; `loginctl` : `Type=wayland`, `Desktop=KDE`, `State=active` ; `plasmashell` avec `XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-1`, greffon Qt Wayland chargé et aucun `xcb` (mappings mémoire) ; processus `kwin_wayland`, `xdg-desktop-portal`, `xdg-desktop-portal-kde`, `kded6` ; noms D-Bus `org.kde.KWin`, `org.kde.plasmashell`, `org.freedesktop.portal.Desktop`, `org.freedesktop.impl.portal.desktop.kde`. Capture : bureau Plasma avec Welcome Center. |
| Scénario graphique | **Mirivue non encore lancé** : le RPM construit par le même commit n'est pas encore transmis à l'invité. Seules sont prouvées la session et ses services. |
| Chemin d'échec et diagnostic | **Démontré involontairement** par les runs de mise au point 43012540749, 43013082876, 43013524841 (jobs rouges, rapport et journaux conservés : QEMU refusant une option, invité muet après 1200 s) ; run 43017519806 : verdict `code 1` sur des preuves insuffisantes. Codes : 0 prouvé, 1 preuves invalides, 2 KVM indisponible, 3 invité muet/délai. Pas encore de test volontaire dédié dans la CI. |
| Durée / coût | Run vert : invité muni de la session en ~250 s, job complet ~291 s de pilotage (jalons hôte : `virtio_gpu` 96 s, invite de connexion série 231 s, script 249–279 s) hors téléchargement de l'ISO (3,5 Go, durée variable selon le miroir, de quelques minutes à plus de 10 min) ; 1 run vert sur 5 : résultat unique, **variabilité non mesurée**. Dépôt public : minutes de runner standard sans coût direct. |

**Conclusion provisoire, sur un seul run vert.** KVM est utilisable sur `ubuntu-latest` et une
véritable session Plasma Wayland démarre dans un invité Fedora 45 KDE jetable. Mirivue n'y a pas
encore été lancé et aucune répétition n'a mesuré la stabilité.

## Architecture et frontière de confiance

- Hôte : runner GitHub éphémère ; `/dev/kvm` ouvert par règle udev **sur ce seul runner**.
- Invité : ISO officielle vérifiée en lecture seule, noyau et initrd extraits de cette ISO ; **pas de
  réseau** (`-nic user,restrict=on`), aucun dossier de l'hôte, aucun secret ni jeton, aucun `HOME` réel.
- Seuls entrent l'ISO et un ISO de scripts (`invite.sh`) ; sortent la console série, des captures QMP
  et les rapports. Le pilote efface son répertoire temporaire, le runner est détruit ensuite.
- Pilotage par la console série (connexion `liveuser`, `sudo`) : aucune injection ni
  `KWIN_WAYLAND_NO_PERMISSION_CHECKS`.
- Workflow `testlab-plasma-vm.yml` distinct, **informatif**, déclenché seulement par ses propres
  fichiers ou à la main ; aucun lien avec les publications COPR/Pacman ni les contrôles obligatoires.

## Limites connues

- **SELinux en mode permissif** dans l'invité (`enforcing=0`) : écart avec un Fedora installé.
- Session **live** (`liveuser`, autologin) et non une installation ; le verrouillage d'écran est désactivé.
- `Xwayland` tourne dans la session (comportement normal de Plasma) : « pas de repli XWayland »
  reste à prouver **pour Mirivue** quand il sera lancé.
- Démarrage direct du noyau de l'ISO : le chargeur et le démarrage UEFI ne sont pas testés.
- Le RPM n'a pas encore été installé : l'invité n'a pas de réseau et le paquet doit lui être fourni
  hors ligne, avec ses dépendances.
- Faux positifs possibles : le verdict ne vérifie que des processus, des noms D-Bus et des mappings
  mémoire, pas la fonctionnalité des portails.
- Les artefacts ne contiennent que l'image Live publique, sans donnée personnelle.
- Une défaillance intermittente (délais, `clocksource`) n'est pas exclue.

Cette documentation ne doit pas être interprétée comme une validation de Mirivue sous Plasma.
