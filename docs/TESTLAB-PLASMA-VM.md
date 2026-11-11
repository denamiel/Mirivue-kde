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
- [ ] Choisir une image Fedora KDE vérifiable et documenter sa provenance
  (version, somme de contrôle et méthode de vérification de l'éditeur).
- [ ] Construire un hôte et un invité entièrement jetables, sans secrets ni
  répertoires personnels montés, avec des délais et un nettoyage bornés.
- [ ] Démarrer une session Plasma Wayland réelle, et relever la présence
  effective des services requis : `plasmashell`, `kwin_wayland`,
  `xdg-desktop-portal-kde` et composants pertinents.
- [ ] Vérifier que Mirivue utilise le greffon Qt Wayland et non XWayland,
  en collectant des preuves reproductibles, pas seulement des variables.
- [ ] Démontrer un scénario minimal nouveau, indépendant des 19 anciens essais.
- [ ] Démontrer qu'un échec réel du guest rend le job non vert et laisse des
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
| Provenance de l'image | Non sélectionnée |
| Session Plasma Wayland réelle | Non démontrée |
| Scénario graphique | Non exécuté |
| Chemin d'échec et diagnostic | Partiel : la sonde sort en code 2 si KVM est inutilisable. Un premier essai a révélé un faux vert (`\| tee` sans `pipefail`), corrigé ; l'échec réel du job n'a pas encore été provoqué volontairement. |
| Durée / coût | Sonde complète : ~30 s sur 4 vCPU. Guest non mesuré. Coût non évalué (dépendra de la visibilité du dépôt). |

**Seule la faisabilité de KVM est établie.** Aucun guest Fedora KDE n'a été démarré :
la validation d'une véritable session Plasma Wayland reste entièrement à faire. Cette
documentation ne doit pas être interprétée comme une validation de session Plasma.
