# Mirivue TestLab — validation des évolutions futures

> État : **première tranche opérationnelle** (PR n° 9). Le banc démarre le RPM
> installé dans une vraie fenêtre X11 sous Xvfb et le pilote au clavier. Il est
> **obligatoire avant toute publication COPR**. Il ne constitue **pas** une
> validation Wayland ou Plasma : chaque rapport l'indique dans son champ `couverture`.
> Il ne relance **pas** la campagne de 19 essais manuels de la bêta 5 : ses
> résultats restent historiques.

## Finalité

Pour chaque future évolution de Mirivue KDE, obtenir une preuve reproductible :
tests pertinents, capture d'écran en cas d'échec, journaux des assistants KIO,
résultats d'installation des paquets et distinction explicite entre simulation
et session Plasma réelle. Réduire au strict minimum les vérifications manuelles.

## Niveaux de test

| Niveau | Environnement exact | Ce qu'il prouve | Ce qu'il ne prouve pas |
|---|---|---|---|
| A — Python/Qt | `QT_QPA_PLATFORM=offscreen`, aucun serveur graphique | Logique, modèles, widgets construits et pilotés par QtTest | Rendu, focus réel, saisie clavier du système |
| B — KIO natif | Assistants KIO compilés, `dbus-run-session`, HOME/XDG jetables | Opérations de fichiers réelles (copie, corbeille, URL) | Interface graphique |
| C — Installation | RPM Fedora 44/45/Rawhide, paquet Arch | Dépendances, fichiers installés, `--smoke-test` | Comportement interactif |
| **X — TestLab Xvfb** | RPM installé, Xvfb 1280×800 **sans gestionnaire de fenêtres**, D-Bus privé, saisie XTEST | Vraie fenêtre, vraie boucle d'évènements, raccourcis, boîtes de dialogue, presse-papiers X11, résultat sur le disque | Wayland, KWin, Plasma, décorations, glisser-déposer entre applications |
| D — Bureau réel | Plasma Wayland (VM éphémère, à construire) | Intégration au bureau | — |
| E — Matériel | Disques externes, NTFS, périphériques | Montages, coupures | — |

Un succès au niveau X n'est **pas** une validation KDE Wayland : le rapport
le rappelle dans son champ `environnement.limite`.

## Inventaire des suites existantes (8 novembre 2026)

- 133 fichiers `tests/test_*.py` existaient avant TestLab, avec environ 660 méthodes de test.
- Seules **33 suites** sont exécutées par la CI : 18 par `packaging/check_python_runtime.py`
  et 15 dans l'étape « Régressions graphiques » du job RPM.
- Sur les 19 suites `*_gui`, 10 tournent en CI. Les 9 autres ne tournent que localement :
  `ergonomics_gui`, `folder_display_gui`, `header_double_click_gui`, `keyboard_gui`,
  `launch_main_gui`, `pane_regressions_gui`, `rc181_panes_gui`, `select_all_shortcut_gui` et `tabs_gui`.
- Toutes les suites graphiques existantes utilisent la plateforme Qt `offscreen` (niveau A).
  Aucune n'utilisait un serveur X, Xvfb ou une session Plasma avant TestLab.
- 43 fichiers créent une `QApplication`, dont 19 avec QtTest.
  12 fichiers utilisent les assistants KIO natifs (niveau B), 4 un bus D-Bus privé,
  et 27 lancent des sous-processus. Les 80 autres n'importent pas Qt.

Intégrer les 9 suites `*_gui` restantes à la CI est une étape distincte. Il faut d'abord
qualifier leur stabilité : `pane_regressions_gui` contient un blocage connu sur une
boîte modale.

## Le harness (`tests/testlab/`)

| Fichier | Rôle |
|---|---|
| `harness.py` | Classe `Lab` : session jetable, pilotage X11, captures, rapports, nettoyage |
| `scenarios.py` | Scénarios de bout en bout (`nouveau-dossier`, `controle-echec`) |
| `run.py` | Exécution d'un scénario en ligne de commande, codes de sortie |
| `xwd.py` | Conversion XWD → PNG sans dépendance tierce |
| `../test_testlab_harness.py` | Tests du harness lui-même |

