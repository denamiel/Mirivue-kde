# Validation RC187 — cohérence des commandes

26 octobre 2026. Correction limitée aux six points acceptés par l'utilisateur.

## Corrections

- app.py : selection_writable partage les gardes de chargement, consultation
  d'archive et fichiers occupés. Le menu contextuel et Outils les utilisent.
- app.py : can_create_archive partage le refus des emplacements distants et des
  objets non Path. Aucun accès disque ajouté au calcul de disponibilité ; la
  fonction create_archive conserve son contrôle d'existence avant de lancer Ark.
- configuration.py : paramètres externes toujours modifiables ; le sélecteur est
  explicitement réservé au choix F2 pour plusieurs fichiers. Valeurs existantes
  et préférence intégré/externe conservées, aucune migration.
- app.py / keyboard.py : destinations des deux commandes de terminal expliquées
  par infobulle, sans changer les raccourcis ni les fonctions exécutées.
- rename_ui.py : titre Renommage avancé ; le titre spécifique au contenu d'un
  dossier est conservé. Les méthodes et les écritures de renommage sont inchangées.
- configuration.py : aide des miniatures expliquant style commun, par dossier et
  emplacements spéciaux ; aucun changement de persistance.

## Reproduction avant correction

Les sept tests de tests/test_command_consistency.py ont été exécutés contre les
sources RC186 : sept tests exécutés, huit assertions en échec (sous-cas inclus),
zéro erreur d'exécution. Journal : validation/RC187/rc186-avant.log.

Le formulaire ConfigurationDialog est réel, avec un propriétaire QWidget isolé.
La page des services est remplacée pour ne pas écrire dans kservicemenurc.
Les tests de menus exécutent les vrais blocs et méthodes extraits par AST, avec
QMenu/QAction réels pour le menu contextuel et un propriétaire simulé ; les
helpers partagés réels sont employés dans RC187. Les dialogues de renommage
sont réellement construits mais rejetés sans écrire. Les infobulles des
terminaux sont vérifiées sur les actions construites par leur code réel ; aucun
terminal n'est lancé. Ce ne sont pas des tests d'un Window/KItemListView complet.

## Résultats exécutés ici

Qt/PySide6 6.12.0 hors écran. Trente contrôles : sept nouveaux de cohérence,
quatre de renommage RC186, neuf de structure des menus et dix de dates. Les
dates utilisent la sonde KFormat 6.31.0 compilée pour RC184, pas le pont complet.

| Passage ciblé | Tests | Durée unittest | Code de sortie |
|---|---|---|---|
| 1 | 30 | 0.209 s | 0 |
| 2 | 30 | 0.198 s | 0 |
| 3 | 30 | 0.196 s | 0 |

- Analyse AST : 200 fichiers Python hors preuves historiques.
- Syntaxe bash -n : 8 scripts et PKGBUILD.
- Sources natives identiques à RC186 : 108 fichiers.
- Diff : validation/RC187/diffs/00-integral.patch.
- La fixture contextuelle RC186 est complétée avec les deux prédicats désormais
  nécessaires ; ses assertions, dont l'absence du doublon de renommage, restent.

## Non exécuté ici

Suite complète avec moteur natif, compilation complète, pacman, Plasma/Wayland,
Corbeille KIO réelle, glisser d'onglet et détachement. Les résultats ciblés ne
sont pas présentés comme ces validations. Les preuves des versions précédentes
restent identifiées par leur numéro d'origine.

Commande complète sur CachyOS : ./Valider-RC187.sh. La commande d'installation
conserve cette étape avant de construire puis d'installer le paquet.

## Conservé volontairement

- Les deux commandes de terminal et leurs destinations distinctes.
- Les accès spécialisés aux métadonnées et à l'outil de renommage externe.
- F2, les colonnes médias, les profils, l'aperçu en gras, les réglages de session.
- Le partage voulu de kservicemenurc ; aucune modification des services natifs.
- Les conditions de présence des commandes selon le type de média ; ce correctif
  harmonise leurs gardes de disponibilité, sans refaire les menus.
- Les autres moteurs, assistants C++, transferts et fonctions de fichiers.
