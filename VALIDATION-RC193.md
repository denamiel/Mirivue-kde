# Validation RC193 — ouverture de plusieurs vidéos

28 octobre 2026. Correctif demandé à partir de deux captures : Dolphin affiche
les applications associées à la sélection, Mirivue affichait « Ouvrir les N
éléments sélectionnés » puis construisait une liste à part.

## Modification et portée

Pour plusieurs fichiers sans dossier, file_context_menu appelle désormais
open_with.add_native_open_with. Le pont C++ transmet leurs URL à un
KFileItemActions conservé comme enfant du menu, fixe la fenêtre parente et
appelle insertOpenWithActionsTo. C’est l’API appelée par Dolphin v26.08.2 dans
src/dolphincontextmenu.cpp:495–498 ; le traitement multiple est :269–310.
La liste exclut l’identifiant de Mirivue, comme Dolphin exclut le sien.

Les associations sont communes à tous les fichiers, pas calculées sur le seul
élément cliqué. KIO fournit les noms, icônes, priorités et actions de lancement.
La sélection complète est transmise. Le bloc générique et le sous-menu Python
ne sont pas ajoutés quand le traitement natif a abouti, même si une restriction
KDE n’autorise aucune action. Un composant absent garde le repli existant.

Les cas d’un fichier seul, des dossiers, l’exécution explicite des scripts,
les outils médias, le renommage, les transferts et les paramètres ne sont pas
modifiés. Le menu entier n’est pas revendiqué identique à Dolphin : la correction
porte sur son bloc d’ouverture pour une sélection multiple de fichiers.
La branche Renommer identique dans les cas simple et multiple est fusionnée
sans changement de résultat ; la limite existante de taille de app.py est
conservée, sans affaiblir son test.

## Référence et licences

La source de comportement est exclusivement Dolphin v26.08.2. L’empreinte est
consignée dans native/OPEN-WITH-REFERENCE.json. Le nouveau pont est un client
original MIT de l’API publique KIO, sans copie de l’implémentation de Dolphin.
La référence native/tests/open-with-reference.cpp appelle séparément cette API
pour les tests. Elle est construite quand MIRIVUE_NAVIGATOR_TESTS est actif,
mais n’est pas installée dans le paquet. Le catalogue MIT natif comporte vingt
fichiers, tous listés dans LICENCES-TIERS.md ; les licences combinées restent.
Aucune nouvelle dépendance d’exécution n’est ajoutée : KIO est déjà requis.

## Tests avant et après

Sept tests ajoutés dans test_multi_open_with.py :
- remplacement du bloc générique par les actions KDE, avec tous les chemins ;
- un résultat natif vide ne réactive pas la commande générique ;
- repli inchangé si le composant est indisponible ;
- commandes inchangées pour un fichier seul et des dossiers ;
- encodage/transmission des URL locales, Unicode, avec deux-points et distantes ;
- absence de composant signalée comme résultat non traité ;
- comparaison native de trois MKV, puis deux MKV et un MP4, avec une référence
  indépendante utilisant l’appel KIO de Dolphin.

Les deux premiers tests échouent sur RC192 : ils confirment que le constructeur
n’appelle pas l’ouverture KDE et continue à ajouter le bloc générique. Journal
avant-ouverture-multiple.log. Les sept réussissent après correction.
Les tests de construction exécutent l’extrait exact de file_context_menu avec
des actions/une fenêtre Qt contrôlées ; ils n’instancient pas le moteur complet.
Le test natif crée de vrais QMenu et KFileItemActions. Les données desktop,
préférences MIME et cache sycoca sont dans des chemins XDG jetables ; un menu
applications.menu de test est aussi fourni pour que le catalogue fonctionne
sans installation Plasma sur l’hôte. Les applications propres à un seul format
sont absentes de la proposition commune à MKV/MP4. Aucun lecteur réel n’est lancé.
Les URL invalides et JSON invalides sont refusés sans ajouter d’action.

## Trois passages ciblés exécutés ici

| Passage | Tests | Durée unittest | Échecs | Erreurs | Code |
|---|---|---|---|---|---|
| 1 | 49 | 0.525 s | 0 | 0 | 0 |
| 2 | 49 | 0.561 s | 0 | 0 | 0 |
| 3 | 49 | 0.565 s | 0 | 0 | 0 |

49 tests à chaque passage, aucun ignoré. Ensemble : les sept nouveaux contrôles,
menus principaux, documents de gel, accès au renommage, cohérence des commandes,
menu Créer, contrat de distribution, identifiants techniques, paquet Arch,
index/compteur et API de filtre RC192, invariant de recherche des paramètres.
Les tests existants ne sont pas retirés ou assouplis pour faire passer ce correctif.

Le pont open-with-menu.cpp et la référence C++ ont été réellement compilés puis
chargés. Qt/PySide6 6.12.0, en-têtes Qt 6.11.2 et KF6/KIO 6.13.0 extraits de
paquets Debian ; Python 3.12.14. Ne pas confondre ces bibliothèques exécutées
avec le tag Dolphin v26.08.2 de référence. Les copies de KF6 ne sont pas livrées
avec l’archive. La structure des menus sur le PC utilisateur dépendra de sa
version de KIO et de ses associations, exactement comme pour Dolphin sur ce PC.

## Non exécuté ici

Ce ne sont pas trois suites intégrales. Le moteur de fichiers et le pont
Emplacements complet ne sont pas disponibles dans l’environnement actuel.
Ils n’ont pas été reconstruits ici. Le contrôle natif repose sur une bibliothèque
de test avec les deux nouvelles sources C++ ; le projet complet reste construit
par Valider-RC193.sh. Pas d’exécution revendiquée de makepkg, de pacman, de la
session Plasma/Wayland, d’un lecteur multimédia réel ou d’une comparaison
visuelle sous Breeze/Union. Les scénarios de fichiers ext4/NTFS3 restent inchangés.

Valider-RC193.sh construit la référence de test et transmet son chemin aux tests.
La suite intégrale garde sa limite de 600 s, et la commande d’installation reste
arrêtée avant pacman en cas d’échec. Le gel des fonctions reste en vigueur ; ce
correctif de conformité réouvre uniquement la validation du parcours concerné.
Les preuves brutes et le diff intégral se trouvent dans validation/RC193.
