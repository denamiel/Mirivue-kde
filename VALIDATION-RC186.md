# Validation RC186

26 octobre 2026.

## Correctif minimal

Une seule ligne fonctionnelle retirée de mirivue/app.py:file_context_menu :
organize.addAction(self.batch_rename_action).
L'action et son insertion dans Outils → Renommer et organiser sont conservées.
Aucun changement des méthodes rename_f2, rename_advanced, rename_names,
rename_rows_with_chosen_tool ni de l'outil intégré.
Toutes les sources natives sont identiques à RC185.

## Reproduction avant / après

Le nouveau fichier tests/test_rename_context_access.py contient quatre tests.
Le premier exécute le bloc réel du sous-menu Organiser sur de vrais QMenu et
QAction Qt, avec un propriétaire isolé. Il échoue sur RC185 (l'action avancée
est présente) et réussit sur RC186. Journal : validation/RC186/rc185-avant.log.
Les trois autres exécutent le bloc réel du menu Outils et les méthodes réelles
de renommage extraites par AST. Ils vérifient l'accès à l'outil intégré depuis
Outils, F2 simple et F2 multiple avec chacun des deux choix intégré/externe.
Les écritures sur les fichiers sont simulées : aucune opération de renommage
réelle ni interaction avec un Window/KItemListView complet n'est revendiquée.

## Exécuté ici

Qt/PySide6 6.12.0 hors écran ; quatre nouveaux tests de renommage, neuf tests
existants de structure du menu et dix contrôles des dates (dont le formulaire
réel isolé et la sonde KFormat 6.31.0 compilée pour RC184).

| Passage ciblé | Tests | Durée unittest | Code de sortie |
|---|---|---|---|
| 1 | 23 | 0.103 s | 0 |
| 2 | 23 | 0.106 s | 0 |
| 3 | 23 | 0.106 s | 0 |

- Analyse AST : 199 fichiers Python hors preuves historiques.
- Syntaxe bash -n : 8 scripts et PKGBUILD.
- Sources natives identiques : 108 fichiers.
- Diff intégral : validation/RC186/diffs/00-integral.patch.

## Non exécuté ici

La suite complète avec le moteur natif, la compilation complète, pacman,
Plasma/Wayland, KIO réel, glisser d'onglet et détachement. Les tests ciblés ne
valident pas ces points. Les journaux des versions précédentes restent datés
et ne sont pas présentés comme de nouvelles exécutions RC186.

Sur CachyOS, la commande officielle reste ./Valider-RC186.sh avant construction
et installation. Aucun test n'est supprimé ni contourné.
