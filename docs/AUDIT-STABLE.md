# Audit de préparation à Mirivue KDE 1.0 stable

Audit du 12 novembre 2026, exclusivement via GitHub, sur main
`faa828e0929dd91d3fe439a05b25048e7ebbe38b` (1.0.0-beta.6).
**Décision technique : stable non encore démontrée.** Aucune publication effectuée.

## Suivi de la qualification

- PR #27, commit `02dde64b64e7b019fc8a307f3fd3d7a102f653b7` :
  [run 43280299908](https://github.com/denamiel/Mirivue-kde/actions/runs/43280299908)
  réussi sur Fedora 44/45/Rawhide, Python, X11 et KWin virtuel. Les deux incidents
  KIO ci-dessous sont corrigés sur cette branche ; les 54 tests C1/H1/H2 passent
  sans test ignoré, worker desktop inclus. Voir `docs/STABILISATION-KIO.md`.
- Première suite intégrale sur le candidat cumulé `83e5765`,
  [run 43280350215](https://github.com/denamiel/Mirivue-kde/actions/runs/43280350215) :
  137 suites parcourues, 777 tests comptés, sept suites en échec ou bloquées,
  19 tests TestLab ignorés faute de leur profil graphique. Journaux conservés
  dans l'artefact `qualification-stable-suites`, pas de validation stable annoncée.
- Écarts constatés : assertions de texte obsolètes (progression, colonne de
  dossier et construction des jobs Corbeille), préparation du paquet sous un
  mauvais répertoire, confusion entre fichiers suivis et outils construits,
  lecture trop tôt du résultat asynchrone des renommages, fermeture de fenêtres
  de test non attendue avant destruction de leurs dossiers. Les assertions de
  résultat restent exigées ; une pile est capturée avant tout nouveau délai.
- Qualification suivante : toutes les suites avec les vrais profils X11 et
  Wayland ; le test du faux programme conçu pour refuser root est rejoué sous
  le compte jetable et reste identifié dans le rapport. Tout autre test ignoré,
  échec ou suite vide reste bloquant. Trois passes ne sont tentées que si la
  première est entièrement couverte et réussie.
- Des jobs distincts préparent des images ext4/NTFS3 et un cycle Arch
  installation/mise à jour depuis le paquet bêta 5 épinglé/retour arrière.
  Ils ne constituent pas encore une preuve de mise à jour vers une version 1.0
  ni une validation de mise à jour Fedora.

Les nouveaux noms de jobs sont classés informatifs dans le vérificateur. Les
six contrôles requis et le ruleset effectif ne sont pas modifiés. Aucun appel
d'application des protections n'est effectué.

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

## Preuves complémentaires hors main

La [PR #14](https://github.com/denamiel/Mirivue-kde/pull/14) contient déjà un
prototype de VM Plasma. Le [run 43069359248](https://github.com/denamiel/Mirivue-kde/actions/runs/43069359248)
réussit ses jobs KVM, RPM, pilote, contrôle négatif, trois démarrages et une
opération clavier/souris. La documentation du commit de tête
`2682b09620e49549752e92c320f4cf5e69978435` rapporte la création d'un dossier
par Mirivue avec fichier témoin intact. C'est une preuve antérieure sur sa
référence de fusion, pas une validation du main audité. Le prototype ne couvre
pas encore copie, renommage et corbeille ; sa stabilité reste annoncée insuffisante.
Réutiliser ce travail si nécessaire, sans construire un second banc ni exiger
sa promotion en contrôle obligatoire.

La branche COPR `publication` pointe sur
`4e5d34f4078e35a3fb1573a5cb5d2882b20ab253` (préparation bêta 6).
Cela identifie les sources proposées à COPR, pas la réussite d'une build publiée.

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
