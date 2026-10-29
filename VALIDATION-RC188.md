# Validation RC188 — ergonomie et dialogue KDE de barre d'outils

27 octobre 2026. Les cinq changements demandés sont réalisés. L'intégration
XMLGUI a nécessité l'adaptation du moteur de barre d'outils, expressément acceptée.
Aucune fonction de fichiers, de médias, de session ni de transfert n'est retirée.

## Fichiers et portée

1. configuration.py : groupes Affichage, Navigation et Onglets ; titre de page
   Configurations de colonnes. Clés et valeurs des réglages inchangées.
2. menu_visibility.py / desktop.py : indications du menu calculées depuis les
   raccourcis actifs, y compris après modification ou suppression. L'accès au
   réglage de la barre réutilise l'action existante et son libellé.
3. action_feedback.py / app.py : motifs d'indisponibilité dans toolTip, statusTip
   et whatsThis natifs des QAction ; restauration de l'aide à la réactivation.
   Infobulles activées sur les menus concernés ; aucune fenêtre d'information
   supplémentaire. Les métadonnées d'aide sont testées, pas un lecteur d'écran réel.
4. toolbar_xml.py / desktop.py : reprise des dispositions historiques sans écrire
   à l'ouverture ; lecture/enregistrement de l'ordre, des côtés, séparateurs,
   espaces et propriétés d'icône/texte XMLGUI. Boutons miroirs pour une commande
   présente dans les deux groupes. Les chemins et l'accès au menu restent disponibles.
5. native/toolbar-editor.cpp : vrai KEditToolBar via KXMLGUIClient/Builder/Factory.
   Les documents temporaires sont privés ; seul le réglage propre à Mirivue reçoit
   le résultat. Les callbacks Python interceptent les erreurs et tentent de
   rétablir l'état précédent si l'application de la disposition échoue.
6. native/CMakeLists.txt : nouveau fichier compilé dans le pont existant ; Qt6::Xml
   déclaré explicitement. Aucun nouveau paquet requis : XmlGui et qt6-base sont
   déjà des dépendances. Le nouveau fichier original MIT figure dans LICENCES-TIERS.

## Reproduction des défauts avant correction

Quatre contrôles exécutés contre RC187 échouent sans erreur du lanceur : ancien
regroupement, ancien titre de page, indications de raccourcis figées, rappel d'un
objet de catégorie détruit. Voir validation/RC188/rc187-avant.log.
Les fonctions XMLGUI sont nouvelles dans l'adaptateur : aucune prétendue mesure
avant/après de ce dialogue sur RC187 n'est annoncée.

## Incident découvert et corrigé pendant la validation

L'enchaînement initial des tests a déclenché un plantage. Il a été reproduit avec
une simple QDialog, sans le dialogue KDE : des destructions différées de la fixture
restaient jusqu'à la boucle modale suivante. Le nettoyage du nouveau test traite
explicitement DeferredDelete pendant que son propriétaire reste vivant.

Un rappel tardif KPageStyleCategories.adjustNavigationWidth a aussi été observé
sur un objet C++ détruit. La ligne QTimer.singleShot emploie désormais le contexte
QObject destinataire, ce qui annule le rappel après destruction. Un test dédié
vérifie l'absence d'exception ; il échoue sur RC187 et réussit après correction.
Le corps original du test des groupes de configuration a également été rejoué
sur le propriétaire isolé et le formulaire réel (contrat-groupes-original.log).
Ses attentes sont actualisées pour les six groupes ; aucune assertion n'est retirée.

## Exécuté ici — trois passages ciblés

Trente contrôles déjà présents en RC187, neuf nouveaux de regroupement, aide,
migration, rendu, persistance et durée de vie, et trois du vrai dialogue KDE.

| Passage ciblé | Tests | Durée unittest | Échecs/erreurs | Code de sortie |
|---|---|---|---|---|
| 1 | 42 | 0.312 s | 0 | 0 |
| 2 | 42 | 0.330 s | 0 | 0 |
| 3 | 42 | 0.304 s | 0 | 0 |

- Analyse AST : 204 fichiers Python hors preuves historiques.
- Syntaxe bash -n : 8 scripts et PKGBUILD.
- Test GUI historique de personnalisation : remplacé par un contrôle de délégation
  et trois contrôles réels de KEditToolBar. L'ancien QListWidget privé n'existe plus.
- Diff intégral : validation/RC188/diffs/00-integral.patch.
- Modifications natives limitées à CMakeLists.txt et toolbar-editor.cpp.

## Compilation et versions — distinction nécessaire

Le fichier toolbar-editor.cpp final a été réellement compilé et lié en bibliothèque
isolée. Les tests ouvrent un vrai KEditToolBar : réordonnancement, Annuler sans
écriture, Appliquer puis Annuler, réouverture, et Réglages par défaut avec sa vraie
confirmation. Ce ne sont pas des simulacres de dialogue.

La sonde utilise les en-têtes KDE Frameworks 6.31.0, les en-têtes Qt 6.11.2,
Qt/PySide6 6.12.0 à l'exécution et les bibliothèques KDE XMLGUI/ConfigWidgets
6.13.0 de Debian trixie. Le détail exact des paquets et le SHA-256 du fichier
compilé figurent dans compilation-native.json. Les en-têtes d'export générés
sont réduits aux seules macros de visibilité. Les API employées viennent des
en-têtes officiels, sans substitution des classes KDE.

Cette sonde ne constitue PAS la compilation du pont Mirivue complet et ne valide
PAS une session Plasma ni le rendu exact de KF6 6.31.0. La sonde de dates KFormat
6.31.0 des versions précédentes reste utilisée pour les contrôles correspondants.
Aucun binaire de sonde ni bibliothèque système n'est distribué dans l'archive.

## Non exécuté ici

Suite complète de Mirivue, construction complète CMake/makepkg, installation
pacman, session Plasma/Wayland, styles Breeze/Union réels, Corbeille KIO réelle,
glisser d'onglet et détachement. Les résultats ciblés et historiques ne sont pas
présentés comme cette validation complète.

Sur CachyOS : ./Valider-RC188.sh recompile le pont complet avec les bibliothèques
de la machine, puis exécute toute la suite, y compris les contrôles natifs ajoutés.
La commande d'installation conserve cette validation avant construction et pacman.

## Conservé et risque résiduel

Les clés de préférences, profils médias, gras de l'aperçu de renommage, F2,
transferts, session, onglets et le partage voulu de kservicemenurc sont conservés.
Les barres de chemin ne sont pas transformées en actions supprimables.

Le point présentant le plus de risque de régression est le nouveau rendu des
dispositions personnalisées : il intervient dans le placement de plusieurs widgets.
Les tests de migration, de boutons miroirs et de réouverture détectent ses erreurs
fonctionnelles ; ils ne remplacent pas l'observation du redimensionnement sous Plasma.
