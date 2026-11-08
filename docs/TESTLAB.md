# Mirivue TestLab — validation des évolutions futures

> État : **première tranche opérationnelle** (PR n° 9). Le banc démarre le RPM
> installé dans une vraie fenêtre X11 sous Xvfb et le pilote au clavier.
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

### Isolation

- **Dossier jetable :** un dossier `mirivue-testlab-*` est créé sous `MIRIVUE_TESTLAB_TMP`
  (par défaut `/tmp`). Il est refusé s'il se trouve dans un dossier personnel.
- **Environnement de l'application :** il est entièrement reconstruit et rien n'est hérité,
  sauf `PATH`.
  - `HOME`, tous les `XDG_*_HOME`, `XDG_RUNTIME_DIR` et `TMPDIR` pointent dans ce dossier.
  - La corbeille KIO est donc `XDG_DATA_HOME/Trash`, elle aussi jetable.
- **Affichage et bus :**
  - Xvfb choisit lui-même un numéro d'affichage libre (`-displayfd`), sans TCP, avec un
    cookie MIT-MAGIC-COOKIE propre à la session.
  - Un `dbus-daemon --session` privé écoute dans le dossier jetable.
- **Aucun secret** COPR ou Pacman n'est lu. Le job CI n'a que `contents: read`.
- **Contrôle des dossiers personnels :** des chemins sensibles des dossiers personnels sont
  photographiés avant et après le scénario : préférences Mirivue, `kiorc`, corbeille, Places,
  journaux. En CI, tout le `HOME` du job est surveillé (`--surveiller "$HOME"`).
  Toute modification donne le code 3.

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

### Rapports et codes de sortie

`<artefacts>/rapport.json` (étapes, durées, captures, nettoyage, isolation),
`junit.xml`, `captures/*.png`, `journaux/*.log` (Xvfb, D-Bus, Mirivue, harness).

| Code | Signification |
|---|---|
| 0 | Scénario réussi, nettoyage et isolation vérifiés |
| 1 | Scénario en échec (capture et journaux conservés) |
| 2 | Environnement indisponible (outil absent) : aucune conclusion |
| 3 | Nettoyage incomplet ou écriture hors du dossier jetable |

### Utilisation

```bash
# Dans un conteneur ou une VM Fedora 45 où le RPM testé est installé :
dnf -y install python3 xorg-x11-server-Xvfb xdotool xwd xclip dbus-daemon
python3 tests/testlab/run.py nouveau-dossier --artefacts /tmp/testlab-resultats
MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1 python3 -m unittest discover -s tests -p test_testlab_harness.py -v
```

Le harness peut tourner sur un poste de développement : il n'y touche ni au `HOME`,
ni à la session graphique. Pour les PR non fiables, il faut toutefois l'exécuter
uniquement en CI ou dans un conteneur jetable (par exemple `podman run --rm` avec le
dépôt monté en lecture seule), jamais dans la session personnelle.

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

## Intégration CI

Le job `testlab` de `fedora-package.yml` :
- dépend du job RPM Fedora 45 et installe **le RPM produit par ce même commit** ;
- exécute les tests du harness avec `MIRIVUE_TESTLAB_REQUIRE_DISPLAY=1`, où un outil absent
  est un échec et non un saut ;
- exécute le scénario `nouveau-dossier` et publie `testlab-fedora-45` (rapports, captures
  et journaux, conservés 14 jours), même en cas d'échec.

Un échec rend le job rouge. Le job de publication COPR et ses conditions (lancement manuel
sur `main`, confirmation `PUBLIER`, environnement protégé) sont **inchangés**. Une CI verte
n'est jamais une autorisation de publier.

Durées mesurées dans un conteneur Fedora 45 local :
- scénario `nouveau-dossier` : environ 10 s ;
- tests du harness : environ 45 s.

Le job complet ajoute surtout l'installation des paquets ; les durées CI réelles sont
indiquées dans la PR.

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

1. **Plasma/Wayland en VM éphémère :**
   - Fedora KDE 45 démarrée depuis une image, sans connexion SSH à un poste personnel,
     détruite après chaque exécution ;
   - même harness, avec un pilote d'entrée Wayland (`kwin_wayland --virtual` ou
     `ydotool`/libei) et des captures par `spectacle` ou un portail ;
   - un runner auto-hébergé n'est acceptable que s'il est isolé, éphémère et n'exécute
     pas les PR de forks.
2. **Étape intermédiaire évaluable en CI :** `kwin_wayland --virtual` dans le conteneur
   Fedora donne un vrai KWin Wayland sans matériel.
3. **Variantes séparées :** NTFS en image loop, SFTP vers un `sshd` local jetable et SMB,
   chacune avec ses propres scénarios. Elles ne sont jamais supposées couvertes par Xvfb.
4. **Arch/CachyOS :** même harness dans un conteneur `archlinux` avec le paquet construit
   par `arch-package.yml`.

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
- Aucun accès au `$HOME` réel, à la vraie corbeille, aux disques personnels ou aux
  secrets de signature/COPR dans les tests.
- Aucun service SSH permanent ni runner auto-hébergé non isolé.
- Les jobs de publication COPR, Arch et Pacman restent inchangés.
- Les captures et journaux ne contiennent que des chemins jetables (`/tmp/mirivue-testlab-*`).

Suivi du chantier : [issue n° 8](https://github.com/denamiel/Mirivue-kde/issues/8).