### Isolation et confinement : ce qui est garanti, et ce qui ne l'est pas

TestLab combine deux mécanismes différents. Il ne faut pas les confondre.

**1. Isolation d'environnement (toujours active).**
- L'environnement de l'application est entièrement reconstruit : seul `PATH` est hérité.
- `HOME`, tous les `XDG_*_HOME`, `XDG_RUNTIME_DIR` et `TMPDIR` pointent dans un dossier
  `mirivue-testlab-*`, créé sous `MIRIVUE_TESTLAB_TMP` (par défaut `/tmp`). Ce dossier est
  refusé s'il se trouve dans un dossier personnel.
- La corbeille KIO est donc `XDG_DATA_HOME/Trash`, elle aussi jetable.
- Xvfb choisit lui-même un numéro d'affichage libre (`-displayfd`), sans TCP, avec un cookie
  propre à la session. Un `dbus-daemon --session` privé écoute dans le dossier jetable.

Cela redirige un programme qui respecte ces variables. **Cela n'empêche pas** un processus
d'écrire ailleurs avec ses propres droits : par exemple via `getpwuid()`, un chemin absolu ou
un volume monté.

**2. Confinement du système de fichiers (choisi automatiquement, indiqué dans le rapport).**

| Mode | Quand | Effet |
|---|---|---|
| `uid` | Harness lancé en root (conteneur CI) | L'application et son bus tournent sous un compte non privilégié dédié (`MIRIVUE_TESTLAB_USER`), sans dossier personnel ni groupe. Ce compte ne possède que le dossier jetable : il ne peut écrire ni dans le `HOME` du job, ni dans l'espace de travail, ni dans le système. Le compte est refusé s'il exécute déjà un processus. |
| `bwrap` | Utilisateur ordinaire avec bubblewrap | Système monté en lecture seule. Les dossiers personnels et `/run/user/<uid>` (vrai bus de session, socket Wayland) sont masqués par des tmpfs vides. Le réseau est privé et seul le dossier jetable est inscriptible. |
| `aucun` | Ni root avec compte dédié, ni bubblewrap | Isolation d'environnement seule. Refusé quand `--exiger-confinement` ou `MIRIVUE_TESTLAB_REQUIRE_CONFINEMENT=1` est actif, ce qui est le cas en CI. |

En root, le harness **refuse** de lancer l'application sans compte dédié.

**3. Surveillance (détection, pas protection).** Des chemins sensibles des dossiers
personnels sont photographiés avant et après le scénario : préférences Mirivue, `kiorc`,
corbeille, Places et journaux. En CI, tout le `HOME` du job est surveillé
(`--surveiller "$HOME"`). Toute modification donne le code 3.

La comparaison ne porte que sur les chemins choisis, sur trois niveaux et au plus 20 000
entrées : elle peut révéler une écriture, elle ne peut pas prouver son absence.

**Limites de sécurité.**
- Le mode `uid` laisse le compte de test lire ce que le système rend lisible par tous.
- Le mode `bwrap` partage le noyau, les sockets abstraites X11 de l'hôte (sans leurs cookies)
  et les processus visibles.
- Aucun des deux ne protège contre une faille du noyau ou de Xvfb.

Une PR non fiable ne doit donc être exécutée **qu'en CI GitHub ou dans une VM ou un conteneur
jetable** qui ne monte aucun dossier personnel, jamais dans la session du propriétaire.
Aucun secret COPR ou Pacman n'est lu, et le job CI n'a que `contents: read`.

### Délais et nettoyage

- Le délai global du scénario vaut 180 s par défaut (`--delai`). Chaque attente est bornée
  par ce délai, et une alarme de sécurité interrompt le harness s'il bloque lui-même.
