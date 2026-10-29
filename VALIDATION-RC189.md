# Validation RC189 — titre attendu par le contrôle graphique

27 octobre 2026. Aucun changement fonctionnel par rapport à RC188.

## Résultat fourni par l'utilisateur

La compilation complète des composants C++ a réussi sur CachyOS, y compris
native/toolbar-editor.cpp et la liaison du pont KDE. Puis 554 tests ont été
exécutés en 50,160 s avec un seul échec :
test_real_toolbar_views_split_and_search_interactions, message
« la recherche ne sélectionne pas la rubrique trouvée ».

Il s'agit du journal utilisateur, pas d'une exécution effectuée sur cet hôte.
La commande set -e s'est arrêtée dans Valider-RC188.sh : elle n'a exécuté ni
Construire-paquet-CachyOS.sh, ni pacman -U, ni le vérificateur d'installation.
La version précédemment installée n'a donc pas été remplacée par ce parcours.

## Cause confirmée dans le code

mirivue/configuration.py crée la page « Configurations de colonnes » depuis RC188.
mirivue/ui_contract.py:290 attendait encore exactement « Colonnes ».
Le filtrage avait passé son contrôle ; c'est l'égalité sur le titre qui échouait.

Correction : une seule valeur attendue change dans ui_contract.py. La recherche
reste lancée avec « Colonnes ». La vérification d'une seule rubrique visible,
la sélection de la rubrique, l'effacement de la recherche, le retour de toutes
les rubriques et le changement de page restent intégralement conservés.

## Reproduction ciblée et résultats exécutés ici

Le test ajouté, tests/test_configuration_search_contract.py, lit le vrai titre
fourni à add_page dans configuration.py, extrait l'expression originale du
contrôle, puis l'évalue avec ce titre. Il échoue contre RC188 et réussit après
la correction. C'est un test d'invariant sans Qt, pas une exécution de l'interface.
Le corps de la recherche Qt et la fenêtre native complète ne sont pas lancés ici.

Trois passages du nouveau contrôle et des neuf tests existants de structure des
menus, sans échec :

| Passage ciblé | Tests | Durée unittest | Code de sortie |
|---|---|---|---|
| 1 | 10 | 0.029 s | 0 |
| 2 | 10 | 0.024 s | 0 |
| 3 | 10 | 0.032 s | 0 |

- Analyse AST : 205 fichiers Python hors preuves historiques.
- Syntaxe bash -n : 8 scripts et PKGBUILD.
- Tous les 109 fichiers natifs sont identiques à RC188.
- Sous mirivue/, seuls ui_contract.py et la version de __init__.py changent.
- Aucun autre ancien titre de rubrique n'a été trouvé dans une assertion de titre
  ou dans le groupe Navigation et fichiers des fichiers Python de l'application/tests.
- Diff intégral : validation/RC189/diffs/00-integral.patch.
- Journal utilisateur conservé : journal-utilisateur-rc188.log.

## Non exécuté ici

PySide6/KF6 et le moteur complet ne sont pas disponibles dans l'environnement
courant. La suite complète, le contrôle graphique Qt, une nouvelle compilation
native, makepkg, pacman et Plasma/Wayland n'ont pas été exécutés ici. La réussite
de compilation RC188 sur le PC utilisateur n'est pas présentée comme une
nouvelle construction de RC189. Les preuves historiques conservent leurs versions.

Sur CachyOS, la commande complète de validation reste :

```bash
./Valider-RC189.sh
```

Cette étape reste obligatoire dans la commande d'installation ; aucun contrôle
ni test n'est supprimé, ignoré ou contourné.
