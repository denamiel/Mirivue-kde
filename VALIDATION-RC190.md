# Validation RC190

27 octobre 2026. Cinq simplifications d’interface demandées, sans modification
des opérations de fichiers, du tri, des colonnes média ou des préférences de
démarrage. Les sources de référence sont Dolphin v26.08.2 et KF6 6.31.0.

## Modifications

- configuration.py : groupes Miniatures / Panneau d’aperçu / Lecture ; même
  stockage et mêmes valeurs. Remplacement du dialogue de raccourcis personnalisé.
- app.py : commandes du presse-papiers regroupées, durée dans Outils, et accès
  de secours au menu KDE dans les menus contextuels.
- menu_visibility.py : vrai KHamburgerMenu et regroupement inspiré du tag exact
  de Dolphin, avec accès complet aux autres commandes et gestion clavier conservée.
- native/desktop-dialogs.cpp, native_desktop_dialogs.py, native_shortcuts.py :
  adaptateurs des API publiques KDE, sans copie des implémentations des dialogues.
- keyboard.py : conservation des listes de touches secondaires et des touches
  désactivées ; lecture des anciennes valeurs scalaires inchangée.
- toolbar_xml.py : les boutons Menu dupliqués sont de vrais widgets de l’action
  KDE ; les autres commandes gardent le mécanisme existant.
- CMakeLists.txt : ajout de la source au pont existant ; aucune dépendance nouvelle.

La taille du dialogue des raccourcis est conservée globalement par KDE,
exception explicitement acceptée. Les raccourcis personnalisés restent propres
à Mirivue. Le fichier partagé kservicemenurc n’est pas modifié par ce travail.

## Exécuté ici

Les adaptateurs desktop-dialogs.cpp et toolbar-editor.cpp ont été réellement
compilés et liés à Qt/KF6. Environnement : Python 3.12, PySide6/Qt 6.12.0,
KF6 6.13.0 extraits de paquets Debian ; en-têtes Qt 6.11.2. Les sources KF6
6.31.0 ont été lues comme référence ; ne pas confondre ces sources avec la
version des bibliothèques exécutées. Versions et empreintes : environnement.json.

Trois passages du même ensemble de 56 tests ciblés, tous sans échec :

| Passage | Tests | Durée unittest | Échecs | Erreurs | Code |
|---|---|---|---|---|---|
| 1 | 56 | 6.606 s | 0 | 0 | 0 |
| 2 | 56 | 4.784 s | 0 | 0 | 0 |
| 3 | 56 | 6.029 s | 0 | 0 | 0 |

- Neuf scénarios natifs : maintien des touches secondaires, touches désactivées,
  Annuler, valeurs par défaut, dialogue non modal, échec d’écriture et retour
  aux anciennes valeurs, accès aux menus, doublons visibles, bouton Menu
  secondaire créé puis détruit. Chaque scénario natif travaille dans des
  répertoires XDG jetables. Aucun service n’est téléchargé ni exécuté.
- Quatre nouveaux contrôles : trois groupes Qt et valeurs intactes, listes
  réellement données au constructeur des menus, touche primaire seule explicite.
- Les quatre nouveaux contrôles échouent contre RC189 : journal
  avant-rc189-groupes.log. Ils passent contre RC190. Le repli clavier de RC189
  ne savait pas conserver une liste explicite des seules touches voulues.
- Neuf tests existants de finition d’interface, trois du vrai KEditToolBar,
  neuf de structure des menus et un invariant du titre de rubrique.
- Vingt-et-un contrôles existants supplémentaires : accès au renommage,
  cohérence des commandes, menu Créer, contrat de distribution, identifiants
  techniques et composition du paquet Arch. Ce dernier contrôle lit le paquetage ;
  il ne constitue pas une exécution de makepkg ni une installation pacman.
- Les échecs intermédiaires sont conservés : le menu natif est créé/remplacé
  tardivement par KDE. Le pont ne conserve plus une référence au menu périmé.
  La fixture de barre d’outils a aussi été corrigée pour exposer réellement le
  bouton testé ; le clic du bouton instantané est vérifié dès la pression,
  avant le relâchement qui peut fermer le popup hors écran.

## Non exécuté ici

La suite complète, la compilation du moteur complet KItemListView et des
assistants KIO, makepkg, pacman, Breeze/Union réels, Wayland et les opérations
KIO réelles ne sont pas validés ici. La bibliothèque de test ne contient que
les adaptateurs du menu, des raccourcis et de la barre d’outils, pas le moteur
de fichiers. Les fixtures fournissent une fenêtre/actions contrôlées et les
valeurs par défaut du clavier ; les dialogues et menus KDE sont réels.

Commande complète requise sur CachyOS : ./Valider-RC190.sh. Elle conserve la
compilation complète, la suite intégrale et son délai de 600 s. Aucun contrôle
existant n’a été retiré. La vérification d’installation reste dans la commande.

## Périmètre préservé

Pas de changement de mode session/dossier, de choix d’ouverture externe, de
partage kservicemenurc, de gras du renommage, d’étiquettes, de moteur de fichiers,
de gestion KIO ni de colonnes média. Les réglages existants sont conservés.
Les anciennes preuves restent datées de leur version et ne sont pas présentées
comme des essais actuels. Diff complet dans validation/RC190/diffs.