- En cas d'échec, le harness :
  1. prend une capture `echec.png` et la liste des fenêtres visibles ;
  2. envoie `SIGABRT` à l'application encore vivante, ce qui place dans son journal la pile
     Python de tous ses fils (`PYTHONFAULTHANDLER`).
- **Nettoyage, dans tous les cas :**
  1. arrêt de chaque groupe de processus (SIGTERM, puis SIGKILL) ;
  2. arrêt des processus détachés, retrouvés grâce au marqueur `MIRIVUE_TESTLAB_ROOT`
     de leur environnement ;
  3. arrêt de D-Bus et de Xvfb, puis suppression du dossier jetable ;
  4. **vérification** qu'il ne reste ni processus marqué, ni dossier, ni verrou X11.

  Les journaux de Mirivue (`XDG_STATE_HOME/mirivue`) sont copiés avant la suppression.

  Les processus de l'exécution sont reconnus à leur marqueur d'environnement, ou, en
  mode `uid`, à leur compte dédié : dans un conteneur, root ne peut pas lire l'environnement
  d'un autre UID sans CAP_SYS_PTRACE.
- **Panne du nettoyage lui-même :**
  - chaque étape s'exécute même si la précédente a échoué, et chaque erreur est inscrite
    dans `nettoyage.erreurs` ;
  - le code devient 3, mais le statut et l'erreur initiale du scénario sont conservés ;
  - les rapports JSON et JUnit sont écrits dans tous les cas. Si l'écriture elle-même échoue,
    le rapport complet est imprimé sur la sortie d'erreur et le code reste non nul.
- **Verrou X11 :** il n'est supprimé que si notre Xvfb s'est arrêté, que le verrou porte encore
  son PID, que ce PID n'est plus actif, que le fichier appartient à l'utilisateur courant et
  qu'il n'a pas été remplacé entre-temps (même inode, lien symbolique jamais suivi).

### Rapports et codes de sortie

`<artefacts>/rapport.json` : étapes, durées, captures, nettoyage, isolation, mode de confinement
et `couverture` (`x11_xvfb : couvert`, `wayland`, `kwin`, `plasma` et `glisser_deposer :
non couvert`). Ces rapports sont prévus pour être lus par un relecteur humain ou par
ChatGPT afin d'analyser un échec.

Autres fichiers :
`junit.xml`, `captures/*.png`, `journaux/*.log` (Xvfb, D-Bus, Mirivue, harness).

| Code | Signification |
|---|---|
| 0 | Scénario réussi, nettoyage et isolation vérifiés |
| 1 | Scénario en échec (capture et journaux conservés) |
| 2 | Environnement indisponible (outil absent) : aucune conclusion |
| 3 | Nettoyage incomplet ou écriture hors du dossier jetable |

### Utilisation

```bash
# CI ou conteneur jetable Fedora 45, en root, avec le RPM testé installé :
dnf -y install python3 xorg-x11-server-Xvfb xdotool xwd xclip dbus-daemon shadow-utils
useradd --system --no-create-home --home-dir /nonexistent --shell /sbin/nologin mirivue-testlab
export MIRIVUE_TESTLAB_USER=mirivue-testlab MIRIVUE_TESTLAB_REQUIRE_CONFINEMENT=1
python3 tests/testlab/run.py nouveau-dossier --artefacts /tmp/testlab-resultats
MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1 python3 -m unittest discover -s tests -p test_testlab_harness.py -v
```

Sur un poste de développement, en utilisateur ordinaire, le mode `bwrap` est choisi
automatiquement si bubblewrap fonctionne. Les PR non fiables restent réservées à la CI ou à
une VM ou un conteneur jetable (par exemple `podman run --rm`, avec le dépôt monté en
lecture seule et sans `HOME` monté).

## Scénario de référence : `nouveau-dossier`

Il représente une évolution typique (commande au clavier, boîte de dialogue, opération
KIO, mise à jour de la vue). Ses données sont créées par le scénario et ne
reprennent aucun essai historique.

