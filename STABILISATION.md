# Critères de publication de Mirivue KDE 1.0

Base auditée : **1.0.0-beta.6**, main `faa828e0929dd91d3fe439a05b25048e7ebbe38b`.
Candidat préparé : **1.0.0**, sans publication.
Bilan daté et preuves : [audit stable](docs/AUDIT-STABLE.md) et [qualification 1.0](docs/VALIDATION-1.0.md).

Les fonctions sont gelées. Avant la version stable, seuls les défauts reproduits,
les corrections de tests obsolètes et la documentation de sortie sont traités.
Claude hébergé et l'extension du TestLab ne sont pas des prérequis de sortie.

## Documents courants

- `README.md` : installation et portée du produit.
- `docs/VALIDATION-beta.6.md` : résultats de la bêta et limites.
- `docs/AUDIT-STABLE.md` : critères satisfaits, preuves manquantes et ordre de travail.
- `docs/PUBLICATION-CONTROLEE.md` : autorisations et circuit de publication.
- `CHANGELOG.md` : historique.

Les scripts et rapports RC194 restent historiques. Ils ne constituent pas une
procédure validée pour la bêta 6. Aucun essai sur un poste personnel n'est demandé :
la préparation et les nouvelles validations ont lieu exclusivement dans le cloud.

## Conditions pour la version stable

Les exigences antérieures restent ouvertes tant qu'une preuve ne les satisfait pas :

- Trois suites complètes consécutives réussies, avec journaux, nombre de tests,
  durée et code de sortie ; trois passes d'un scénario ciblé ne suffisent pas.
- Compilation native neuve et contrôle du paquet installé sur chaque cible annoncée.
- Scénarios de fichiers ext4 et NTFS3, conflits, annulation, corbeille et restauration
  réussis ; toute perte ou écrasement non demandé bloque la sortie.
- Protocoles et systèmes de fichiers non essayés annoncés comme non validés.
- Aperçus, audio/PipeWire, session prolongée, mise à jour et retour arrière vérifiés
  pour chaque mode distribué.
- Versions de l'application, Python, AppStream, RPM et Arch cohérentes ; notices
  livrées complètes ; preuves rattachées au commit candidat exact.

Une suite ciblée ne suffit pas à satisfaire ces conditions. La campagne fonctionnelle
complète est acquise ; le paquet portant la version 1.0 doit réussir les mêmes contrôles.
Les essais Plasma historiques ne sont ni annulés ni présentés comme de nouveaux
résultats sur le candidat. Toute réduction d'une exigence est une décision de
portée du mainteneur, jamais une conséquence d'un test rouge.

## Correction après le gel

Reproduire le défaut, ajouter ou réutiliser un test pertinent, appliquer le
correctif minimal et vérifier les régressions concernées sur GitHub Actions.
Aucune refonte, fonction supplémentaire ou retouche d'apparence sans défaut démontré.
Les PR restent séparées de l'autorisation de fusion et de publication.
Ne pas modifier les protections de main. Conserver la version précédente.
