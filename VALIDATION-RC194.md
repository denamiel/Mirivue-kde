# Validation RC194 — Fedora : menus, bus de test et traces

28 octobre 2026. Correction du banc de validation, sans modification de
l’application hors numéro de version. Les sources natives sont identiques
à RC193, octet pour octet. Aucun test en échec n’est désactivé ni ignoré.

## Ce que prouve le journal Fedora reçu

La RC193 a compilé ses composants natifs puis exécuté 589 tests en 106,865 s.
Trois erreurs concernent les scénarios de menu curated, clone et borrowed-actions.
Une fenêtre de test refuse son enregistrement D-Bus. La commande s’est arrêtée
avant Installer.sh. Le résumé ne contient ni les exceptions des trois scénarios
ni le nom de l’erreur D-Bus : il ne permet pas d’attribuer cette dernière à SELinux,
à un paquet manquant ou au code de routage. Aucune de ces causes n’est affirmée.

## Menus : échec reproduit et correctif

Le helper de test ouvrait un menu puis attendait le retour de l’appel pour
l’examiner et le fermer. QToolButton::showMenu peut attendre la fermeture dans
une boucle Qt imbriquée. Sur Qt 6.11.2 avec le code KHamburgerMenu de KDE 6.30.0,
les trois tests attendent chacun 20 s et lèvent TimeoutExpired :
avant-menu-qt611-kde630-correct.log, 3 erreurs, 60,074 s.
Les mêmes tests ne bloquaient pas avec Qt 6.12 dans ce banc : la version de Qt
explique pourquoi les essais ciblés précédents n’avaient pas révélé cette attente.

Correction : tests/helpers/desktop_dialog_peer.py, inspect_popup programme
l’examen et la fermeture depuis la boucle d’événements avant l’ouverture.
Les vérifications de visibilité, contenu, actions empruntées et bouton secondaire
sont conservées. La limite extérieure de 20 s reste ; l’absence réelle de menu
fait échouer le scénario après 3 s. Les erreurs des callbacks sont remontées.
Les dix tests de bureau réussissent : apres-menu-qt611-kde630.log, 2,528 s.
Aucun QMenu, KHamburgerMenu ni raccourci de l’application n’est modifié.
Le parent de tests affiche aussi les sorties capturées si un sous-processus expire.

Référence d’explication Qt : https://doc.qt.io/qt-6/qtoolbutton.html#showMenu
Le KHamburgerMenu consulté pour l’environnement Fedora est précisément
https://raw.githubusercontent.com/KDE/kconfigwidgets/v6.30.0/src/khamburgermenu.cpp
Il ne remplace pas Dolphin v26.08.2 comme référence de comportement applicatif.

## D-Bus : correction du banc et limite de preuve

Le test utilisait systématiquement TCP/ANONYMOUS, y compris sur Linux où une
session KDE emploie normalement Unix. Le nouveau helper private_bus.py choisit
Unix/EXTERNAL après vérification de disponibilité. Seules les interdictions
explicites d’Unix autorisent le repli local TCP ; une autre erreur reste une erreur.
Les variables DBUS_STARTER_ADDRESS, DBUS_STARTER_BUS_TYPE et DBUS_SESSION_BUS_PID
ne sont plus héritées dans les pairs privés. Les variables du bureau de l’utilisateur
ne sont pas modifiées. En cas de refus, instance_peer.py affiche isConnected et
le nom/message de QDBusConnection.lastError au lieu d’un refus générique.

Quatre tests vérifient le choix du transport, l’absence d’accès anonyme sur Unix,
le repli limité et le retrait des adresses héritées. Le test existant de deux vraies
fenêtres, discovery/Dispatch et regroupement réussit localement en 1,747 s, puis
dans les trois passages ciblés ci-dessous. Il utilise le repli TCP : cet environnement
interdit la création de sockets Unix. Le choix Unix est testé par simulation du
contrôle de disponibilité ; son exécution réelle sous Fedora n’a pas été faite.

Le refus spécifique Fedora n’est PAS reproduit ici. Il n’est donc PAS déclaré
résolu avec certitude. Le changement rend le banc conforme au transport de sa
plateforme ; le nouveau journal permettra d’identifier un éventuel refus persistant.
Le routage D-Bus de Mirivue et la validation des requêtes restent inchangés.

## Journaux conservés