1. Démarrer `mirivue-kde` (RPM installé) sur un dossier jetable contenant `Existant/` et `note.txt`.
2. Fermer la fenêtre « Premiers pas » avec Entrée.
3. Donner le focus à la vue (Ctrl+L, Échap), puis Ctrl+A et Ctrl+C : le presse-papiers X11
   contient exactement les deux URL attendues.
4. Ctrl+Maj+N, saisir `Dossier TestLab 1`, Entrée : le dossier existe sur le disque.
5. Recherche clavier dans la vue, puis Ctrl+C : seule l'URL du nouveau dossier est copiée.
6. Ctrl+Q : l'application se termine avec le code 0.
7. Contrôles finaux :
   - données jetables inchangées, hormis le nouveau dossier ;
   - préférences écrites dans le `XDG_CONFIG_HOME` jetable ;
   - corbeille vide.

`controle-echec` est le contrôle négatif. Il attend une fenêtre inexistante et doit
échouer avec le code 1, une capture `echec.png`, la liste des fenêtres, les journaux et un
nettoyage vérifié. `test_testlab_harness.py` l'exécute à chaque PR.

## Intégration CI et contrôles bloquants

Le job `testlab` de `fedora-package.yml` :
- dépend du job RPM Fedora 45 et installe **le RPM produit par ce même commit** ;
- crée le compte dédié `mirivue-testlab` et exige l'affichage et le confinement
  (`MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1` et `MIRIVUE_TESTLAB_REQUIRE_CONFINEMENT=1`) : un outil
  absent est un échec, et non un saut ;
- exécute les tests du harness, puis **trois fois** le scénario `nouveau-dossier`, pour suivre
  la stabilité du focus sous Xvfb sans gestionnaire de fenêtres ;
- publie `testlab-fedora-45` (rapports, captures et journaux, conservés 14 jours), même en
  cas d'échec.

**Publication COPR.** `publish.needs` vaut `[rpm, python, testlab]`.
- Un TestLab en échec, annulé ou ignoré empêche donc la publication.
- La condition de publication ne contient aucune fonction de statut (`always()`, etc.) :
  GitHub applique `success()` à chaque job requis.
- Les exigences d'autorisation restent inchangées : lancement manuel sur `main`,
  confirmation `PUBLIER`, puis approbation dans l'environnement protégé `publication-copr`.
- `tests/test_publication_controlee.py` vérifie ces trois points.

**Fusion dans `main`.** Les workflows seuls n'empêchent pas une fusion. Il faut une règle
GitHub. `packaging/protection-main.py` vérifie (`--verifier`, lecture seule) ou crée
(`--appliquer`, réservé au propriétaire) le ruleset « Mirivue — contrôles obligatoires ». Il impose :
- une pull request ;
- les contrôles `RPM KDE Fedora 44`, `RPM KDE Fedora 45`, `Python 3.11 — imports et fichiers`,
  `Python 3.x — imports et fichiers`, `TestLab — vraie fenêtre sous Xvfb (Fedora 45)` et `build`
  (Arch), tous émis par GitHub Actions ;
- une branche à jour ;
- ni suppression, ni réécriture de `main` ;
- aucun contournement.

`tests/test_protection_main.py` vérifie que ces noms correspondent aux vrais jobs.
**Tant que ce ruleset n'est pas appliqué, le TestLab ne bloque que la publication COPR, pas
la fusion.** Une CI verte n'est jamais une autorisation de publier.

Durées mesurées (exécution CI 42464579875, première version) : job complet en 2 min 14 s après
le RPM Fedora 45, tests du harness en 47 s et scénario en 11,8 s. Les durées de la version
actuelle figurent dans la PR.

## Limites connues de la tranche Xvfb

- **Pas de gestionnaire de fenêtres :** quand une boîte de dialogue se ferme, le focus X ne
  revient pas seul à la fenêtre principale. Les scénarios le rendent explicitement
  (`lab.focus`). Le retour de focus géré par KWin n'est donc pas testé.
