# Moteur de vues de Dolphin dans Mirivue

Sources KDE officielles, version 26.08.2, tag `v26.08.2` :
https://github.com/KDE/dolphin/tree/v26.08.2/src/kitemviews

`UPSTREAM.json` conserve les SHA-256 des fichiers d’origine. Les mentions
d’auteurs et les licences originales restent dans les fichiers.

## Intégration

- KItemListContainer, KItemListController et KStandardItemListView assurent
  défilement, sélection, clavier, souris, disposition et en-tête natifs.
- FileWidget dérive de KStandardItemListWidget : le code de Dolphin conserve
  QStaticText et les pixmaps dans les objets des éléments visibles.
- L’adaptateur `../dolphin-view.cpp` traduit les signaux du modèle Qt de Mirivue
  en insertions, suppressions, déplacements et changements de rôles du moteur.
  Les icônes ne sont demandées au modèle que pour les éléments dessinés.
- Les opérations et les outils restent ceux de Mirivue ; aucun moteur de
  copie/suppression supplémentaire n’est importé.
- Les symboles privés sont masqués. Le composant est recompilé depuis ces
  sources ; il ne charge pas `libdolphinprivate` ni une classe privée provenant
  du paquet Dolphin installé. Une mise à jour des sources KDE sera explicite.
- Un filtre C++ limite les appels aux contrôleurs Python aux types d’événements
  utiles ; il ne détourne pas les événements de dessin du moteur KDE.

## Adaptations des sources KDE

Trois fichiers d’origine sont adaptés :

1. kstandarditemlistwidget.cpp : remplace les inclusions spécifiques au modèle
   de fichiers Dolphin par les inclusions génériques nécessaires ; appelle
   deux petits points d’extension pour les couleurs sémantiques et les polices
   de colonnes de Mirivue. Le dessin et QStaticText restent ceux de KDE.
2. kstandarditemlistwidget.h : déclare ces points d’extension, dont les valeurs
   par défaut conservent le comportement KDE.
3. accessibility/kitemlistdelegateaccessible.cpp : utilise les données et les
   textes déjà formatés du modèle de Mirivue, sans conversion en KFileItemModel.
   Les noms accessibles, descriptions et actions de sélection sont conservés.

Le petit `views/draganddrophelper` reprend uniquement la comparaison de listes
URL nécessaire au contrôleur, sous sa licence GPL. Les en-têtes d’export et
la catégorie de journalisation sont locaux. Les textes de licence sont joints.
