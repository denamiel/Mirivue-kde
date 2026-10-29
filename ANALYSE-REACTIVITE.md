# Moteur de fichiers de Dolphin — RC163

## Changement effectué

Les anciens QTableView et QListView des panneaux sont remplacés par un moteur
issu de Dolphin 26.08.2 : KItemListContainer, KItemListController,
KStandardItemListView (qui dérive de KItemListView) et KStandardItemListWidget.
Un seul moteur par panneau passe entre les modes détails, icônes et compact.

Les objets visibles conservent leurs QStaticText et leurs pixmaps comme dans
le moteur KDE. Les icônes sont préparées à la demande pour les éléments dessinés.
L’adaptateur conserve les rôles des colonnes et traite les notifications du
modèle de Mirivue sans réinventorier le dossier à chaque redessin.

Le modèle de fichiers Python, le tri et les filtres restent disponibles, ainsi
que les outils de médias, le renommage en masse et les opérations KIO.
Un QHeaderView caché conserve le format des anciennes préférences de colonnes ;
l’en-tête visible appartient au moteur KDE. Largeurs personnalisées, largeur
automatique et remplissage de la vue sont reliés à cet en-tête natif.

Les filtres globaux de fenêtre et de menus sont précédés d’un masque C++ :
les événements de dessin et de disposition des objets graphiques ne traversent
plus ces filtres Python. Les raccourcis, menus, événements de souris, zoom et
commandes des médias conservent leurs contrôleurs.

## Vérifications exécutées

- Compilation réelle par CMake/Ninja des deux bibliothèques de vues.
- 339 tests réussis, aucun échec ni test ignoré, avec ces bibliothèques chargées.
- Neuf contrôles du moteur et un contrôle des largeurs, notamment : modes et
  moteur partagé ; sélection native et Qt ; insertion/suppression/tri ;
  éditeur KDE F2 et Tab ; menu contextuel ; action réelle d’un dépôt simulé ;
  mises à jour des durées, colonnes, icônes, couleurs et URL ; filtre natif
  d’événements ; conservation des largeurs de base pendant le remplissage.
- Un test de redimensionnement répété active 38 colonnes et exige zéro appel
  à data() du modèle Python après préparation des éléments.
- Les contrôles d’installation exigent le moteur natif et vérifient une mise
  à jour réelle d’un élément affiché. Aucun nouveau diagnostic manuel requis.

## Mesure automatisée du séparateur

Banc : 120 éléments par panneau, fenêtre 1500 × 800, 180 déplacements mesurés,
puis 80 déplacements profilés. Python 3.12.14, Qt 6.12.0, style Fusion,
rendu hors écran, configuration et fichiers jetables. Les essais ont été
exécutés successivement, sans forcer un second redessin à chaque déplacement.

| Version et moteur | Colonnes activées | Médiane | P95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| 1.0.0-rc162 — QTableView | 6 | 8.66 ms | 10.32 ms | 13.23 ms |
| 1.0.0-rc162 — QTableView | 38 | 8.91 ms | 10.03 ms | 13.18 ms |
| 1.0.0-rc163 — KStandardItemListView | 6 | 8.96 ms | 11.65 ms | 13.74 ms |
| 1.0.0-rc163 — KStandardItemListView | 38 | 9.72 ms | 12.23 ms | 15.51 ms |

La mesure ne démontre pas de gain de temps net par rapport à la RC162, qui
possédait déjà son cache de données C++. Elle confirme en revanche le passage
au moteur KStandardItemListView et l’absence d’appels au modèle Python pendant
le glissement profilé : plus aucun appel à data, flags, rowCount ou columnCount.
Les filtres globaux Python des menus ne reçoivent plus les événements graphiques.

Ce banc ne mesure ni KWin/Breeze sur la machine CachyOS, ni la présentation des
images par le GPU. Il ne justifie pas une promesse de réaction instantanée dans
toutes les sessions. Aucun essai manuel sous Plasma n’est présenté comme réalisé.
Les temps portent sur des déplacements après préparation ; ils ne mesurent pas
le premier inventaire d’un dossier, le tri initial ou une opération KIO.

Les résultats bruts figurent dans `tests/support/resultats-redimensionnement-RC163.json`.
Le programme reproductible est `tests/support/benchmark_splitter.py`.

## Sources et maintenance

- Sources KDE épinglées : https://github.com/KDE/dolphin/tree/v26.08.2/src/kitemviews
- Politique des tailles : https://github.com/KDE/dolphin/blob/v26.08.2/src/views/dolphinitemlistview.cpp
- Provenance et trois fichiers adaptés : `native/dolphin-engine/UPSTREAM.json` et `README.md`.
- Aucun chargement de libdolphinprivate ; les sources intégrées sont recompilées
  pour le Qt/KF6 de la machine. Leur suivi devra être effectué lors des versions
  futures de Mirivue. Voir `LICENCES-TIERS.md` pour les mentions de distribution.
