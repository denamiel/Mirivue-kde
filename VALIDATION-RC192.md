# Validation RC192

27 octobre 2026. Correction de trois coûts de traitement et des instructions de
stabilisation. Aucune nouvelle fonction ni refonte de l’interface.

## Résumé du correctif

- panes.py / FileSortProxy.set_name_filter : un contexte de panneau ne relance
  pas le filtre quand son texte n’a pas changé. beginFilterChange/endFilterChange
  encadrent la modification sur Qt compatible ; repli conservé pour Qt 6.8/6.9.
- start_thumbnails : le signal ready applique le résultat dans le contexte
  discret du panneau d’origine. Il ne déclenche plus sync_pane_controls, donc
  ni lecture de l’espace disque ni rafraîchissement des dates de l’autre panneau.
- VideoModel / model_inventory.py : index chemin → positions et compteur de
  médias incomplets propres à chaque modèle. Les signaux Qt entretiennent les
  insertions et les modifications. Après retrait/réinitialisation, une
  reconstruction est faite au premier besoin, pas à chaque ligne supprimée.
  Les références précédentes sont libérées dès l’invalidation. Les chemins en
  double sont conservés, avec le même ordre de traitement qu’auparavant.
- thumbnail_ready / apply_quick_metadata : accès aux lignes concernées par
  l’index ; les empreintes continuent de rejeter un résultat devenu périmé.
- update_delete_button : lecture du compteur au lieu d’un parcours du dossier.
- Le renommage en ligne actualise immédiatement l’index, avant sa notification
  différée ; les réinitialisations et le renommage multiple restent gérés.

L’index et les indicateurs utilisent une mémoire proportionnelle au nombre de
lignes. Les mutations du modèle suivent les notifications Qt : les chemins
actualisés, remplacements et décalages après suppression sont testés. Aucun
code de dessin C++ n’est changé. Les autres appels historiques à invalidateFilter,
qui portent sur d’autres critères, ne font pas l’objet d’une migration générale.

## Documentation

STABILISATION.md décrit le gel effectif et uniquement les commandes RC192 qui
existent. Il n’annonce plus un gel ancien alors que des fonctions ont été
ajoutées ensuite. Le changelog est classé par numéro décroissant, ses titres
unifiés et le contenu RC173 séparé de RC174. Les textes historiques sont
conservés ; ils ne sont pas présentés comme des résultats actuels.
LISEZ-MOI-KDE.txt indique quels documents lire. Les documents ne sont pas tous
déplacés dans docs/ : cette réorganisation générale reste hors périmètre.
A-verifier conserve les scénarios existants, avec des titres par sujet plutôt
que des sections répétées sous un même numéro.

## Preuves avant et après

Les tests ajoutés sont dans test_reactivity_inventory.py (11 tests) et
 test_freeze_documents.py (2 tests).

Sur RC191 :
- Les contrôles des nouvelles API d’index/filtre signalent leur absence.
- Sur 100 lignes, un résultat de durée visite 100 lignes ; une miniature en
  visite 200 ; dix changements de sélection évaluent 1 000 médias.
- Deux scénarios dans la vraie fenêtre scindée avec 128 lignes par panneau
  échouent : un résultat à droite fait repasser 128 fois le filtre de gauche
  pour la durée, 256 fois pour la miniature. Les résultats à droite font
  repasser le filtre 129 fois. Journaux avant-inventaire.log et
  avant-refiltrage-fenetre.log.
- Les deux contrôles documentaires échouent : commandes RC191 absentes des
  consignes courantes et rubrique RC173 vide. Voir avant-documents.log.

Sur RC192 :
- Les trois parcours linéaires précédents disparaissent après construction de
  l’index : zéro visite de la liste pour chercher le résultat, zéro réévaluation
  du prédicat de complétude pendant dix changements de sélection.
- Dans les deux scénarios de fenêtre scindée : zéro passage dans le filtre de
  gauche, un passage pour la ligne de droite. Les tests déclenchent le vrai
  raccordement du signal des miniatures avec un QThread contrôlé, sans lancer
  de génération de miniature externe. Le compteur des appels virtuels est dans
  une sous-classe créée avant les vues et calibré positivement par une
  invalidation forcée ; il ne repose pas sur un remplacement tardif du callback.
- Les contrôles de cohérence des chemins, remplacements préliminaires, chemins
  dupliqués, suppressions multiples, réinitialisations, renommages et changements
  de métadonnées réussissent. Les rôles de décoration sont distingués.

Ces nombres mesurent du travail exécuté, pas une durée garantie ni une
fréquence d’affichage sous Plasma. Les chiffres de 174 ms et 3,6 ms cités dans
la critique ne sont pas présentés comme des mesures refaites sur cet hôte.

## Trois passages ciblés exécutés ici

| Passage | Tests | Durée unittest | Échecs | Erreurs | Code |
|---|---|---|---|---|---|
| 1 | 134 | 29.263 s | 0 | 0 | 0 |
| 2 | 134 | 36.010 s | 0 | 0 | 0 |
| 3 | 134 | 39.203 s | 0 | 0 | 0 |

134 tests par passage, aucun ignoré. Journaux bruts : passage-1.log à passage-3.log.
Ils comprennent les contrôles natifs de menu et de raccourcis, de barre d’outils,
de configuration, de clavier et de panneaux ; ainsi que les transferts entre
panneaux, la mise à jour de présentation, la sélection après transfert, les
miniatures, le modèle de présentation natif, le renommage et son annulation,
la file des durées et la mise à jour des entrées visibles.
Aucun traceback ni erreur de wrapper Qt détruit dans ces trois journaux.

## Environnement et limites

Python 3.12.14, Qt/PySide6 6.12.0, KF6 6.13.0 extraits de paquets Debian.
Le moteur KItemListView et le modèle de présentation sont ceux compilés pendant
le travail RC191 à partir de sources identiques à RC192 ; ils sont chargés dans
la vraie fenêtre pour les tests. Le pont des dialogues contient les adaptateurs
réels de KDE, mais pas le panneau Emplacements complet. Les bibliothèques
natives n’ont pas été recompilées pour cette modification purement Python.
Sources de référence inchangées : Dolphin v26.08.2 / KF6 6.31.0.

Ce ne sont pas trois passages de la suite intégrale. La compilation complète
KIO/Emplacements, la suite complète, makepkg, pacman, Plasma/Wayland, les styles
Union/Breeze réels et les opérations sur ext4/NTFS3 de la machine cible ne sont
pas déclarés validés ici. Le repli Qt ancien est simulé en masquant l’API récente ;
aucune exécution réelle de Qt 6.8/6.9 n’est revendiquée.

La commande ./Valider-RC192.sh conserve la compilation complète et tous les
tests, avec une limite de 600 s. La commande d’installation s’arrête avant
pacman si cette étape échoue. Les résultats historiques restent dans leurs
répertoires validation/RCxxx. Aucun test existant n’a été retiré pour réussir.

## Périmètre préservé et gel

Pas de nouvelle fonction, de réorganisation générale des documents, de portage,
de changement du moteur de vues, du tri, des colonnes média, des raccourcis,
du mode de session ou des choix des installations existantes. Aucun changement
de dépendance ou de licence. kservicemenurc reste volontairement partagé.

Les fonctions sont gelées à partir de cette version. Les critères de sortie
stable restent à satisfaire, notamment les trois suites intégrales et les
scénarios de session concernés. Le principal risque résiduel est un futur
chemin de mutation du modèle qui oublierait ses notifications Qt : les tests
ajoutés et les tests de transferts/renommage surveillent cette cohérence.
