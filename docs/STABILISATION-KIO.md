# Stabilisation KIO : Corbeille desktop et annulation

Base : main faa828e0929dd91d3fe439a05b25048e7ebbe38b.
Les tests et constructions s'exécutent exclusivement sur GitHub Actions, sur
des fichiers, HOME/XDG et Corbeille jetables.

## Défauts visés

- Dépôt desktop:/ vers la Corbeille : le worker de transfert reçoit une URI
  de redirection et peut déplacer le fichier tout en signalant un échec.
- Annulation de suppression/corbeille pendant une confirmation :
  DeleteOrTrashJob ne fournit pas de doKill ; le service finit par être arrêté
  par le client Python, perdant l'historique d'annulation de la session.

## Correction proposée

Le service résout les sources desktop:/ par l'API publique KIO::mostLocalUrl
avant toute mise à la Corbeille. Toutes ces résolutions doivent réussir avant
de commencer. Les liens ne sont pas résolus par realpath ; le chemin fourni
par le worker est transmis à KIO.

Un job composite annulable propage l'arrêt au sous-job actif. Chaque demande
de suppression possède le parent de ses dialogues de confirmation, détruit
quand la demande se termine. Le service et FileUndoManager restent vivants.
Les confirmations et l'enregistrement des opérations restent ceux de KDE.
La suppression définitive conserve les URL d'origine.

Sources API inspectées : KDE KIO v6.31.0 statjob.h et deleteortrashjob.cpp ;
KCoreAddons v6.31.0 kjob.cpp et kcompositejob.cpp.
Il s'agit d'adaptateurs des API publiques, sans copie de leur implémentation.

## Validation attendue

Les tests de tests/test_c1_h1_h2_regressions.py doivent vérifier :
- annuler les confirmations corbeille et suppression sans redémarrer le service,
  sans toucher au fichier, puis annuler réellement une opération antérieure ;
- déposer un nom desktop terminé par un espace sans toucher à son homonyme ;
- déposer un lien desktop sans toucher à sa cible ;
- refuser un lot desktop si une résolution échoue, sans traiter le premier fichier.

Le worker desktop Plasma est explicitement installé en CI Fedora et son absence
fait échouer les nouveaux tests au lieu de masquer la couverture.
Les résultats exacts de reproduction et de validation sont consignés dans la PR.

Ces tests hors écran n'établissent pas une validation complète d'une session
Plasma, de NTFS3, des mises à jour ou des médias. Aucun numéro de version stable
n'est attribué, aucune publication ni modification des protections.
