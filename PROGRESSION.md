# Progression des opérations — RC193

Les copies, déplacements, mises à la corbeille, suppressions et extractions
réalisées par le service KIO conservent les notifications et commandes
natives de KDE. Mirivue ne réplique plus leurs pourcentages dans sa barre
de chargement. Les dépôts natifs vers Emplacements et les fils d’Ariane
restent gérés directement par KIO::drop ; leur présentation reste native.

La fenêtre Opérations répertorie les demandes du service KIO et permet de
les annuler individuellement ou collectivement. Elle ne prétend pas compter
les fichiers récursifs traités : la colonne Éléments indique le nombre de
sources sélectionnées, et KDE conserve les détails du travail. Les demandes
du service restent sérialisées comme avant ; cet indicateur ne signifie pas
que plusieurs copies physiques sont exécutées simultanément. Les dépôts
natifs externes à ce service ne sont pas ajoutés artificiellement à cet
historique : leur suivi et annulation restent ceux de KDE.

Le bouton Arrêter le chargement du dossier conserve son rôle. Les étapes
de préparation d’une extraction et les analyses gardent leurs propres
indicateurs et commandes. Une durée déjà calculée n’est plus remplacée par
un texte d’attente pendant l’analyse suivante.

La fermeture ne demande plus l’annulation d’une copie avant de présenter
le choix concernant les opérations en cours. Revenir à Mirivue conserve
les opérations ; Arrêter les transferts et quitter attend leurs retours.
L’option de conservation en arrière-plan conserve son fonctionnement.

## Vérifications automatiques

- Dix tests Qt dans test_kio_progress_routing_gui.py : indépendance de deux
  opérations, conservation de la barre de chargement, absence de barre de
  copie interne, accès à Opérations avec et sans Emplacements, clic sur
  l’annulation sélectionnée, historique, fermeture et conservation des durées
  dans les trois vues. Les signaux du transport KIO sont contrôlés ; les
  widgets, événements et vues natives sont réels.
- Quatre tests du protocole Python dans test_kio_request_cancellation.py :
  annulation pendant l’attente du service, annulation native pour huit types
  d’opérations, durée longue et absence de délai imposé aux transferts.
- Test supplémentaire du registre des tâches pour protéger explicitement
  les transferts lors de l’arrêt des lectures en arrière-plan.

La compilation couvre aussi mirivue-kio-service et son indicateur explicite
d’annulation. L’environnement d’essai ne permet pas d’ouvrir le bus D-Bus
nécessaire à une véritable session Plasma : les notifications, pauses et
reprises ne sont pas prétendues testées ici. Le service réel et la corbeille
jetable restent vérifiés par Verifier-installation-RC193.sh sur la machine
d’installation. Aucun nouvel essai manuel n’est demandé.

## Références utilisées

- Dolphin 26.08.2 : src/views/dolphinview.cpp,
  src/dolphinviewcontainer.cpp et src/statusbar/dolphinstatusbar.cpp.
  https://github.com/KDE/dolphin/tree/v26.08.2/src
- API KIO::CopyJob et conventions de progression native :
  https://api.kde.org/kio-copyjob.html
  https://api.kde.org/kio.html
