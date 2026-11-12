# Audit de préparation à Mirivue KDE 1.0 stable

Audit du 12 novembre 2026, exclusivement via GitHub, sur main
`faa828e0929dd91d3fe439a05b25048e7ebbe38b` (1.0.0-beta.6).
**Décision technique : stable non encore démontrée.** Aucune publication effectuée.

## Preuves disponibles

- [CI Fedora 43258212980](https://github.com/denamiel/Mirivue-kde/actions/runs/43258212980) :
  Fedora 44, 45 et Rawhide, Python 3.11/3.x, TestLab X11 et KWin virtuel réussis.
  Jobs et journal Fedora 45 131322102223 examinés. Les régressions C1/H1/H2
  exécutent 49 tests, dont un sauté : worker Plasma desktop:/ absent.
  Le contrôle runtime exécute 87 tests ; ce n'est pas la suite intégrale.
- [CI Arch 43258212994](https://github.com/denamiel/Mirivue-kde/actions/runs/43258212994) :
  construction réussie, publication sautée. Le PKGBUILD vérifie compilation Python
  et dépendances de deux assistants ; il ne lance pas les parcours graphiques.
- Publication COPR sautée dans le run Fedora. Aucune release GitHub retournée par
  l'API du dépôt ; cela ne renseigne pas les versions effectivement présentes sur
  COPR ou le dépôt Pacman. Leur état reste à vérifier avant publication.
- `docs/VALIDATION-beta.6.md` rapporte 19 essais Plasma utilisateur réussis
  sur les correctifs de #5 et un essai SFTP privé. Preuve historique conservée,
  sans demander à l'utilisateur de refaire cette campagne.
- 137 fichiers `tests/test_*.py` à la racine des tests dans l'arbre audité :
  inventaire de fichiers, pas nombre de tests exécutés ou tous applicables.
- [Comparaison Claude 43272225925](https://github.com/denamiel/Mirivue-kde/actions/runs/43272225925) :
  échec des deux voies invalid_request. Hors critères de sortie du produit.

## Écarts démontrés et première correction

1. `STABILISATION.md` désignait encore RC194 et des commandes sur le poste
   personnel. Le document est remis en cohérence avec bêta 6 et le travail cloud,
   sans abaisser ses exigences de validation.
2. `native/clipboard-paste.cpp` et `native/file-properties.cpp` portent MIT
   mais manquent dans l'index `LICENCES-TIERS.md` : index complété (23 fichiers).
3. `test_freeze_documents.py` suppose une version rc et refuse les sections
   bêta du changelog : test adapté au format actuel et ajouté au contrôle runtime.
   La vérification pure de l'index MIT évite de dépendre d'un test GUI non exécuté.
   Les résultats de cette correction doivent être lus dans la CI de sa propre PR.

## Blocages de validation avant de déclarer stable

| Exigence | État vérifié | Travail restant |
|---|---|---|
| Trois suites complètes consécutives | Non démontré ; CI sélectionnée seulement | Qualifier les suites applicables, corriger les tests obsolètes et vrais défauts, puis conserver trois résultats complets |
| Paquets sur les cibles annoncées | RPM installé et smoke-test Fedora ; construction Arch | Vérifier installation, mise à jour et retour arrière Arch/Fedora sur données jetables |
| Sécurité des fichiers ext4/NTFS3 | Régressions KIO ciblées vertes ; pas de campagne NTFS3 actuelle identifiée | Produire les preuves manquantes sur images jetables dans le cloud |
| Intégration Plasma et médias | KWin virtuel disponible ; Plasma complet/PipeWire non couverts par cette CI | Exploiter les preuves historiques et valider les parcours manquants sur un candidat exact |
| Versionnement stable et livraison | Métadonnées encore bêta 6 | Changer ensemble les versions seulement après traitement des blocages ; vérifier ordre de mise à jour |

L'absence de preuve n'est pas un défaut produit démontré. Aucun nouveau défaut
de perte de données n'est établi par cet audit documentaire.

## Défauts connus à qualifier

`docs/VALIDATION-beta.6.md` et `docs/VALIDATION-C1-H1-H2.md` signalent :
- dépôt d'une URI desktop:/ sur la Corbeille : opération possible avec faux échec ;
- annulation pendant une confirmation KDE : redémarrage du service et perte
  de l'historique d'annulation.

Ces chemins doivent être reproduits sur données jetables et évalués avant sortie ;
leur ancienneté ne justifie pas de les ignorer. Les observations de focus initial
et de sélection du nouveau dossier du TestLab restent à confirmer sous Plasma.
SMB reste non validé ; ne pas lui attribuer la preuve SFTP.

## Ordre de travail, sans nouvelle fonction

1. Corriger les incohérences documentaires/licences et valider leur PR.
2. Qualifier la suite intégrale existante et les deux incidents KIO connus ;
   corriger uniquement les défauts démontrés et leurs tests.
3. Compléter les preuves de fichiers, paquets et intégration manquantes en cloud.
   Réutiliser les outils existants ; ne pas imposer la fusion des PR TestLab
   #13/#14, ni #15/#18/#19 consacrées aux règles Claude ou diagnostics.
4. Préparer un candidat stable cohérent et une demande finale de fusion/publication,
   accompagnée des résultats exacts et limites restantes.

Aucune fusion, publication, modification des protections ou secrets, aucun nouvel
appel Claude et aucune exécution sur les ordinateurs personnels pendant cet audit.
