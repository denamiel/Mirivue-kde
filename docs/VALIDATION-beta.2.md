# Mirivue KDE 1.0.0-beta.2 — périmètre de validation

Version de consolidation, sans nouvelle fonction de gestion des fichiers.
La révision RPM commence à `0.197.beta2.1` : ce compteur interne assure une
mise à jour supérieure aux anciennes révisions `0.196.beta1.*`. La version
visible est `1.0.0-beta.2`, également déclarée `1.0.0b2` pour Python.

## Contrôles obligatoires avant publication COPR

| Domaine | Vérification | Nature du contrôle |
|---|---|---|
| Copie et déplacement Python | contenu SHA-256, Unicode, fichiers cachés, liens, source conservée ou retirée selon l’opération | moteur réel, fichiers jetables |
| Copie et déplacement KIO | mêmes invariants, y compris passage entre le disque du runner et `/dev/shm` puis retour | service KIO compilé réel, session D-Bus isolée |
| Conflit | annulation sans écrasement de la destination | service KIO réel et moteur Python |
| Annulation | source intacte après demande d’annulation | service KIO réel et moteur Python |
| Incident | disque plein simulé et erreur inattendue | injection d’erreurs contrôlée dans le moteur Python |
| Source modifiée | nouvel élément ou fichier modifié conservé, copie publiée intacte | tests de concurrence déterministes |
| Fermeture | fenêtre masquée pendant les travaux, fermeture différée après la fin, réouverture possible | vraie fenêtre Qt, frontière de fin des tâches contrôlée |
| Deux panneaux | copier/déplacer dans les neuf combinaisons de vues, dans les deux directions | vraie interface Qt ; transport substitué dans ces tests d’interface |
| Dolphin | sélection, onglets, styles de vue, retour à l’onglet précédent, restauration de session, renommage | moteur de vue natif et événements Qt |
| Diagnostic | plusieurs processus, PID réutilisé, ancien démarrage et session interrompue | marqueurs dans un dossier temporaire |
| Distribution | construction, installation, lancement, guides installés | Fedora 44 et 45 ; construction Arch séparée |

Les résultats de chaque exécution sont consultables dans GitHub Actions.
Un succès de compilation ne remplace pas les suites de comportement. Le
workflow Fedora doit réussir avant d’avancer la branche `publication`.

## Messages utilisateur

- **Informations sur l’installation** : liste les composants disponibles et la
  révision exacte ; ce rapport n’explique pas à lui seul une erreur.
- **Arrêt précédent incomplet** : signale une absence de fermeture normale,
  sans affirmer une perte de fichiers ; invite à vérifier source et destination
  si une opération était en cours, puis à consulter le journal.
- **Informations multimédias non lues** : un fichier incomplet, inaccessible ou
  non reconnu reste distinct d’un plantage de l’application. Les détails
  techniques sont conservés pour le dépannage.

## Limites explicites

Les essais automatisés Qt utilisent le backend offscreen et un D-Bus isolé.
Ils ne remplacent pas une utilisation sous Plasma/Wayland, sur NTFS, un partage
SMB/SFTP, un disque externe retiré physiquement ou un ordinateur suspendu.
Le test entre systèmes de fichiers n’est pas une validation de tous les types
de disques. Le disque plein est simulé pour le moteur Python ; il n’a pas été
provoqué physiquement pour KIO. Les deux moteurs ont des garanties différentes :
les contrôles SHA-256 de Mirivue ne sont pas ajoutés aux opérations KIO.
Aucun moteur ne verrouille toutes les applications susceptibles d’écrire dans
la source. Un arrêt brutal peut laisser une copie temporaire à examiner.
La bêta 2 reste une préversion et ne prétend pas être exempte de défauts.
