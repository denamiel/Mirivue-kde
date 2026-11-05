# Mirivue KDE 1.0.0-beta.5 — composants KDE et renommage en masse conservé

Version visible `1.0.0-beta.5`, Python `1.0.0b5`, première révision RPM
`0.200.beta5.1`.

## Propriétés et permissions

La fenêtre utilise l’API publique `KPropertiesDialog`, pour une sélection locale
ou des URL KIO. Les pages natives KDE gèrent les informations, permissions,
propriétaires et fonctions fournies par les plugins installés. Le dialogue et
le module Python de modification des permissions sont supprimés. Les commandes
en cours sont vérifiées avant ouverture.

Le changement de nom dans cette fenêtre est en lecture seule lorsqu’un média
possède un compagnon XMP : utiliser F2 ou le renommage avancé afin de garder les
deux fichiers ensemble. Les renommages autorisés par la fenêtre native sont
répercutés dans les panneaux et résultats de Mirivue.

## Renommage

- Un seul élément sans compagnon XMP : validation préalable puis `KIO::moveAs`,
  avec l’historique Annuler/Rétablir du service KIO.
- Média avec XMP : transaction spécialisée conservée, sans écrasement, avec
  restauration des noms en cas d’échec.
- Plusieurs éléments, règles, numérotation, remplacement, métadonnées,
  correction d’extensions : **outil de renommage en masse conservé**.
  Les modules `rename_ui.py`, `renaming.py` et `extensions.py` sont inchangés.
  La prévisualisation, les chaînes/permutations de noms, les compagnons XMP et
  l’historique spécialisé restent disponibles.

## Inventaire et actualisation

Les racines de dossiers locaux et les emplacements virtuels/distants utilisent
le même assistant `KCoreDirLister`. La détermination approfondie des MIME locaux
est différée pour éviter de sonder tous les médias avant affichage. La lecture
est bornée et annulable lors d’une navigation ou fermeture.

La surveillance conserve les notifications natives Qt, mais les inventaires de
comparaison et les stat nécessaires à la précision nanoseconde sont maintenant
lus dans un worker enregistré, hors du fil graphique. La réconciliation conserve
les lignes, sélections et miniatures. Elle traite aussi les changements `.hidden`.
La recherche récursive spécialisée et les modèles enrichis multimédias restent
en Python ; cette version ne prétend pas supprimer tous les accès Python aux
fichiers ni remplacer tout le modèle d’affichage.

## Miniatures

Les plugins KDE restent prioritaires. Le secours vidéo FFmpeg existait déjà
dans l’assistant natif : la seconde génération de frames en Python est retirée.
Le panneau d’aperçu utilise ce même assistant pour la vidéo. Les rendus locaux
images/PDF/documents et les pochettes audio sont conservés : ils apportent un
contenu que les seuls plugins installés ne garantissent pas de fournir.
Si l’assistant vidéo natif est absent ou défaillant, aucune seconde génération
Python n’est tentée ; la prévisualisation peut être indisponible.

## Validation avant publication

La nouvelle suite graphique teste les permissions natives réellement appliquées,
les propriétés multiples, le verrouillage du nom avec XMP, F2 natif et son undo,
F2 avec compagnon, **le vrai dialogue de numérotation de plusieurs images avec
leurs XMP puis son annulation**, l’inventaire masqué/nanoseconde et le secours
vidéo natif avec les plugins désactivés dans une configuration de test isolée.
Les suites de transactions de renommage et l’historique local sont obligatoires.
Les résultats sont ceux des workflows GitHub Actions du commit publié.

Les essais Qt offscreen et D-Bus isolé ne constituent pas une validation de tous
les serveurs réseau, des ACL de tous les systèmes de fichiers ni d’une session
Plasma/Wayland réelle. Les réglages et documents personnels ne sont pas utilisés
par les tests, qui opèrent dans des dossiers temporaires.