Valider-RC194.sh conserve build.log, tests.log et exit-status.txt dans un nouveau
sous-dossier de ${XDG_STATE_HOME:-$HOME/.local/state}/mirivue-kde/validation.
Son chemin est imprimé à la fin, après réussite ou échec, même si le répertoire
d’extraction est ensuite effacé. MIRIVUE_VALIDATION_LOG_DIR permet une destination
spécifique au banc de test. Le journal de tests intégral est affiché en cas d’échec.
Les temporaires natifs sont toujours nettoyés. Un échec bloque toujours l’installation.
Deux nouveaux tests exécutent le vrai script shell avec commandes de compilation
et de test substituées : erreur de compilation et TimeoutExpired simulé. Ils échouent
sur le script RC193 (journaux absents), puis réussissent sur RC194. Ce sont des tests
du traitement des erreurs du script, pas une compilation ni une suite intégrale.

## Trois exécutions ciblées

| Passage | Tests | Durée | Échecs | Erreurs | Ignorés | Sortie |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 84 | 14.568 s | 0 | 0 | 0 | 0 |
| 2 | 84 | 15.142 s | 0 | 0 | 0 | 0 |
| 3 | 84 | 14.916 s | 0 | 0 | 0 | 0 |

Journaux bruts : validation/RC194/passage-1.log à passage-3.log et resultats.json.
84 tests par passage : menus natifs, transport, diagnostics, deux fenêtres D-Bus
réelles, budget/réponses de routage, ouverture multiple KIO, menus, installateur,
versions, paquet, documentation de gel et index du modèle. Le runner exact est
validation/RC194/final194-tests.py. Un essai intermédiaire a échoué sur une assertion
qui citait encore RC193 après changement de numéro : le journal est conservé et
l’assertion suit maintenant RC194. Il n’est pas compté comme passage réussi.

## Environnement et limites

- Hôte Ubuntu, Python 3.12, PySide6/Qt 6.11.2 ; pas de session Fedora ni Plasma.
- Menus : adaptateur réel desktop-dialogs.cpp, KHamburgerMenu 6.30.0 compilé
  séparément pour reproduire le cas, reste de KF6 6.13 extrait en répertoire privé.
- Fenêtres : moteur KItemListView compilé, pont de test local basé sur KF6 6.13.
  Une copie temporaire du pont omet l’appel setHighlightFocusIndicator, absent de
  cette ancienne bibliothèque ; cette copie n’est PAS livrée. Aucun test de cadre,
  focus ou fidélité visuelle n’est revendiqué avec ce pont. Les sources livrées
  sont intactes et avaient compilé sur Fedora dans le journal utilisateur.
- Le CMake complet de la livraison et la suite intégrale n’ont PAS été validés
  localement : outils/bibliothèques natives disponibles plus anciens que Fedora.
  Les tentatives et limites sont conservées ; pas de résultat de compilation complet
  inventé à partir du harnais partiel. Les assistants KIO d’opérations ne sont pas
  couverts par cette compilation locale.
- Aucune installation Fedora, SELinux, activation Wayland, corbeille réelle,
  détachement/glissement d’onglet ni session prolongée n’est déclarée validée.

## Vérifications de livraison

Compilation syntaxique Python, syntaxe des scripts shell, cohérence des entrées
de version, licences présentes et contrôle de l’archive effectués. Les résultats
complets de validation restent requis avant installation et avant publication stable.

Commande Fedora après téléchargement de l’archive RC194 dans Téléchargements :

```bash
bash -c 'set -e; dossier=$(mktemp -d); trap '\''rm -rf -- "$dossier"'\'' EXIT; tar -xzf "$HOME/Téléchargements/Mirivue-1.0.0-RC194-KDE.tar.gz" -C "$dossier"; cd "$dossier/Mirivue-1.0.0-RC194-KDE"; ./Valider-RC194.sh; ./Installer.sh'
```

## Changements volontairement écartés

Aucun ajout de paquet, réglage SELinux, changement d’apparence ou de moteur,
contournement de test, modification de délai 600 s, ni modification du routage
applicatif. Les associations, outils médias, services partagés et réglages sont conservés.
Le principal risque restant est le refus D-Bus spécifique à Fedora : le test réel
de deux fenêtres sur le bus privé doit réussir et son journal complet est indispensable
s’il échoue encore. Une suite ciblée réussie ne remplace pas ce résultat.