- **Pas d'AT-SPI :** l'état interne est observé par des effets visibles de l'extérieur
  (titres de fenêtres, presse-papiers, fichiers, captures), et non par introspection
  des widgets.
- **Hors périmètre :** Wayland (portails, activation XDG, fractional scaling), menus
  globaux, notifications Plasma et glisser-déposer entre applications.

## Observations relevées par le banc (à confirmer en session Plasma)

Elles ne sont pas corrigées dans cette PR, qui se limite au banc de tests :

1. **Focus au démarrage :** Ctrl+C copie le texte « Home » du panneau Emplacements,
   alors que Dolphin donne le focus à la vue des fichiers.
2. **Nouveau dossier :** après Ctrl+Maj+N, le dossier créé n'est pas sélectionné
   (Dolphin le sélectionne).

## Suite proposée

1. **Wayland natif (PR distincte) :** KWin avec son backend virtuel dans le conteneur
   Fedora, l'application en `QT_QPA_PLATFORM=wayland` sans XWayland, et une saisie et des
   captures sans xdotool. Voir `docs/TESTLAB-WAYLAND.md` sur sa branche. Ce n'est pas une
   session Plasma complète.
2. **Plasma Wayland en VM éphémère :** Fedora KDE 45 démarrée depuis une image, sans
   connexion SSH à un poste personnel, détruite après chaque exécution, avec le même format
   de rapports. Un runner auto-hébergé n'est acceptable que s'il est isolé, éphémère et
   n'exécute pas les PR de forks.
3. **Variantes séparées :** NTFS en image loop, SFTP vers un `sshd` local jetable et SMB,
   chacune avec ses propres scénarios. Elles ne sont jamais supposées couvertes par Xvfb.
4. **Arch/CachyOS :** même harness dans un conteneur `archlinux` avec le paquet construit
   par `arch-package.yml`.
5. **Suites `*_gui` restantes :** les qualifier une par une avant de les ajouter à la CI.

## Contrat de validation d'une future PR

Chaque PR affectant le comportement utilisateur doit contenir :

1. **Scénario** : action, résultat attendu, données jetables nécessaires ;
2. **Niveau** : A/B/C/X/D/E ci-dessus et environnement exact ;
3. **Preuve automatique** : chemin des tests, résultat CI, artefact `testlab-fedora-45`
   quand une fenêtre est concernée ;
4. **Limites** : ce qui n'a pas été exécuté et pourquoi (par exemple, Wayland non couvert) ;
5. **Impact** : refus de fusion si un test obligatoire échoue, sauf dérogation documentée.

Ajouter un scénario consiste à écrire une fonction dans `tests/testlab/scenarios.py`,
qui crée ses données avec `lab.fixture_folder`, agit avec `lab.key` et `lab.type_text`,
puis vérifie avec `lab.wait_window`, `lab.clipboard` et les fichiers. Elle est ensuite
enregistrée dans `SCENARIOS`, et la CI peut l'appeler par son nom.

Les tests ajoutés deviennent permanents. Il ne faut pas demander à l'utilisateur de
recommencer les anciens essais à chaque bêta, ni annoncer « 19/19 automatiques » sans
preuve.

## Sécurité non négociable

- Ne jamais exécuter une PR non fiable sur la session personnelle du propriétaire.
- Les tests n'utilisent ni le `$HOME` réel, ni la vraie corbeille, ni les disques
  personnels, ni les secrets de signature ou COPR. Cette garantie repose sur le confinement
  (`uid` ou `bwrap`) et sur l'exécution en CI ou dans une VM jetable, pas sur la seule
  substitution des variables.
- Aucun service SSH permanent ni runner auto-hébergé non isolé.
- Les conditions d'autorisation des jobs de publication COPR, Arch et Pacman sont inchangées.
- Les captures et journaux ne contiennent que des chemins jetables (`/tmp/mirivue-testlab-*`).

Suivi du chantier : [issue n° 8](https://github.com/denamiel/Mirivue-kde/issues/8).
