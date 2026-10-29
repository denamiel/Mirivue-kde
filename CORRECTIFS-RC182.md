# Correctif de validation RC182

## Défaut reproduit

Le journal transmis pour RC181 montre une compilation réussie, puis quatre
échecs dans `test_dolphin_navigation_policy`. La chaîne d'installation s'arrête
avant `pacman -U` : elle n'a donc pas remplacé l'application installée.

Les mêmes quatre échecs ont été reproduits sur RC181 inchangée avec un vrai
bus D-Bus de session jetable : 15 tests, quatre échecs. Les demandes externes
passent alors par le routage asynchrone. Les tests attendaient la lecture des
dossiers, mais pas la fin des échanges avec les fenêtres. Une assertion pouvait
ainsi intervenir avant le résultat attendu, ou après la sortie de son mock.

## Correction limitée aux tests

- `tests/test_dolphin_navigation_policy.py` : attendre aussi les routes non
  terminées appartenant à la fenêtre testée ; attendre avant les assertions et
  avant la disparition des mocks ; terminer ces échanges au nettoyage.
- Les 44 assertions sont conservées, ainsi que la limite de cinq secondes.
  Aucun résultat erroné n'est accepté et aucun test n'est désactivé.
- `Valider-RC182.sh` : lancer la suite sous `dbus-run-session` pour couvrir le
  chemin asynchrone et éviter les échanges avec les fenêtres personnelles.
- `tests/test_rc181_routing.py` : traiter les événements Qt déjà en attente
  avant de démarrer le chronomètre du test de transport. Les assertions de
  délai global et de battements Qt restent identiques.
- `tests/test_window_instances_dbus.py` : conserver dans la sortie du test les
  diagnostics des processus du bus privé en cas d'échec.
- Les références aux scripts renommés sont mises à jour dans les tests existants.

## Périmètre conservé

Les fichiers applicatifs Python sont identiques à RC181, sauf la version dans
`mirivue/__init__.py`. Les sources natives sont identiques (85 fichiers C++ et
en-têtes). Aucun changement de comportement des panneaux, des onglets, du tri,
des services, des préférences ou des opérations de fichiers.

La RC182 ne déclare pas la version 1.0 stable. Les résultats finaux et leurs
limites figurent dans VALIDATION-RC182.md. Les preuves historiques de RC181
restent dans validation/RC181 ; celles de cette correction dans validation/RC182.
