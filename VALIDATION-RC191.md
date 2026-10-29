# Validation RC191

27 octobre 2026. Deux défauts corrigés, sans ajout de fonction.

## Journal fourni par l’utilisateur

La compilation complète de RC190 réussit sur CachyOS, dont desktop-dialogs.cpp,
le moteur de vues et les assistants KIO. La suite exécute 568 tests en 50,153 s,
avec neuf échecs d’import et trois erreurs dans les sous-cas d’un test de
navigation au clavier. Le script set -e s’arrête dans Valider-RC190.sh : ni la
construction du paquet ni pacman ne sont lancés par ce parcours. Ce journal
est une exécution de l’utilisateur, pas une exécution sur cet hôte.

## 1. Sous-processus des tests sans chemin du projet

Défaut de tests/test_native_desktop_dialogs.py : lancer directement un script
dans tests/helpers place ce dossier dans sys.path. Sans PYTHONPATH de
développement, le sous-processus ne trouve pas mirivue. Les essais RC190 sur
cet hôte avaient hérité d’un PYTHONPATH contenant le projet, ce qui masquait
le défaut. La correction fournit explicitement le chemin absolu déduit de
__file__, en conservant les entrées externes éventuelles.

Reproduction : les neuf scénarios échouent sur RC190 avec ModuleNotFoundError
lorsque seul le dossier des dépendances externes est hérité. Les neuf
réussissent après correction, sans installation de Mirivue. Voir
avant-imports.log et apres-imports.log. Le parcours élargi utilise également
cette absence de PYTHONPATH de développement.

## 2. Actions partagées invalidées pendant la reconstruction du menu

Défaut de mirivue/menu_visibility.py : les trois menus temporaires étaient
vidés avec QMenu.clear(). Avec des actions empruntées créées par
QMenu.addAction(texte, callback), cet appel invalide des wrappers PySide6,
contrairement aux fixtures initiales créées par QAction(parent). Une action
C++ peut encore appartenir à son menu d’origine alors que son wrapper Python
n’est plus utilisable. Propriétés et Coller sont notamment touchées.

Tab sur le bouton Menu prépare le menu KDE ; cette reconstruction suffit à
déclencher le défaut, sans qu’une commande soit choisie. La reproduction du
test existant donne les mêmes trois erreurs que le journal utilisateur,
avec une trace complète situant l’échec sur properties_action.setEnabled.
Voir avant-panneaux-trace.log.

Correction minimale : removeAction pour retirer les références, sans effacer
les actions empruntées. Seuls les séparateurs créés et possédés par le menu
sont détruits, par deleteLater. Aucun raccourci, callback ou objet de commande
partagé n’est remplacé. Le chemin de secours utilise la même règle.

Nouveau test test_menu_rebuild_keeps_actions_created_by_other_menus_alive :
actions créées dans leurs menus d’origine, quatre cycles Tab/ouverture du menu,
contrôle de validité, puis déclenchement unique de Propriétés et Configuration.
Il échoue avant le correctif et réussit après : avant-actions-partagees.log
et apres-actions-partagees.log. Le test existant Tab/Maj+Tab et copie entre les
panneaux réussit ensuite dans les trois vues, sans supprimer ni assouplir
une assertion : apres-panneaux-trace.log.

## Exécutions effectuées ici

Le moteur KItemListView/KStandardItemListWidget, le modèle de présentation Qt et
les adaptateurs des menus/raccourcis ont été réellement compilés et chargés.
Le moteur et la présentation utilisent les sources livrées sans modification,
avec un projet CMake de diagnostic local parce que les paquets de développement
installés ici ne permettent pas de configurer tout le projet de distribution.
Ce projet et son journal sont conservés dans les preuves.

Environnement : Python 3.12.14, PySide6/Qt 6.12.0, en-têtes Qt 6.11.2, KF6
6.13.0 extraits de paquets Debian. Sources de comparaison : Dolphin v26.08.2
et KF6 6.31.0. Ne pas confondre référence de code et bibliothèques exécutées.
Les sources natives de RC191 sont identiques à RC190 ; seule l’intégration
Python du menu change dans l’application.

Trois passages du même ensemble de 81 tests, avec répertoires XDG jetables :

| Passage | Tests | Durée unittest | Échecs | Erreurs | Code |
|---|---|---|---|---|---|
| 1 | 81 | 15.474 s | 0 | 0 | 0 |
| 2 | 81 | 15.264 s | 0 | 0 | 0 |
| 3 | 81 | 15.444 s | 0 | 0 | 0 |

Cet ensemble comprend les dix scénarios natifs des menus/raccourcis, les
contrôles des groupes de configuration, du presse-papiers, de la durée, du
KEditToolBar, du renommage, du paquet et des identifiants ; ainsi que tous les
tests de test_pane_regressions_gui et test_keyboard_gui. Ces derniers utilisent
le vrai moteur natif dans la fenêtre Mirivue, dont le parcours des raccourcis
dans les vues et les panneaux. Aucun traceback ni erreur de wrapper détruit
n’apparaît dans ces trois journaux. Les données sont des fichiers jetables.

## Non exécuté ici

Ce ne sont pas trois passages de la suite intégrale. Les assistants KIO et
le pont Emplacements complet n’ont pas été reconstruits ici ; le menu natif
utilise un pont de test avec les adaptateurs inchangés. Une session Plasma,
Wayland, Union/Breeze réels, makepkg, pacman et la corbeille réelle ne sont pas
déclarés validés. La compilation complète réussie sur le PC de l’utilisateur
concerne RC190, pas une nouvelle exécution de RC191.

Sur CachyOS, ./Valider-RC191.sh reste obligatoire et conserve tous les tests,
la compilation complète et le délai de 600 s. La commande d’installation
s’arrête avant pacman si un test échoue. Aucun échec n’est contourné.

## Périmètre

Aucun changement de fonction, de réglage personnel, d’opération KIO, de tri,
de vue, de licence ou de dépendance. Le partage volontaire de kservicemenurc
et la taille commune du dialogue KDE restent inchangés. Les preuves et les
diffs intégraux figurent dans validation/RC191.
