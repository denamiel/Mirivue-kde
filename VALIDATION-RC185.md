# Validation RC185 — attente des groupes de configuration

26 octobre 2026. Aucun changement fonctionnel par rapport à RC184.

## Ce que montre le journal utilisateur

La compilation native complète a réussi sur la machine CachyOS. La suite de
531 tests s'est terminée en 50,491 s avec un seul échec :
test_configuration_groups_and_startup_only_preview_choice.
Ce résultat est fourni par l'utilisateur, pas exécuté de nouveau sur cet hôte.
La commande set -e s'est arrêtée avant la construction du paquet et pacman :
ce parcours n'a donc pas installé RC184.

## Cause confirmée et correction minimale

RC184, tests/test_ergonomics_gui.py:124 attend exactement quatre groupes :
Démarrage, Fermeture, Navigation et fichiers, Confidentialité.
Le groupe Affichage a pourtant été ajouté en RC184 à la demande de l'utilisateur.

RC185 ajoute uniquement Affichage à cet ensemble attendu. La comparaison reste
une égalité exacte. Les assertions suivantes, concernant l'absence de l'ancien
historique et le réglage du panneau d'aperçu au démarrage, sont conservées.
Aucun test n'est retiré, ignoré ni remplacé par un simple test d'inclusion.
Les autres modifications des tests sont des références aux scripts renommés.

## Reproduction et résultats ciblés

Le corps original de la méthode a été exécuté sur un vrai ConfigurationDialog,
avec le contrôleur QWidget isolé des tests de dates. Il reproduit l'échec sur
RC184 : « Items in the first set but not the second: 'Affichage' ».
Le même corps réussit après l'ajout du groupe attendu.

Cette exécution réutilise le formulaire réel et deux vrais VideoModel ; elle
ne reproduit pas le setUp complet avec Window/KItemListView du test original.
La page de services est neutralisée pour ne pas écrire dans kservicemenurc.
Il ne s'agit pas d'une nouvelle exécution complète des 531 tests.

Trois passages du corps corrigé, plus les dix contrôles ciblés des dates :

| Passage ciblé | Contrôles | Durée unittest | Échecs/erreurs | Ignorés | Sortie |
|---|---|---|---|---|---|
| 1 | 11 | 0.125 s | 0 | 0 | 0 |
| 2 | 11 | 0.130 s | 0 | 0 | 0 |
| 3 | 11 | 0.120 s | 0 | 0 | 0 |

Journaux : validation/RC185/controles-cibles-1.log à -3.log.
Reproduction rouge : groupes-rc184-avant.log. Le journal de la machine de
l'utilisateur est conservé sous journal-utilisateur-rc184.log.

## Périmètre vérifié

- Sous mirivue/, seule la version dans __init__.py change.
- Toutes les sources natives sont identiques à RC184 ; aucune nouvelle
  compilation native n'est prétendue ici. Le journal utilisateur prouve leur
  compilation pour RC184, pas une nouvelle construction du paquet RC185.
- Les contrôles des dates utilisent Qt/PySide6 6.12.0 hors écran et la sonde
  KFormat 6.31.0 déjà compilée pour RC184. Ils vérifient les choix, l'annulation,
  la persistance, le contrôleur de dates et les valeurs numériques de tri.
- Analyse AST de 198 fichiers Python ; bash -n de 8 scripts/PKGBUILD.

- Diff intégral dans validation/RC185/diffs/00-integral.patch.
- Les preuves précédentes gardent leurs dossiers et versions d'origine.

## Non exécuté ici

La suite complète avec tous les composants natifs, l'installation pacman et
la vérification en session Plasma/Wayland. Les résultats de RC184 et ceux des
contrôles ciblés ne sont pas présentés comme cette validation complète.

Commande officielle sur CachyOS :

```bash
./Valider-RC185.sh
```

La commande d'installation fournie conserve cette validation avant de construire
et d'installer le paquet. Aucun contournement de la validation n'est proposé.
