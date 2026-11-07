# Préparation de Mirivue KDE 1.0.0-beta.6 — non publiée

État : préparation uniquement. Ne pas fusionner cette branche, créer de tag/release, pousser vers `publication`, COPR, ni vers le dépôt Pacman sans validation explicite.

Base : fusion de la PR #5 dans `main` (commit `d4d5b95363619ae1548585cf25f9b028bba7bce1`).

## Contenu à intégrer dans la prochaine version
- Correctif C1 : préservation des URL complètes et des noms avec espaces finaux dans les opérations KIO, la navigation et les Emplacements.
- Correctif H1 : ne jamais résoudre la cible d'un lien symbolique lors d'une opération sur le lien.
- Correctif H2 : gestion des suppressions KIO locales et distantes, confirmation KDE et états des actions Corbeille.
- Affichage des liens symboliques cassés dans le premier inventaire, F5 et le suivi des dossiers, y compris les extensions multimédias.
- Tests permanents et notes de validation de la PR #5.

## Travaux de versionnement à effectuer sur cette branche
1. Répertorier **tous** les endroits où `1.0.0-beta.5`, `beta5`, `0.200.beta5` et les noms d'archives sont utilisés (spec, PKGBUILD, métadonnées Python, docs, scripts et tests figés).
2. Proposer un versionnement cohérent pour `1.0.0-beta.6` et la révision des paquets Fedora/Arch, strictement supérieur aux versions déjà distribuées ; éviter de modifier les anciens rapports d'archives.
3. Vérifier la génération des archives sources, l'intégration des assistants natifs recompilés, la cohérence des métadonnées et les mécanismes de refus de mise à jour pendant que Mirivue est ouvert.
4. Exécuter les tests ciblés, puis construire les paquets Fedora 44/45 et Arch/CachyOS dans les workflows de PR, sans les publier.
5. Examiner les anomalies résiduelles consignées dans la PR #5, en distinguant corrections bloquantes et travaux ultérieurs.
6. Faire relire les changements de version et les artefacts produits avant toute fusion ou publication.

## Validation disponible
- 19/19 essais manuels Fedora 45 / KDE Plasma réussis, selon le retour de l'utilisateur, après le correctif des liens cassés.
- CI de la PR #5 verte avant fusion.
- Les essais de validation ont été nettoyés, selon la confirmation de l'utilisateur.

## Attention aux automatisations existantes
Le workflow `.github/workflows/fedora-package.yml` contient un job `publish` qui, après un `push` réussi sur `main`, pousse automatiquement le commit validé vers la branche `publication`. Préparer une version **uniquement sur cette branche de travail** et vérifier l'état de `publication` avant toute future fusion ; une absence de release ne garantit pas l'absence d'un avancement de publication.

Cette note n'est pas une autorisation de publier.
