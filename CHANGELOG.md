## 1.0.0-rc193 — 28 octobre 2026

- Pour une sélection de plusieurs fichiers sans dossier, le haut du menu utilise
  KFileItemActions::insertOpenWithActionsTo, comme Dolphin v26.08.2. Les actions
  des applications et le choix « Ouvrir avec » proviennent des associations KDE
  communes à toute la sélection ; chaque action reçoit tous les fichiers.
- La commande générique « Ouvrir les N éléments sélectionnés » et le sous-menu
  Python ne doublonnent plus cette partie native. Une restriction KDE laissant
  ce bloc vide n’est pas remplacée par une commande générique.
- Les cas d’un fichier seul, de dossiers et le repli sans composant natif gardent
  leur comportement existant. Les outils propres à Mirivue sont conservés.
- Référence KIO indépendante de test, construite par Valider mais non installée.
  Les préférences MIME des essais sont jetables ; aucune application média
  n’est lancée pendant les contrôles.

## 1.0.0-rc194 — validation Fedora et journaux complets

- Examiner et fermer les menus natifs depuis leur boucle d’événements dans les
  tests ; conserver les assertions et les délais, sans changer l’application.
- Utiliser un bus privé Unix/EXTERNAL quand disponible, avec repli TCP réservé
  aux environnements interdisant Unix ; retirer les adresses d’activation héritées.
- Conserver les sorties complètes des tests et de la compilation après nettoyage.
- Afficher l’erreur D-Bus précise en cas de refus d’enregistrement de la fenêtre de test.
- La cause exacte du refus constaté sur Fedora n’est pas reproduite localement ;
  aucune validation intégrale Fedora ou Plasma n’est revendiquée.

## 1.0.0-rc192 — 27 octobre 2026

- Évite le refiltrage d’un panneau lorsque son filtre de noms n’a pas changé.
  Utilise beginFilterChange/endFilterChange quand disponibles, avec repli pour
  Qt 6.8/6.9. Les autres critères restent inchangés.
- Les miniatures du panneau inactif n’entraînent plus une synchronisation
  complète de l’interface, de l’espace disque et des dates de l’autre panneau.
- Index des chemins et compteur de médias incomplets entretenus par les
  notifications du modèle : résultats ciblés sans parcours complet des lignes,
  sélection sans recomptage. Les doublons de chemin sont pris en compte.
- Tests des insertions, remplacements, suppressions, réinitialisations,
  renommages, métadonnées et miniatures, y compris dans la fenêtre scindée.
- STABILISATION.md décrit uniquement le parcours actuel et le gel effectif.
  Le contenu RC173 retrouve sa section et les titres du changelog sont unifiés.
  Les documents historiques restent en place et sont désignés comme tels.

## 1.0.0-rc191 — 27 octobre 2026

- Corrige l’invalidation des actions partagées pendant le remplissage du menu
  principal : retrait des références sans QMenu.clear(), notamment pour les
  actions créées par QMenu.addAction. Propriétés et Coller restent utilisables
  après le passage au clavier sur le bouton Menu.
- Les sous-processus des tests natifs reçoivent explicitement le dossier du
  projet dans PYTHONPATH, comme nécessaire depuis une archive non installée.
- Test ajouté : actions créées dans d’autres menus, réouvertures et Tab répétés,
  puis déclenchement unique des commandes. Les vérifications existantes restent.
- Aucun changement de fonctionnalités, de raccourcis ou de préférences.

## 1.0.0-rc190 — 27 octobre 2026

- Aperçus et lecture : trois groupes Miniatures, Panneau d’aperçu et Lecture.
- Édition : les commandes de copie du nom du dossier et des chemins sont
  regroupées avec Couper, Copier et Coller.
- Calculer la durée totale est directement accessible dans Outils.
- Le menu principal utilise KHamburgerMenu : commandes déjà visibles évitées,
  commandes spécialisées conservées dans les menus complets.
- Les raccourcis utilisent le vrai KShortcutsDialog. Les réglages Mirivue,
  les touches secondaires et les commandes sans touche sont conservés.
- La mémorisation globale de la taille de ce dialogue KDE est acceptée ;
  les combinaisons de touches ne sont pas écrites dans les réglages de Dolphin.

## 1.0.0-rc189 — 27 octobre 2026

- Le contrôle graphique attend le titre actuel « Configurations de colonnes ».
  La recherche reste exercée avec « Colonnes » ; les vérifications du filtrage,
  de la sélection de rubrique et du retour de toutes les rubriques restent.
- Aucun changement fonctionnel ni natif par rapport à RC188.

## 1.0.0-rc188 — 27 octobre 2026

- Réglages regroupés par Affichage, Navigation et Onglets ; la page des profils
  est nommée Configurations de colonnes sans modifier les préférences existantes.
- Les indications du bouton Menu suivent les raccourcis réellement configurés.
- Les commandes indisponibles exposent leur raison dans l'aide native QAction.
- La personnalisation utilise KEditToolBar et XMLGUI. Les anciens réglages sont
  repris ; ordre, visibilité, côté des chemins, séparateurs, espaces extensibles,
  icônes et textes sont enregistrés dans les préférences propres à Mirivue.
- Annuler conserve les réglages antérieurs au dernier Appliquer. Restaurer les
  réglages par défaut utilise la confirmation et l'application immédiate de KDE.
- Un rappel différé de la liste de catégories est lié à son contexte QObject
  pour ne pas viser un objet détruit lors de la fermeture de la configuration.

## 1.0.0-rc187 — 26 octobre 2026

- Menus Outils et contextuel : mêmes gardes pour les opérations sur une sélection
  occupée, pendant le chargement ou lors de la consultation d'une archive.
- Créer une archive est désactivé sur un emplacement distant, dans les deux menus.
- Les paramètres externes de renommage restent modifiables avec l'outil intégré
  choisi pour F2 ; ce choix ne concerne que le renommage de plusieurs fichiers.
- Explications distinctes pour les deux destinations de terminal ; titre de
  l'outil intégré harmonisé en Renommage avancé ; aide des miniatures précisée.

## 1.0.0-rc186 — 26 octobre 2026

- L'entrée « Renommage avancé… » n'est plus répétée dans le menu contextuel
  Organiser. Elle reste dans Outils → Renommer et organiser.
- F2, le renommage multiple, le choix de l'outil externe et les fonctions de
  l'outil intégré sont inchangés.

## 1.0.0-rc185 — 26 octobre 2026

- Le test des groupes de configuration attend désormais « Affichage », ajouté
  en RC184. La comparaison reste exacte et toutes les autres assertions restent.
- Aucun changement fonctionnel ni natif par rapport à RC184.

## 1.0.0-rc184 — 26 octobre 2026

- « Style de date » déplacé de Colonnes vers Général → Affichage.
- Deux boutons exclusifs « Relative » et « Absolue », avec un exemple de date
  remontant à trente minutes, comme Dolphin v26.08.2.
- Les dates relatives passent par KFormat::formatRelativeDateTime, le formateur
  KDE utilisé par Dolphin. Les dates absolues utilisent QLocale::ShortFormat.
- Les valeurs existantes informal/locale sont conservées. Un ancien choix ISO
  reste intact à l'ouverture et sur Annuler ; Appliquer/OK le remplace par
  l'affichage absolu régional. La compatibilité de lecture ISO reste disponible.

## 1.0.0-rc183 — 24 octobre 2026

- Le contrôle natif d'installation attend une fenêtre exposée et la réponse au
  redimensionnement au lieu de conclure après un seul processEvents().
- Il initialise la barre de chemin avec un dossier jetable avant de valider
  Entrée ; il ne transmet plus une URL vide à KIO.
- La limite artificielle de 700 pixels est retirée du scénario de contrôle.
  Un refus persistant de rétrécir reste un échec, avec géométrie et minima.
- Aucun changement du rendu, des contraintes ou du fonctionnement de Mirivue.

## 1.0.0-rc182 — 24 octobre 2026

- Correction de quatre tests de navigation : ils attendent désormais la fin
  du routage D-Bus asynchrone avant de vérifier onglets, sélection et fenêtres.
  Leurs assertions et le délai maximal de cinq secondes sont conservés.
- Valider-RC182.sh utilise un bus de session jetable, actif pendant les tests,
  afin de couvrir le chemin utilisé sous Plasma et d'isoler le bureau personnel.
- Le test de réactivité traite les événements Qt antérieurs avant sa mesure ;
  ses bornes restent inchangées. Les erreurs des clients du bus privé produisent
  désormais leurs diagnostics dans le journal.
- Les fonctions de l'application, ses réglages et son moteur natif ne changent
  pas. Seules la validation et les métadonnées de version sont corrigées.
- L'échec réel de RC181 est reproduit avec un bus actif (quatre échecs), puis
  les quinze tests concernés réussissent après correction. Voir VALIDATION-RC182.md.

## 1.0.0-rc181 — 24 octobre 2026

- Refus silencieux d'une activation/commande sur panneau fermé ; arrêt de son
  minuteur de colonnes, garde de relance des métadonnées et révélation de chemin
  de secours compatible avec la destruction différée des widgets. La surface
  native de dessin invalide aussi sa référence Python lors de sa destruction,
  pour éviter la réutilisation d’une ancienne adresse de widget.
- Entrées d'ouverture D-Bus normalisées et bornées ; routage Qt asynchrone des
  fenêtres vivantes, budget global et suivi des envois acceptés/incertains pour
  ne pas répéter un lot déjà accepté. Voir IPC-RC181.md.
- Fin de la coupure silencieuse à cent onglets ; contrôle de QSettings.status
  après sauvegarde, avec retour d'échec et message d'activité.
- Titres automatiques : KStringHandler::rsqueeze après échappement des &,
  quarante unités QString et trois points ASCII ; titres personnels conservés.
- Tri limité aux corrections demandées : dimensions largeur/hauteur, piste
  entière (y compris 2/12), auteur en comparaison brute, valeurs textuelles vides
  et départage nom affiché/nom réel/URL. Année/date reste une balise générale,
  pas un rôle releaseYear. Les autres comparaisons ne changent pas.
- Contrôle d'images : curseur de saisie figé uniquement dans le programme de
  test ; comparaison intégrale conservée et images de différence enregistrées.
  Le délai de démarrage de huit secondes reste inchangé, avec diagnostic ajouté.
- Mentions du code original et index des seize fichiers natifs MIT ; fichiers de
  provenance supplémentaires installés dans le staging du paquet.
- Page des services : libellés KDE sans suffixe technique ajouté, comme Dolphin
  v26.08.2 ; identifiants internes et partage de kservicemenurc conservés. Le
  chemin de provenance reste en infobulle, comme dans la page de Dolphin.
- Pas de changement des réglages session/dossier, des préférences historiques
  d'ouverture, du gras du renommage ni des colonnes média propres à Mirivue.

## 1.0.0-rc180 — 23 octobre 2026

- Services KDE insérés indépendamment du groupe Organiser, avec Propriétés comme
  point d’insertion de secours. Masquer Organiser ne retire plus les services.
- Détection des actions par identifiant natif, sans comparaison des traductions.
  Le service runInKonsole et les extensions Ark compressfileitemaction et
  extractfileitemaction remplacent leurs équivalents de secours dans le menu.
- Une seule case pour Konsole et la compression quand leur fournisseur KDE est
  installé ; la case KDE contrôle aussi le secours. Le désactiver ne le réactive
  plus par une seconde voie. Les commandes des menus principaux restent accessibles.
- La commande de déplacement vers un nouveau dossier reste celle de Mirivue,
  reliée à son historique d’annulation KIO. L’extension Dolphin équivalente est
  exclue seulement des menus de Mirivue, sans changer sa préférence dans Dolphin.
- Origine des services affichée dans la liste ; les homonymes de même origine
  gardent leur identifiant visible. Compression/extraction désignées par leur
  action et Ark ; Lancer un Exécutable devient Exécuter le fichier et Média
  devient Outils multimédias. Les accès au renommage intégré sont conservés.
- Intégration testée avec de vrais services .desktop et des extensions KF6 de
  validation compilées, qui ne réalisent aucune opération de fichiers.
  Voir VALIDATION-RC180.md et MENU-CONTEXTUEL.md.

## 1.0.0-rc179 — 23 octobre 2026

- Correction de QUrl.matches dans la résolution de secours des libellés
  d’Emplacements : conversion explicite vers ComponentFormattingOption,
  conformément à la signature exposée par PySide6. Le sens de la comparaison
  sans slash final reste identique.
- Régression reproduite avec un signet local réel ; essais ajoutés pour les
  signets locaux et SMB, les adresses différentes et la création/suppression
  de la vue scindée dans les trois modes quand le libellé natif est indisponible.
- Les réglages personnels, les signets et les fonctions de RC178 sont conservés.
  Résultats de validation dans VALIDATION-RC179.md.

## 1.0.0-rc178 — 23 octobre 2026

- Page Menu contextuel avec recherche, cases de commandes intégrées et services
  KDE installés, réglages par défaut, raccourcis et téléchargement KNewStuff.
  Découverte et préférences des services reprises de Dolphin 26.08.2.
- Préférences appliquées seulement à la validation ; les commandes masquées au
  clic droit conservent leurs autres accès. Les services partagent kservicemenurc
  avec Dolphin ; les commandes intégrées restent propres à Mirivue.
- Actions d’ouverture de dossiers en onglets, fenêtre ou vue scindée, et actions
  existantes de copie/déplacement vers l’autre panneau accessibles au clic droit.
- L’aperçu du renommage intégré met en gras uniquement les nouveaux noms
  modifiés sans conflit, avec une légende et mise à jour immédiate. Aucun ajout
  de couleurs ou de police imposée ; aucune modification des règles de renommage.
- Dépendance directe knewstuff pour le bouton de téléchargement KDE.
- Contrôles Qt réels de recherche, cases, application, abandon, valeurs par
  défaut, raccourcis, services partagés, trois vues et aperçu de renommage.
  Résultats dans VALIDATION-RC178.md ; détails dans MENU-CONTEXTUEL.md.

## 1.0.0-rc177 — 23 octobre 2026

- Fermeture d’un onglet pendant un chargement : annulation coopérative sans
  attente graphique, conservation des tâches jusqu’à leur fin et rejet des
  signaux/timers tardifs visant le panneau fermé. Le détachement conserve
  l’onglet source si la nouvelle fenêtre ne peut pas être créée.
- Les inventaires KIO passent par KCoreDirLister, qui reconnaît aussi .hidden,
  et transportent l’état caché réel. L’inventaire local des médias emploie les
  mêmes règles de noms exacts ; tri et peinture native ne le recalculent plus
  d’après le seul nom affiché. Les changements de .hidden sont incrémentaux.
- Une même résolution de libellé alimente fenêtre et onglet, avec le modèle
  d’Emplacements KDE natif. Icônes d’onglets fournies par KIO/le thème.
- Options persistantes de barre d’onglets toujours visible et de boutons de
  fermeture. Les titres automatiques gardent la limite de 40 caractères de
  Dolphin ; les noms personnalisés ne sont plus réduits à cette limite.
- Validation : construction complète des assistants natifs, contrôle réel
  du lister KIO et du pont d’Emplacements, nouveaux scénarios Qt de fermeture,
  visibilité, réglages et libellés. Résultats dans VALIDATION-RC177.md.
- Licence de la distribution combinée explicitée sous GPL-3.0-or-later ; les
  droits MIT du code original sont conservés. Adaptations d’onglets et de
  libellés sous GPL-2.0-or-later avec auteurs/provenance ; textes installés.
- L’état occupé et le lecteur d’un panneau sont enregistrés dès le démarrage,
  avant son premier résultat ; les observateurs ne voient plus un panneau libre
  pendant cette courte fenêtre.
- Métadonnées de version pyproject.toml alignées sur la version livrée.

## 1.0.0-rc176 — 23 octobre 2026

- Correction des onglets scindés restaurés en arrière-plan : les deux panneaux
  chargent leur contenu lors de la première activation, sans lancer les lecteurs
  des onglets encore masqués.
- Conservation des proportions de séparation pendant la construction des autres
  onglets et avant le premier affichage de la fenêtre. Les dimensions transitoires
  de cette construction ne remplacent plus les proportions mémorisées.
- Un onglet fermé avant sa première activation rouvre son dossier demandé, et non
  le dossier personnel. Le nom personnalisé est conservé dans l’historique et lors
  de la réouverture, comme dans l’état d’onglet sauvegardé par Dolphin.
- Si seul le panneau droit est conservé, fermer puis rouvrir l’onglet conserve ce
  dossier ; l’ancien panneau gauche masqué ne prend plus sa place.
- Une sélection externe destinée à un onglet non encore chargé reste en attente
  jusqu’à son inventaire, y compris dans le panneau droit d’un onglet restauré.
- Dix tests Qt supplémentaires : cinq défauts reproduits sur la RC175, puis
  contrôle de leurs corrections et des variantes de démarrage et de panneau droit.
  Les composants C++ sont inchangés par rapport à la RC175.
- Correction du type Python associé au viewport natif : QWidget remplace un
  downcast incorrect vers QAbstractScrollArea. Un test confronte le type Python
  au type Qt réel pour éviter les erreurs intermittentes de réutilisation d’objets.
- Le contrôle d’intégrité de la disposition des colonnes utilise désormais un
  profil personnalisé fixe ; les tailles d’un profil automatique sont transitoires.

## 1.0.0-rc175 — 23 octobre 2026

- Politique de style de vue commune ou propre à chaque dossier pour le mode,
  le tri, les miniatures, les éléments cachés et les informations sous les icônes.
  Les anciennes exceptions restent conservées ; les tailles d’icônes restent
  partagées par mode. Les profils médias ne sont pas supprimés.
- Styles natifs pour Récents et Corbeille ; défaut Téléchargements en mode par
  dossier, comme Dolphin. Les dates d’accès et de suppression et l’emplacement
  d’origine proviennent des informations KIO. Groupement chronologique assuré
  par l’algorithme de Dolphin 26.08.2, avec cache dans le moteur C++.
- Position des nouveaux onglets après le courant, Ctrl+T à la fin, option pour
  toujours les ajouter à la fin ; retour à l’onglet précédemment consulté.
- Clic du milieu pour fermer, double-clic pour ouvrir, menu contextuel,
  renommage persistant, titres adaptés aux deux panneaux et détachement.
- Restauration des onglets, des panneaux scindés, du panneau actif, des proportions
  et des noms personnalisés ; les emplacements explicitement demandés priment.
  Nouvelle installation : restauration de session. Choix existants conservés.
- Confirmation à trois choix lorsque la restauration est désactivée : fermer la
  fenêtre, fermer l’onglet courant ou annuler.
- Chaque fenêtre, y compris --new-window, s’enregistre sur le bus de session.
  Les dossiers déjà ouverts sont recherchés dans toutes les fenêtres ; les
  dossiers manquants d’une même demande sont regroupés dans une seule fenêtre.
- Jeton d’activation transmis depuis FileManager1, les demandes d’instance et
  l’environnement à KWindowSystem ; identifiant de démarrage transmis sur X11.
- Options --split et --select traitées par le vrai point d’entrée de l’application,
  avec sélection rattachée au bon panneau, y compris pour un dossier.
- Trois tris comme Dolphin : naturel, alphabétique sensible/insensible à la casse ;
  option de placement des éléments cachés en dernier, avant la séparation des
  dossiers et fichiers, dans les deux sens de tri.
- Migration des en-têtes : les nouvelles colonnes n’apparaissent pas de force.
  Les vues spéciales ne remplacent pas la disposition des colonnes médias.
- Tests supplémentaires de l’interface, des vrais lancements et du routage entre
  processus Qt sur un bus D-Bus temporaire isolé. Garde de validation portée à
  300 s avec progression régulière, compte tenu de la suite élargie.

## 1.0.0-rc174 — 23 octobre 2026

- Tri commun conservé pendant la navigation par défaut, y compris après relance ;
  option explicite pour retrouver le tri propre à chaque dossier. Les anciennes
  préférences par dossier sont conservées.
- Comparateur naturel de Dolphin 26.08.2 exécuté en C++ : collation de la langue,
  comparaison du nom sans extension puis de l’extension, décimaux et versions.
- Les égalités de taille, durée, date et autres critères sont départagées par nom
  puis par chemin, dans les deux sens de tri.
- Sur une nouvelle installation, les dossiers externes s’ouvrent en fenêtres comme
  dans Dolphin 26.08.2. Le choix des installations existantes est conservé.
- Les demandes externes réutilisent une vue déjà ouverte, y compris l’autre panneau
  d’un onglet scindé ; les fichiers demandés sont sélectionnés sans rechargement.
- Plusieurs dossiers et fichiers provenant de plusieurs dossiers sont tous traités,
  au démarrage, par le canal d’instance et par FileManager1.
- Le rappel d’une fenêtre conserve son état agrandi, même après minimisation.
- Dans les vues de fichiers, le clic du milieu ouvre un dossier en arrière-plan ;
  Maj active le nouvel onglet, conformément à Dolphin.
- Tests automatiques de navigation et de tri avec réglages isolés.

## 1.0.0-rc173 — progression native et annulation par opération

- Retire la barre de copie interne et le détournement du bouton Arrêter le chargement par les transferts KIO. KDE/Plasma reste responsable des pourcentages et des commandes natives de pause, reprise et annulation.
- Enregistre séparément les opérations KIO dans la fenêtre Opérations, avec leur état, leurs sources et destination, sans répliquer leurs pourcentages. L’indicateur d’activité couvre ces opérations, y compris lorsque le panneau Emplacements est masqué ; l’historique reste accessible à la fin.
- Arrête uniquement l’opération sélectionnée, ou toutes les opérations sur demande explicite. Protège les transferts lors de l’arrêt des autres tâches de fermeture et attend leur terminaison si l’utilisateur choisit de les arrêter et quitter. Une annulation ne déclenche pas la suite d’opérations prévue après un succès.
- Annule immédiatement une demande encore en attente du service sans lancer son opération. Reconnaît les retours d’annulation de KDE pour tous les types d’opérations. Retire le délai d’exécution arbitraire de cinq minutes des transferts ; la détection de fermeture du service et le délai de réponse à une annulation restent actifs.
- Conserve les valeurs de Durée connues pendant les analyses, au lieu de les remplacer par En attente ou En cours. L’avancement reste disponible dans Opérations et son indicateur dédié. Retire l’ancien mécanisme de substitution des cellules et met à jour le test qui l’exigeait.
- Vérifications détaillées dans PROGRESSION.md ; aucun nouvel essai manuel demandé. Les tests graphiques utilisent les vues natives compilées et un transport contrôlé, sans session Plasma réelle.
- Suite complète : 427 tests réussis, aucun échec ni test ignoré. Compilation complète des assistants C++ réussie. Valider-RC173.sh réussit aussi après compilation neuve avec le style Union.

## 1.0.0-rc172 — corrections des trois défauts de l’audit

- Reconnaît le focus du véritable KItemListContainer et de ses descendants. Tab et Maj+Tab activent le panneau correspondant avant les commandes, sans reprendre le focus au champ ou à l’éditeur qui vient de le recevoir.
- Rattache chaque modèle de renommage à son panneau lors de sa création. La validation différée de l’éditeur reste appliquée au bon fichier, même si l’autre panneau est devenu actif ou est en cours de chargement. Les rappels de miniatures et de lecture du dossier restent aussi rattachés au panneau d’origine ; la sélection active de l’autre panneau n’est pas détournée.
- Filtre les noms à partir du nom affiché, comme le tri naturel, plutôt qu’à partir de Path.name. Les URL KIO, noms Unicode et chemins locaux suivent le même filtre, sans accès disque ajouté.
- Ajoute huit tests fonctionnels Qt couvrant les trois vues, les deux panneaux, les renommages réels de fichiers et de dossiers, leur annulation et les données d’inventaire KIO. Les serveurs distants et le service KIO réel ne sont pas lancés par ces tests hors écran.
- Suite complète : 412 tests réussis, aucun échec ni test ignoré ; Valider-RC172.sh réussit également après compilation neuve et avec le style Union. La validation utilise les bibliothèques natives compilées ; les connexions distantes et les opérations KIO de bureau restent contrôlées séparément par la procédure d’installation.

## 1.0.0-rc171 — double-clic sur les en-têtes et miniatures persistantes

- Distingue l’en-tête graphique natif d’un vrai espace vide avant de traiter la remontée au parent. Le titre reste triable et le double-clic sur une poignée ajuste la largeur par le code de Dolphin. Aucun remplacement du dessin ou des interactions KDE.
- Enregistre le choix explicite des miniatures dans view/previews, en plus du choix du dossier courant. Les dossiers sans choix particulier héritent de cette valeur, y compris au prochain lancement. Les exceptions déjà mémorisées par dossier sont conservées ; leur restauration ne modifie pas la valeur par défaut.
- Ajoute des tests d’interactions Qt sur les titres, les séparations et le fond des trois vues, ainsi que sur le bouton des miniatures, la navigation, les exceptions et la réouverture.
- Suite complète : 404 tests réussis, aucun échec ni test ignoré ; également réussie avec Union. Les essais exécutent les vues natives compilées hors écran ; ils ne remplacent pas le contrôle du service KIO dans la session d’installation.

## 1.0.0-rc170 — dépôts entre panneaux et affichage après un dépôt natif

- Corrige le refus du fond des vues par l’adaptateur du modèle natif : le contrôleur de Dolphin doit pouvoir accepter supportsDropping(-1). Les dossiers vides et les zones libres des trois vues redeviennent des destinations de dépôt.
- Remplace le retour des dépôts Emplacements et fils d’Ariane par une synchronisation des deux panneaux, source active comprise. Conserve les différences en attente lors d’une reconfiguration des surveillances et retire aussi les sources disparues avant l’enregistrement de leur arrivée. Aucune réinitialisation des modèles locaux.
- Met à jour et sélectionne les liens créés sans recharger les vues. Conserve les URL KIO dans la sélection, les fichiers associés et le presse-papiers ; le collage distant vérifie le service permanent utilisé.
- Ajoute des essais fonctionnels Qt des transferts entre les neuf couples de vues, des raccourcis, menus, liens, sous-dossiers, sélections multiples et retours natifs. Renforce l’ancien test de dépôt pour vérifier DragMove. Détails et limites du transport simulé dans TRANSFERTS.md.
- Suite complète : 400 tests réussis, aucun échec ni test ignoré ; vérification supplémentaire avec Union. Validation par Valider-RC170.sh réussie. Le service KIO réel reste contrôlé sur la machine d’installation.

## 1.0.0-rc169 — fonds des vues et cadres natifs avec Union et Brise

- Compare la documentation officielle d’Union et ses sources Qt Widgets aux conteneurs et palettes de Dolphin 26.08.2. L’analyse et les liens sont dans UNION.md.
- Donne au conteneur des fils d’Ariane la même ascendance QFrame que dans Dolphin ; le cadre absent sous Union est dessiné par KUrlNavigator et le style natif. Aucun dessin ou couleur de bordure n’est imposé.
- Conserve le cadre natif du KItemListContainer et reprend DolphinView::updatePalette sur son véritable QGraphicsView : fond KDE View et opacité du panneau inactif. Les palettes des façades et la désactivation des bandes du panneau inactif sont retirées.
- Vérifie le rendu natif avec les plugins Brise et Union, des configurations claires et sombres, les trois vues, l’activation, la saisie et les changements de palette. Conserve les personnalisations et les raccourcis de la RC168. Aucun nouveau paquet obligatoire.
- Suite complète : 391 tests réussis, aucun échec ni test ignoré ; nouvelle exécution réussie avec Union chargé pour l’interface. Compilation complète Qt/KF6 réussie, hors session Plasma. Aucun nouvel essai manuel demandé.

## 1.0.0-rc168 — raccourcis des vues et conventions KDE/Dolphin

- Corrige 30 raccourcis inactifs avec la barre de menus masquée : les actions sont enregistrées sur la fenêtre. Toutes les vues et les deux panneaux partagent le même registre.
- Lit les raccourcis standard et leurs variantes avec KStandardShortcut, en conservant la priorité des personnalisations de Mirivue. Surveille les changements KDE et détecte aussi les conflits avec les variantes secondaires.
- Aligne les transferts sur Maj+F5/Maj+F6 ; complète les accès aux onglets, miniatures, chemins, autre panneau et configuration. F10 reste le menu, Ctrl+Maj+N reste Nouveau dossier.
- Distingue Maj+F4 (terminal dans le dossier courant) et Maj+Alt+F4 (emplacements sélectionnés). KTerminalLauncherJob utilise le terminal choisi dans KDE.
- Corrige Retour arrière dans les vues natives et Échap après la saisie d’un chemin. Ctrl+I rappelle le filtre sans le fermer. Retire l’ancien contournement global de F2 ; les éditeurs gardent leurs commandes de texte.
- L’aide reprend les combinaisons réelles. Le menu de création et le terminal contextuel réutilisent les actions enregistrées, sans second raccourci concurrent.
- Ajoute 16 tests fonctionnels, dont une matrice de 960 combinaisons. Suite complète : 385 tests réussis, aucun échec ni test ignoré. Compilation complète Qt/KF6 et contrôle supplémentaire des touches sur le vrai KUrlNavigator. Détails et limites dans RACCOURCIS.md.

## 1.0.0-rc167 — Ctrl+A avec la barre de menus masquée

- Rattache explicitement l’action Tout sélectionner à la fenêtre, en plus du menu Édition. Son raccourci ne dépend plus de la visibilité de la barre de menus.
- Conserve la sélection limitée aux éléments affichés du panneau actif. Les champs de chemin, de filtre et de recherche, ainsi que l’éditeur de renommage KDE, gardent leur sélection de texte native.
- Six tests Qt envoient de vraies touches au moteur natif : trois vues avec menus affichés/masqués, deux panneaux indépendants, filtre, champs de saisie, renommage F2 et chargement réel d’un dossier jetable. La suite complète réussit : 369 tests, sans échec ni test ignoré, hors écran.

## 1.0.0-rc166 — palette et cadre natifs des fils d’Ariane

- Retire la substitution d’AlternateBase par Base et la palette explicite propre aux navigateurs. Les rôles de couleurs héritent du thème KDE et de la barre d’outils, comme dans le navigateur de Dolphin.
- Actualise la hauteur fixée à la construction par KUrlNavigator lorsque la police, le style ou les métriques de l’éditeur changent. Le calcul utilise les dimensions du style Qt/KDE ; aucune hauteur ni couleur n’est imposée. Cela évite le repli de Breeze vers un rectangle sans cadre lorsqu’il manque de la hauteur.
- Le fond, les arrondis, les bordures et la saisie restent entièrement dessinés par KUrlNavigator et Breeze. Le panneau actif garde le texte natif accentué et le contour neutre demandé ; le focus de saisie reste celui de KDE. Aucun calcul de hauteur n’est ajouté au glissement du séparateur.
- Ajoute un exécutable de contrôle compilant la même fabrique que l’application et cinq tests de fonctionnement : palettes claire/sombre, agrandissement et réduction de police, changement de style, focus de saisie et activation du panneau. Les pixels du cadre sont comparés à ceux d’un KUrlNavigator standard avec les mêmes états ; les contrôles de palette et de saisie comparent aussi le contenu.

## 1.0.0-rc165 — noms sans couleur et retrait de la colonne État

- Retire la colonne État des vues, menus d’en-têtes et configurations de colonnes. Les anciens profils et états d’en-têtes ne peuvent pas la réafficher ; les identifiants internes sont conservés pour reprendre les préférences sans décaler les autres colonnes.
- Les noms et informations de fichiers utilisent le texte normal du thème Qt/KDE, sans coloration selon une analyse, une erreur, un doublon ou une étiquette personnelle. Les couleurs de sélection, de focus et des icônes du thème restent natives.
- Les informations utiles de lecture, erreurs, doublons et étiquettes sont conservées dans les infobulles et les rapports d’opérations. Aucune analyse ni donnée personnelle n’est supprimée.
- Corrige la vérification des fichiers audio : ni résolution d’image ni fréquence vidéo attendues ; le codec et le débit sont lus dans les champs audio. Les vidéos gardent leurs critères vidéo et les images leurs dimensions.
- Quatre tests de fonctionnement supplémentaires couvrent les types de médias, les textes sans couleur, les infobulles et les anciennes configurations des deux panneaux.

## 1.0.0-rc164 — commandes, réglages et organisation de l’interface

- Accès directs dans Outils à Renommer et organiser, Métadonnées, Collections et Opérations. F2 conserve la modification directe ou l’outil configuré pour une sélection multiple ; Renommage avancé ouvre explicitement l’outil intégré. Le logiciel externe est identifié par son nom. Le renommage à partir des métadonnées utilise désormais le même aperçu et les mêmes contrôles de conflits.
- Une seule fenêtre non modale pour les transferts et analyses, avec deux onglets et des commandes d’arrêt distinctes. Les commandes sans objet sont désactivées. Les outils de métadonnées sont réservés aux médias compatibles.
- Informations sous les icônes et Colonnes de la vue détaillée sont présentées selon la vue active. Configurations de colonnes a une portée explicite ; les champs communs ne sont plus répétés dans plusieurs catégories. Le résumé respecte les fichiers réellement affichés après filtrage.
- Barre d’outils initiale allégée, modes de vue dans un sélecteur commun et navigation Précédent/Suivant/Parent. Les commandes individuelles restent configurables et les dispositions personnelles existantes sont conservées. Ajoute Nouvelle fenêtre (Ctrl+N). Les collections suivent l’activation Qt/KDE.
- Général regroupe démarrage, fermeture, navigation et confidentialité ; toutes les pages sont défilables. La recherche des réglages montre les correspondances et un état sans résultat. Corrige les libellés des fichiers récents, composants nécessaires, formats de colonnes et pas de lecture/volume.
- Le choix du panneau d’aperçu au démarrage n’ouvre ou ne ferme plus le panneau courant lors d’Appliquer. L’infobulle des miniatures décrit les trois vues. Le type de recherche n’est plus dupliqué dans les critères de métadonnées.
- L’historique de lecture sans commande de consultation n’est plus proposé ni alimenté ; les données déjà enregistrées restent conservées. Les fichiers récents, les collections, les étiquettes, les outils médias et les préférences existantes restent disponibles.
- Tests d’interaction Qt : états des actions, hiérarchie, vue active, fenêtres, conservation des préférences, aperçu de renommage, fenêtre des opérations, résumé filtré et historique retiré.

## 1.0.0-rc163 — moteur de vues de Dolphin

- Remplace les vues QTableView/QListView par KItemListContainer, KStandardItemListView/KItemListView et KStandardItemListWidget issus de Dolphin 26.08.2. Un seul moteur par panneau assure les modes détails, icônes et compact, leurs objets de dessin conservant QStaticText et les pixmaps.
- L’adaptateur garde les modèles, tris, filtres, outils de médias et opérations KIO de Mirivue. Les notifications d’insertions, suppressions, réordonnancements et changements de rôles mettent à jour les éléments sans réinventorier le dossier. Les icônes ne sont préparées que pour les éléments dessinés.
- L’en-tête KDE assure le dessin, le redimensionnement, le tri et le déplacement des colonnes. Le format de préférences existant est conservé par un contrôle caché, avec les choix de largeur automatique/personnalisée et de remplissage.
- L’éditeur KDE sélectionne le nom sans l’extension ; Tab valide puis passe au fichier suivant. Sélection après transfert, menus, informations supplémentaires, miniatures, couleurs sémantiques et autorisations d’édition sont reliés au moteur natif.
- Un masque d’événements C++ évite les appels globaux aux filtres Python pour les événements de dessin et de disposition. Les interactions utiles continuent d’être traitées par les contrôleurs existants.
- Les sources KDE et leurs licences sont incluses et épinglées ; aucune dépendance à l’ABI privée du paquet Dolphin. Le paquet et l’installateur utilisateur compilent et installent le nouveau moteur, devenu requis.
- Compilation CMake du moteur réussie ; 339 tests réussis sans test ignoré. Le banc hors écran confirme zéro appel au modèle Python pendant le glissement, mais ne montre pas de gain net de temps sur la RC162. Détails et résultats dans ANALYSE-REACTIVITE.md. Aucun nouveau test manuel demandé pour cette correction.

## 1.0.0-rc162 — présentation native des fichiers et redimensionnement des colonnes

- La comparaison avec Dolphin 26.08.2 confirme que le séparateur est déjà un QSplitter dans les deux applications. Le coût propre à Mirivue vient surtout des demandes répétées au modèle Python pendant le dessin des cellules et des en-têtes. Une mémoire native Qt, limitée à 4 096 cellules, est placée entre le modèle de fichiers et le proxy de tri. Les tris, filtres, actions, données et opérations KIO restent dans leurs composants existants.
- Les changements de données invalident les cellules concernées avant notification du tri. Les insertions et suppressions conservent les cellules inchangées et les index persistants. Miniatures, options d’affichage, palette et police notifient leurs changements ; l’autorisation d’éditer le nom reste consultée en direct.
- L’en-tête natif ajuste la colonne Nom à partir de sa largeur déjà mesurée, comme l’algorithme de Dolphin, plutôt que d’étirer la dernière colonne de métadonnées. Un redimensionnement automatique ne déclenche plus la sauvegarde des largeurs personnalisées.
- Le nouveau module utilise les dépendances Qt existantes. Il est compilé par les deux installateurs et contrôlé après installation. La validation compile aussi ce module dans un dossier temporaire afin de tester le chemin natif réel.
- Contrôles exécutés : compilation du module C++, 329 tests réussis sans test ignoré, syntaxe Python et shell. Le banc automatisé hors écran mesure environ 9,5 ms par déplacement avec six colonnes activées et 9,8 ms avec 38, contre 21,6 et 22,3 ms pour la RC160. Il ne mesure pas la présentation finale par KWin. Voir ANALYSE-REACTIVITE.md.

## 1.0.0-rc161 — redessin de la vue détaillée

- Le délégué de la vue Détails laisse Qt préparer les cellules pendant un redimensionnement ; le délégué des vues icônes et compacte conserve les informations supplémentaires sous les noms. Le comportement de F2 reste commun aux vues.
- Le modèle ignore plus tôt les rôles de données qu’il ne fournit pas et évite de consulter l’état des opérations pour les colonnes sans indicateur. Cette modification répond au profil réel de la vue Détails, qui montre encore de nombreux appels au modèle après la correction des tailles de dossiers de la RC160.
- La fluidité doit être mesurée sur la machine Plasma avec les réglages et le dossier habituels. Le diagnostic de cette version refuse désormais un chemin de dossier inexistant au lieu de mesurer silencieusement le dossier personnel.

### Complément — coût de la vue détaillée pendant le déplacement du séparateur

- Le profil sur la machine de référence a relevé 117 957 appels à `VideoModel.data()` et 3 655 appels au délégué de la colonne Nom pendant 12 secondes de glissement en vue détaillée. Le calcul de taille totale des dossiers a été écarté par une seconde mesure.
- `data()` lit la colonne une seule fois, écarte immédiatement les rôles Qt inutilisés et ne consulte l'état des opérations que dans les deux colonnes qui peuvent l'afficher.
- La vue détaillée conserve la sélection du nom sans l'extension lors de F2, mais laisse Qt préparer le dessin standard de cette colonne. Les vues icônes et compacte gardent leur délégué avec informations supplémentaires.
- La fluidité obtenue doit être mesurée sur la machine CachyOS avant de conclure ; aucun réglage personnel n'est remplacé.

## 1.0.0-rc160 — fond du fil d’Ariane et redessin des fichiers

- Le navigateur KDE utilise la couleur `Base` de la palette active pour son fond en mode boutons, comme son champ de saisie. Son cadre, ses segments survolés et le focus du champ restent dessinés par Breeze ; la palette est actualisée lors d’un changement de thème.
- Les icônes MIME sont conservées par ligne pendant le redessin de la vue détaillée, puis invalidées à la modification ou au retrait du fichier et au changement de thème. La recherche de l’état des tâches est évitée pour les colonnes sans état et lorsqu’aucune tâche n’existe.
- Ces changements visent le coût observé dans le profil du glissement ; la fluidité sur la machine CachyOS et l’aspect du cadre restent à confirmer sous Plasma.

## 1.0.0-rc159 — cadre neutre et redimensionnement des détails

- Le contour des deux fils d’Ariane garde la teinte normale de Breeze pendant la vue scindée ; l’indicateur de focus bleu n’est plus appliqué au cadre. Les commandes et les couleurs restent celles du composant KDE.
- Les changements de largeur ne programment plus une vérification de toutes les barres de défilement des vues, déjà configurées à leur création et lors d’un changement de mode. Les consultations de l’état des opérations sont limitées aux rôles du modèle qui en ont besoin.

## 1.0.0-rc158 — état du fil d’Ariane KDE et suivi immédiat du séparateur

- Reprend le conteneur transparent de Dolphin, sans marge ajoutée ni feuille de style sur la barre, et active `KUrlNavigator::setHighlightFocusIndicator` lorsque les vues sont scindées. Le dessin du cadre reste confié au style KDE.
- Le déplacement du séparateur aligne immédiatement les chemins sur les vues, sans attendre le minuteur de 16 ms. Un garde empêche une remise en page récursive.

## 1.0.0-rc157 — déplacement du séparateur plus fluide

- Le suivi du séparateur ne force plus une remise en page de la barre d’outils lorsque ses largeurs sont déjà correctes. Seuls les fils d’Ariane dont la largeur change sont réajustés ; le défilement du fil de secours n’est plus demandé pour les navigateurs KDE natifs.
- Conserve le cadre natif prévu en RC156.

## 1.0.0-rc156 — cadre natif du fil d’Ariane

- Le conteneur du navigateur KDE réserve au-dessus et en dessous l’épaisseur de cadre indiquée par le style Qt. Son fond et son arrondi restent peints par `KUrlNavigator` et le thème Plasma, comme dans Dolphin. La géométrie horizontale et les chemins des deux panneaux restent inchangés.

## 1.0.0-rc155 — validation graphique sans attente invisible

- Le test du menu d’historique désactive la confirmation de fermeture des onglets dans ses réglages isolés. En RC154, cette boîte modale hors écran immobilisait `Valider-RC154.sh` avant la construction du paquet.
- Le validateur affiche le dernier test lancé toutes les dix secondes si une validation tarde.

## 1.0.0-rc154 — présentation native du chemin et historique de navigation

- Le fil d’Ariane KDE est créé directement sous son conteneur de barre d’outils et son cadre natif est activé explicitement, comme dans Dolphin. Le contrôle graphique vérifie cet état ; l’apparence du cadre reste à comparer sous Plasma.
- Les boutons Précédent et Suivant proposent un menu déroulant construit à l’ouverture à partir de l’historique du panneau actif. Le clic principal garde la navigation d’un seul pas ; choisir une entrée va directement au dossier souhaité.
- Le sélecteur d’Emplacements continue de suivre F9, tel qu’introduit en RC152. Les choix enregistrés pour la barre d’outils et la taille des icônes sont conservés.

## 1.0.0-rc153 — contrôle du fil d’Ariane sous Wayland

- Le contrôle natif envoie Entrée directement à l’éditeur visible du `KUrlNavigator`. Il ne dépend plus du focus global de la fenêtre, que Wayland peut refuser pendant un lancement automatisé.
- Le fonctionnement du fil d’Ariane introduit en RC152 reste identique.

## 1.0.0-rc152 — fil d’Ariane natif synchronisé avec les panneaux

- Le sélecteur d’Emplacements du `KUrlNavigator` est visible seulement lorsque le panneau Emplacements est masqué. Le réglage est appliqué aux deux vues et aux onglets réactivés.
- Les sous-dossiers cachés proposés dans les flèches suivent Ctrl+H et le réglage mémorisé pour chaque dossier et panneau. Le tri propre à KIO reste à son défaut.
- La validation d’un chemin avec Entrée revient aux boutons du fil d’Ariane après acceptation de l’adresse. Mirivue ne propose pas de mode « barre toujours modifiable ».
- Le contrôle natif après installation vérifie les deux états du sélecteur ainsi que les dossiers cachés dans des vues scindées.

## 1.0.0-rc151 — suivi de sauvegarde utilisable après remontage

- Le fichier de suivi créé par cette version compare la taille, la date et une empreinte SHA-256 de trois zones du contenu. Les identifiants de montage et d’inode restent utilisés à l’intérieur de la vérification d’une lecture, mais ne sont plus enregistrés comme identité persistante. L’empreinte est partielle et ne garantit pas l’identité de tous les octets.
- Une fiche de la RC150 est migrée automatiquement seulement si les anciens identifiants du média et de l’original correspondent encore. Sinon, Mirivue conserve les deux fichiers et explique comment repartir explicitement sans adopter une sauvegarde à partir de la seule taille et date.
- La procédure de récupération précise que renommer ou déplacer un média laisse l’original et le suivi à l’ancien emplacement. Des essais simulés couvrent le remontage, la migration sûre et le refus de la migration ambiguë ; les essais réels exFAT et Btrfs restent requis.

## 1.0.0-rc150 — un original identifiable pour les modifications de métadonnées

- Les écritures des balises et du débit utilisent une politique commune : le premier original est conservé dans `nom.mirivue-original` et les modifications suivantes le réutilisent. Un petit fichier caché relie la sauvegarde au fichier courant ; en cas de correspondance incertaine, la nouvelle modification est refusée sans effacer de données.
- Quand le système de fichiers ne permet pas les liens matériels, une copie vérifiée prend le relais après contrôle de l’espace disponible. Les anciennes sauvegardes des RC précédentes sont signalées et conservées.
- Si un montage refuse la synchronisation d’un dossier, l’incident est journalisé sans présenter comme échouée une écriture déjà effectuée. La durabilité en cas de coupure brutale est alors réduite ; ce cas doit être vérifié sur le support concerné.
- Le résultat indique le chemin d’un original unique et la procédure de récupération décrit les fichiers. L’argument `delete_backup` et les libellés de l’option sans effet sont retirés.
- Des tests couvrent les modifications répétées par les deux voies, le changement de fichier sous le même nom, les liens matériels refusés et une copie de sauvegarde interrompue.

## 1.0.0-rc149 — fermeture depuis un aperçu plein écran

- À la fermeture pendant un aperçu en plein écran, la fenêtre conserve la géométrie et l’état agrandi qu’elle avait avant l’aperçu. La prochaine ouverture ne reprend plus le plein écran sans aperçu.
- Un contrôle Qt reproduit l’entrée en plein écran puis la sauvegarde et la restauration de la fenêtre.

## 1.0.0-rc148 — couleurs et formats du bureau, géométrie de la fenêtre

- Les états des fichiers emploient les rôles positifs, neutres, négatifs et de lien de KColorScheme plutôt que des codes de couleur fixes. Les doublons et les étiquettes personnelles restent explicitement nommés dans « État » ; leur valeur sauvegardée est conservée.
- Les tailles de fichiers passent par KFormat et respectent le choix d’unités du bureau. Les débits gardent leurs unités en bits/s. Le format régional Qt devient le défaut des dates pour les nouveaux réglages ; les préférences « Relatif » et « ISO » enregistrées restent applicables.
- La fenêtre principale mémorise taille et état agrandi, avec une taille initiale limitée à l’écran. L’aide décrit le clic choisi dans KDE et précise que le double clic dans le vide est une option.
- Le message de dossier vide utilise la police de la vue. Les commandes de lecture plein écran ne fixent plus la taille de leur texte en pixels et leur hauteur suit le contenu ; le fond sombre de la vidéo est conservé.
- `kcolorscheme` et `kcoreaddons` sont déclarés comme dépendances directes du paquet ; la vérification après installation interroge réellement les deux fonctions natives.

## 1.0.0-rc147 — service KIO, chemins avec deux-points et fermeture

- La validation après installation envoie une requête de corbeille à `mirivue-kio-service`, le service utilisé en priorité par l'interface et fondé sur `KIO::DeleteOrTrashJob`. Un fichier et une corbeille jetables sont isolés ; le contrôle expire si une confirmation invisible bloque l'opération. La solution de secours `mirivue-kio-transfer` reste disponible.
- Les dossiers existants dont le nom contient deux-points sont traités comme chemins locaux avant d'interpréter une adresse KIO, dans `Lancer.sh` et dans l'analyse Python des arguments.
- Les fenêtres de configuration et de raccourcis sont non modales et réutilisées. La fermeture de Mirivue depuis le dock peut fermer la fenêtre principale et ses dialogues enfants ; les modifications non appliquées sont abandonnées. Le contrôle graphique exerce cette situation.
- La procédure de désinstallation et sa portée par compte utilisateur sont indiquées dans le document d'accueil.

## 1.0.0-rc146 — centrage réel des libellés de configuration

- Le contrôle de la RC145 portait sur une option du délégué Qt, mais Qt continuait à dessiner les libellés à gauche. Le délégué dessine désormais lui-même l'icône puis le texte avec `QTextLayout` centré, selon le calcul de `KPageListViewDelegate` de KDE. La largeur et le retour à la ligne utilisent le même calcul ; l'état sélectionné et le focus conservent la palette et le style Plasma.
- Le contrôle graphique vérifie que la disposition du texte utilisée pour le dessin est centrée.

## 1.0.0-rc145 — configuration plus lisible

- La navigation des paramètres reprend la graisse forte de KPageListView et centre réellement les libellés sous les icônes. Le contrôle graphique vérifie les deux propriétés.
- La fenêtre s'ouvre plus large, le choix du dossier de démarrage et le bouton de sélection occupent chacun une ligne, et trois libellés longs sont raccourcis. Leurs explications restent dans les infobulles ; les valeurs et les clés des réglages sont conservées.

## 1.0.0-rc144 — contrôle graphique corrigé

- Le contrôle graphique attend désormais l'absence du choix de langue retiré en RC143. La RC143 échouait à la validation avant la construction du paquet parce que ce contrôle référençait encore le widget supprimé. Aucun comportement utilisateur n'est modifié par cette correction.

## 1.0.0-rc143 — lancement, langue et vérification KIO

- Le lanceur conserve le dossier de travail de l'appelant pour ouvrir les chemins relatifs, y compris les noms contenant des espaces ; les URL restent inchangées.
- Pendant la stabilisation 1.0, l'interface reste en français et le réglage de langue inachevé est masqué. `tr()` ne transforme plus de clés techniques ou d'arguments, et aucun `QSettings` commun n'est consulté depuis les tâches de fond. Les brouillons anglais sont conservés hors de la voie d'exécution en attendant un catalogue relu.
- Le contrôle après installation met effectivement un fichier jetable à la corbeille par KIO, avec un répertoire de données temporaire isolé. Il exige que l'assistant confirme le succès, que la source disparaisse et que la corbeille de test contienne le fichier.
- Une procédure de désinstallation du paquet retire, pour le compte qui l'exécute, uniquement le service FileManager1 marqué et pointant vers Mirivue. `qt6-webengine` reste requis pour QtPdf.
- L'ancienne voie Python de copie/déplacement n'est pas retirée à ce stade : ses méthodes partagent encore l'interface de suivi et leur extraction demande une validation sous Plasma. La suppression active continue à passer par KIO.

## 1.0.0-rc142 — nettoyage des anciennes voies de suppression

- La voie de suppression Python qui n’était plus appelée et son import ont été retirés. La protection contre la suppression d’une racine de partition est placée avant le travail KIO utilisé par l’interface ; les fichiers contenus dans cette partition restent sélectionnables.
- Le constructeur d’archive RAR pour les contrôles isolés utilise maintenant `zlib.crc32` ; un test vérifie les CRC de l’en-tête et du contenu sans remplacer le constructeur par une simulation.
- Un ancien bouton de colonnes jamais affiché, une méthode de palette sans appel et deux correspondances de dépendances GIO/GVfs sans demandeur ont été retirés. Les migrations qui lisent encore des réglages ou des métadonnées d’anciennes versions sont conservées.
- Le document d’accueil décrit désormais la version courante et renvoie à cet historique.

## 1.0.0-rc141 — mémoire des aperçus et rendu PDF

- Les images décodées gardées pour les aperçus ont une limite commune de 256 Mio et sont évincées selon leur dernière utilisation. L’image actuellement affichée reste visible ; elle est recalculée si elle a quitté le cache. Masquer le panneau libère ses images.
- Le rendu d’une page PDF ne bloque plus le fil de l’interface. Les résultats d’un fichier, d’une page ou d’une taille devenus obsolètes ne remplacent pas l’aperçu courant ; les changements de page pendant le chargement sont pris en compte.
- La fermeture demande l’arrêt du rendu PDF en cours et attend sa fin. Contrôler sous Plasma de grands PDF, les changements rapides de sélection et la fermeture pendant un rendu.

## 1.0.0-rc140 — tri naturel et compteurs des grands dossiers

- La clé du tri naturel est calculée au plus une fois par nom de ligne et recalculée si ce nom change. La même comparaison est conservée, y compris après renommage. Sur un essai Python isolé avec 20 000 noms et 260 000 comparaisons, ce calcul prend 1,08 s sans cache contre 0,47 s avec un cache porté par chaque ligne, construction comprise ; ces chiffres ne sont pas des temps d’affichage de Mirivue.
- Si aucun élément n’est filtré, le pied de panneau compte directement les lignes du modèle sans demander à Qt de convertir chaque index du proxy. Le parcours par proxy reste en place lorsque le filtre masque des lignes.
- Un test vérifie que le cache du tri est renouvelé après un changement de nom. Comparer l’ouverture, le tri et les transferts de gros dossiers sous Plasma avant de conclure sur le gain réel.

## 1.0.0-rc139 — test graphique des largeurs d’onglets corrigé

- Le test de la RC138 donnait deux largeurs à un séparateur contenant aussi les panneaux masqués des autres onglets. La seconde proportion n’était donc pas appliquée au bon endroit et l’essai échouait avec deux largeurs identiques.
- L’essai cible désormais les panneaux actifs par leur position réelle dans Qt et vérifie distinctement l’application de chaque proportion, le changement d’onglet, F3 et la réouverture. Le comportement de l’application reste celui de la RC137.

## 1.0.0-rc138 — validation hors écran débloquée

- Le nouveau test de largeurs par onglet ferme sa fenêtre avec deux onglets sans afficher la confirmation modale. En mode hors écran, cette confirmation attendait une réponse invisible et bloquait `Valider-RC137.sh` avant la construction du paquet.
- Le validateur indique désormais le début des tests et, en cas de blocage prolongé, s’arrête après trois minutes en affichant le dernier test lancé. Les fonctionnalités de la RC137 sont conservées.

## 1.0.0-rc137 — largeurs conservées entre les onglets et les lancements

- Chaque onglet garde la proportion de sa vue scindée quand on passe à un autre onglet, désactive puis réactive F3, ou rouvre un onglet fermé. Une modification encore en attente est conservée dès le changement d’onglet.
- La largeur du panneau Emplacements est enregistrée après un glissement et rétablie au lancement suivant. Masquer le panneau ne remplace pas cette valeur par zéro ; une fenêtre plus étroite limite la largeur rétablie pour laisser de la place aux fichiers.
- Les interactions Qt sont couvertes par deux nouveaux essais hors écran. Une comparaison manuelle sous Plasma reste prévue.

## 1.0.0-rc136 — glissement plus fluide des séparateurs

- L'alignement de la barre de chemin, auparavant recalculé immédiatement pour chaque signal `splitterMoved`, est regroupé par tranches de 16 ms pendant le glissement. Le recentrage du dossier courant dans le fil d'Ariane est également regroupé.
- Les tailles du séparateur entre vues sont enregistrées 200 ms après le dernier déplacement, et immédiatement à la fermeture si l'attente n'est pas terminée. Les vues continuent de se redimensionner pendant le glissement.
- Un test vérifie le regroupement des recalculs et l'enregistrement final. L'essai manuel doit comparer la fluidité avec Dolphin sur la même session Plasma.

## 1.0.0-rc135 — progression sans variation de largeur

- La RC134 n'a pas supprimé le mouvement signalé pendant les opérations. Le diagnostic précise que les séparateurs Emplacements/vues et vue gauche/vue droite se déplacent pendant la progression.
- Les trois barres de progression du panneau Emplacements ne contribuent plus à sa largeur minimale, même lorsque leur texte ou leur pourcentage change. Le libellé des tâches n'impose plus une largeur fixe de 150 pixels. Les séparateurs et les vues gardent leur largeur choisie.
- Un contrôle graphique mesure les deux séparateurs pendant une progression simulée de 1 à 100 %, y compris à l'apparition et à la disparition de l'indicateur. La vérification sous Plasma reste nécessaire car Qt et le thème déterminent la mise en page finale.

## 1.0.0-rc134 — largeur stable des panneaux pendant les opérations

- Les compteurs d'éléments et l'espace libre dans les pieds des vues n'imposent plus une largeur minimale dépendant du texte. Leur variation lors d'une copie, d'un déplacement ou d'une suppression ne doit plus déplacer le séparateur des panneaux ; les libellés trop longs sont tronqués visuellement et restent complets dans leur infobulle.
- Un essai graphique vérifie que le séparateur ne change pas de position lorsque les deux libellés passent de nombres courts à des nombres longs et inversement.

## 1.0.0-rc133 — suppression sans rechargement de la vue locale

- Après une suppression ou une mise à la corbeille KIO, les lignes des fichiers locaux effectivement disparus sont retirées séparément du modèle. La sélection des autres éléments et la position du panneau sont conservées, y compris lorsque deux panneaux affichent le même dossier.
- Une opération interrompue conserve les fichiers encore présents. Une vue de la Corbeille, un emplacement distant, une recherche ou un dossier en cours de lecture continue de demander une nouvelle liste ; un panneau ouvert sur un dossier supprimé revient à un parent existant.
- Des tests vérifient ces cas. Le contrôle manuel compare la suppression de lots et la conservation de la sélection avec Dolphin.

## 1.0.0-rc132 — propriétés d'affichage par dossier

- Le critère et le sens de tri sont conservés entre les lancements pour chaque dossier. L'affichage des éléments cachés, des miniatures et « dossiers d'abord » peut aussi différer d'un dossier à l'autre, et chaque panneau retrouve ses propres commandes en changeant de dossier.
- Le menu Affichage → Informations supplémentaires permet de montrer sous les noms, dans les vues Icônes et Compacte, la taille, la date, la durée, la résolution, le codec, l'artiste et l'album disponibles. Le choix est enregistré par dossier et la modification du nom avec F2 conserve seulement le vrai nom du fichier.
- Les réglages anciens restent les valeurs initiales des dossiers qui n'ont pas de style enregistré. L'option de masquage des fichiers cachés au démarrage garde la priorité au premier affichage.
- Le regroupement visuel et les dossiers dépliables sont reportés à la demande de l'utilisateur : ils nécessitent de revoir le modèle commun aux vues et aux opérations sans pouvoir vérifier les interactions Qt dans cet environnement.

## 1.0.0-rc131 — lecture progressive des durées après de nombreux transferts

- Une seule lecture de métadonnées à la fois par panneau ; les médias visibles sont traités en premier et les nouvelles arrivées visibles passent devant la file restante.
- Pour un lot de plus de huit médias, le cache Mirivue est utilisé directement et la lecture ciblée des en-têtes prend le relais. Le lancement préalable de `balooshow6` pour chaque fichier est évité. Les petites demandes conservent la consultation de Baloo ; aucune dépendance supplémentaire n'est requise.
- Les lignes sont actualisées séparément, sans rechargement ni perte de sélection. Un essai sous Plasma sur un gros transfert reste nécessaire avant publication stable.

## 1.0.0-rc130 — durée des médias après un transfert

- L’arrivée locale d’un fichier vidéo ou audio lance la même lecture ciblée des métadonnées que l’ajout d’un fichier dans la vue : consultation de Baloo, puis lecture du média en arrière-plan si nécessaire. Seule la ligne concernée est actualisée.
- Une notification ultérieure du dossier conserve la durée déjà lue lorsque le fichier n’a pas changé.

## 1.0.0-rc129 — sélection après transfert entre panneaux

- Après une copie ou un déplacement KIO local sans conflit, seules les lignes transférées sont ajoutées ou retirées ; les fichiers arrivés restent sélectionnés dans le panneau de destination.
- Les emplacements distants, les vues récursives et les conflits de noms conservent un rechargement de sécurité suivi d’une restauration de la sélection.
- La sélection couvre les différentes vues et les destinations nommées explicitement ; aucun fichier n’est sélectionné lors d’un transfert échoué ou annulé.

## 1.0.0-rc128 — test de renommage dans les trois vues

- Chaque vue du contrôle F2 utilise un modèle distinct : le changement de nom réalisé dans la première ne modifie plus le fichier attendu dans les suivantes.
- Le comportement de renommage de la RC127 reste identique.

## 1.0.0-rc127 — sélection F2 après le focus de Qt

- Corrige la RC126 : Qt pouvait sélectionner à nouveau le nom entier après l’ouverture du champ. La sélection est rétablie après le focus, avant la saisie.
- La longueur du nom suit la règle de Dolphin : extension reconnue par la base MIME de Qt (y compris `tar.gz`), sinon partie suivant le dernier point ; dossiers et noms cachés sans autre point sont entièrement sélectionnés.
- Le contrôle graphique ouvre réellement l’éditeur dans les trois vues et vérifie la sélection après traitement des événements Qt.

## 1.0.0-rc126 — sélection du nom lors du renommage F2

- Dans les trois vues et les panneaux scindés, F2 sélectionne le nom avant la dernière extension pour un fichier. L’extension reste visible et modifiable à la main ; les dossiers et les fichiers sans extension gardent leur nom entièrement sélectionné.
- Le renommage en masse et les autres outils de renommage restent inchangés.

## 1.0.0-rc125 — largeur des commandes sans Emplacements

- Le groupe de navigation conserve sa largeur naturelle lorsque le panneau Emplacements est masqué : le ressort interne ne crée plus de vide devant le fil d’Ariane.
- Le contrôle graphique vérifie la largeur et la position du chemin en vue simple et scindée, puis l’alignement après réaffichage d’Emplacements.

## 1.0.0-rc124 — boutons de navigation avec Emplacements masqué

- La barre d’outils retrouve sa largeur naturelle quand le panneau Emplacements est masqué ; Menu, Dossier personnel, Parent, Précédent, Suivant et Actualiser restent accessibles.
- Le contrôle graphique masque Emplacements, vérifie que Précédent reste visible, puis le réaffiche et contrôle à nouveau l’alignement.

## 1.0.0-rc123 — fil d’Ariane, colonnes et retours dans la vue

- Le fil d’Ariane garde le dossier courant visible après la mise en page et les changements de largeur, y compris en vue scindée. La barre horizontale reste masquée.
- Le chargement ne réactive plus « Extension suggérée » lorsque les réglages historiques `columns-v4` sont absents. Les colonnes personnalisées déjà enregistrées restent telles quelles.
- Une installation neuve conserve ses quatre colonnes initiales ; « Médiathèque » et les autres profils restent accessibles à la demande.
- Avec Emplacements masqué, le message temporaire occupe la ligne de résumé existante dans le panneau actif puis le résumé revient. L’infobulle conserve le message complet, sans changement de hauteur de la vue.

## 1.0.0-rc122 — validation de la RC121

- Actualise deux tests qui supposaient qu'aucune barre d'état ne pouvait être utilisée, alors que la barre discrète de secours est désormais nécessaire lorsque Emplacements est masqué.
- Corrige l'appel de formatage des tailles en octets à `QLocale.toString` pour respecter la surcharge entière de PySide6 et ajoute un contrôle des nombres français et anglais.
- En cas d'échec, le script de validation résume les noms des tests et les exceptions sans recopier tout le code source dans le terminal.

## 1.0.0-rc121 — comportement de la fenêtre et retours visibles

- La croix quitte Mirivue par défaut ; l'ancienne réduction dans la zone de notification reste disponible dans les réglages. Le message « Premiers pas » est retenu dès sa fermeture.
- Le double-clic sur le fond ne remonte plus par défaut ; une option dans Général permet de rétablir ce geste. Les messages restent visibles dans une barre inférieure lorsque le panneau Emplacements est masqué.
- Un dépôt interne sans touche modificatrice propose Déplacer, Copier ou Lier. Ctrl, Maj et Ctrl+Maj conservent leurs actions directes ; le dépôt dans la Corbeille reste une mise à la corbeille.
- Les tailles suivent la langue de l'interface et n'affichent pas de fraction d'octet. La date informelle masque les secondes, l'état distingue les informations détaillées non lues des données rapides et une nouvelle installation montre moins de colonnes initiales. Les barres de défilement horizontales du fil d'Ariane sont masquées.

## 1.0.0-rc120 — sécurité des écritures et des opérations

- L’édition des métadonnées préserve l’original par lien matériel quand le système de fichiers le permet ; en repli, la copie vérifie l’espace disponible et une sauvegarde partielle est supprimée en cas d’échec. Les sauvegardes existantes ne sont pas modifiées.
- L’extraction RAR avec Ark n’a plus de délai fixe de 120 secondes ; l’annulation reste disponible et les erreurs d’Ark sont recueillies sans risque de remplir un tube de sortie.
- Lors d’une suppression, les XMP et autres fichiers associés sont présentés dans le dialogue. Le choix par défaut ne concerne que les fichiers sélectionnés. Aucun compagnon n’est ajouté après ce choix.
- Installer.sh et la demande de composants manquants depuis l’application indiquent les paquets nécessaires et la commande de mise à jour complète adaptée à Arch/CachyOS. Ils ne lancent plus de transaction de paquets eux-mêmes.

## 1.0.0-rc119 — menu contextuel de la vue en icônes

- « Afficher les miniatures » a été retiré du menu contextuel du fond, où il répétait la commande de la barre d’outils et du menu Affichage. Les miniatures et leurs réglages restent disponibles.

## 1.0.0-rc118 — tri dans le menu de la vue en icônes

- Le menu contextuel du fond de la vue en icônes donne accès à « Trier par », avec les mêmes critères et le même ordre que le menu Affichage. Le tri reste propre au panneau actif et s’applique aussi à sa vue détaillée.

## 1.0.0-rc117 — rafraîchissement après suppression

- La suppression KIO relit uniquement les panneaux dont l’emplacement est touché, et la Corbeille si elle est ouverte. Un dossier sans rapport ne se recharge plus ; les opérations autres que la suppression conservent leur comportement.

# Historique des versions

## 1.0.0-rc116

- Supprime les notifications « terminé » supplémentaires de Mirivue pour les transferts KIO. En cas d’échec KIO, laisse le délégué KDE présenter son erreur et affiche le détail dans Mirivue sans ouvrir une seconde fenêtre ou une notification urgente. Les annulations restent discrètes.

## 1.0.0-rc115

- Isole les préférences et données des tests graphiques dans un profil temporaire. Le test des onglets démarre avec ses propres paramètres, indépendamment du démarrage en vue scindée choisi par l’utilisateur. Aucun comportement de la vue scindée en production ne change.

## 1.0.0-rc114

- Fige les fonctions pour la stabilisation de la 1.0 : corrige le test de suppression KIO périmé, actualise les critères et les guides de validation.
- Retire les anciens binaires natifs du code source ; les installations compilent leurs propres assistants, et le diagnostic vérifie les composants installés ou configure temporairement les sources natives.
- Clarifie le parcours de validation : Valider-RC116.sh pour les tests, Verifier-installation-RC116.sh pour l’installation, A-verifier-RC116.md pour les essais manuels.

## 1.0.0-rc113

- Une seule entrée « Extraire » pour les archives : action du service KDE si disponible, extraction Mirivue en secours sinon.

## 1.0.0-rc112

- Évite la double entrée « Extraire » lorsque le greffon KDE fournit cette action : son extraction reste au premier niveau, et l’extraction propre à Mirivue est déplacée dans Organiser. Si KDE ne fournit pas l’action, l’extraction Mirivue reste visible au premier niveau.

## 1.0.0-rc111

- Réorganise le menu contextuel : suppression avant les actions KDE, actions de service KDE au premier niveau, outils Mirivue regroupés après elles et Propriétés en dernier. Masque « Afficher dans le dossier » lorsque le fichier figure déjà dans le dossier ouvert.

## 1.0.0-rc110

- Échap ferme la barre de filtre lorsque son champ a le focus ; Ctrl+I permet aussi de l’ouvrir ou de la fermer.
- La recherche démarre après une brève pause pendant la saisie ; une nouvelle saisie annule la recherche précédente avant de relancer les résultats du panneau actif.
- F4 affiche un panneau Terminal avec KonsolePart, synchronisé dans les deux sens pour les dossiers locaux ; Maj+F4 conserve le lancement d’un terminal séparé. Konsole est une dépendance facultative.

## 1.0.0-rc109

- F2 sur une sélection multiple ouvre le renommeur intégré ; F2 sur un seul fichier garde le renommage direct.
- La création des dossiers par regroupement et organisation multimédia passe par KIO et entre dans l’historique d’annulation, après les déplacements correspondants.
- Ajoute le filtre immédiat Ctrl+I, la recherche par noms avec `*` et `?` dans les dossiers locaux ou KIO distants, et une recherche locale dans les fichiers texte jusqu’à 16 Mio.
- Charge les actions de service et les extensions de menu contextuel KDE via `KFileItemActions` pour les fichiers sélectionnés.
- Propose une confirmation configurable à la fermeture réelle d’une fenêtre avec plusieurs onglets ; la réduction dans la zone de notification ne la déclenche pas.

## 1.0.0-rc108

- Conserve plusieurs lots du renommeur intégré dans l’ordre de Ctrl+Z/Ctrl+Maj+Z avec les tâches KIO ; les échanges de noms et la vérification des signatures restent protégés.
- Route « Dupliquer », les déplacements d’organisation vers un nom choisi et le nettoyage des doublons par KIO, avec annulation des transferts et confirmation KDE pour la corbeille. Chaque destination nommée est une opération annulable distincte.
- Applique aussi la confirmation KDE à la suppression définitive, permet de rouvrir les onglets fermés avec Ctrl+Maj+T et crée un fichier nommé lors du collage local de texte ou d’image.

## 1.0.0-rc107

- Les copies et déplacements locaux ordinaires, ainsi que la mise à la corbeille, utilisent les tâches KIO et deviennent accessibles par Ctrl+Z. La confirmation de corbeille est celle de KDE ; la suppression définitive conserve son avertissement explicite.
- Les noms de fichiers et de dossiers suivent les règles Linux sous Plasma, y compris les espaces et caractères autorisés par le système de fichiers. Le renommeur intégré reste disponible et ses échanges de noms peuvent être annulés puis rétablis après vérification des fichiers.

## 1.0.0-rc106

- Ctrl+molette dans les vues Icônes, Détails et Compacte tient compte de l'amplitude de la rotation : les fractions de cran sont cumulées séparément dans chaque vue et un événement de plusieurs crans applique plusieurs niveaux. Les raccourcis clavier et les tailles mémorisées restent inchangés.

## 1.0.0-rc105

- Affiche l’icône Opérations du panneau Emplacements uniquement pendant une analyse ou un transfert ; sa bulle décrit la progression. Le menu Opérations garde l’accès à l’historique une fois l’icône masquée. La navigation et la création de miniatures ne déclenchent pas cette icône.

## 1.0.0-rc104

- Dans « Opérations en cours et historique », place les actions côte à côte, masque les détails sans sélection et supprime le bouton Fermer redondant avec la décoration de fenêtre. Lorsque la liste est vide, l’accès est désactivé ; un historique ou un transfert conserve son accès.

## 1.0.0-rc103

- L’assistant C++ de miniatures essaie KIO en premier et produit une image vidéo locale de secours uniquement lorsque KIO ne fournit aucun aperçu. Les images vidéo de secours sont mises en cache séparément et ne masquent pas un générateur KDE installé ultérieurement. Le rendu détaillé et les autres secours restent disponibles.

## 1.0.0-rc102

- Accepte les mises à jour mineures de PySide6 6, dont 6.12, dans les dépendances du paquet Arch, le projet Python et le vérificateur de l'installateur. Corrige le blocage de `pacman -Syu` provoqué par `pyside6<6.12`.

## 1.0.0-rc101

- N'affiche plus de rectangle de sélection sur toute la vue pendant un dépôt sur le dossier courant. Seul un dossier survolé garde son indication localisée ; le dépôt sur le fond et le choix de l'opération restent disponibles.

## 1.0.0-rc100

- Utilise les assistants KIO et KApplicationTrader pour ouvrir les fichiers, proposer « Ouvrir avec » et vider la corbeille, y compris lorsque Mirivue KDE est lancé sous GNOME. Une indisponibilité de KIO est signalée sans basculer silencieusement sur GIO.
- L'icône de l'application associée aux documents provient du service KDE préféré pour leur type MIME ; si aucun service ou icône n'est disponible, l'icône MIME est utilisée. L'association est relue après un changement de préférence.
- Conserve le générateur local d'aperçus lorsque KIO ne fournit pas de miniature et le routage FileManager1 entre sessions.

## 1.0.0-rc99

- Utilise sous Plasma `KApplicationTrader` pour le menu « Ouvrir avec… », et `KIO::ApplicationLauncherJob` pour démarrer l'application choisie. Sous GNOME, l'intégration GIO restait en place.
- Utilise `KIO::emptyTrash()` pour vider la corbeille sous Plasma ; évite les chemins de secours GIO pour les fichiers et URL quand l'assistant KDE manque.

## 1.0.0-rc98

- Ouvre les fichiers locaux sous Plasma avec `KIO::OpenUrlJob`, y compris lors d'une sélection multiple, afin d'utiliser les associations et le dialogue de choix de KDE comme Dolphin.
- Conserve les chemins d'ouverture spécifiques des archives, dossiers et emplacements réseau, ainsi que les autres bureaux.

## 1.0.0-rc97

- Dans la personnalisation de la barre d’outils, remplace les boutons « Déplacer avant » et « Déplacer après » par deux flèches verticales à icônes du thème KDE, placées près de la liste. Leurs états suivent la sélection et les limites de la liste.
- Préserve le glisser-déposer, les cases de visibilité, les barres de chemin, la remise à zéro et l'enregistrement de l'ordre. L'annulation ne modifie pas la disposition enregistrée.

## 1.0.0-rc96

- Le clic droit sur les en-têtes des détails regroupe les colonnes comme Dolphin : informations générales, Document, Image, Audio, Vidéo et Autre. Les réglages de largeur et les profils de colonnes restent dans le menu.
- Le menu Affichage → Informations affichées adopte les mêmes groupes. Les profils existants conservent leurs colonnes ; « Nom » reste visible et fixe comme dans Dolphin, y compris dans les anciens profils.

## 1.0.0-rc95

- Retire la case « Actualiser automatiquement les dossiers ouverts » de Configuration → Général. Les dossiers locaux visibles restent surveillés automatiquement, y compris si ce réglage avait été désactivé dans une version précédente. F5 reste disponible pour demander une actualisation manuelle.
- Supprime la dépendance de la surveillance au réglage enregistré et adapte le contrôle graphique de la configuration. Les emplacements réseau restent exclus du suivi local existant.

## 1.0.0-rc94

- Corrige l'activation de `org.freedesktop.FileManager1` lorsque la même personne utilise GNOME et Plasma : le lanceur D-Bus conservé dans le profil délègue à Nautilus sous GNOME et démarre Mirivue sous Plasma. Mirivue ne revendique son nom D-Bus que sous Plasma lorsqu'il est le gestionnaire de dossiers par défaut.
- Lors de la vérification après mise à jour, migre une ancienne entrée d'activation RC93 appartenant à Mirivue vers le lanceur installé, sans créer d'entrée Mirivue dans un profil GNOME qui n'en avait pas. Vérifie le routage GNOME, Plasma et une session ambiguë qui mentionne les deux.
- La configuration propose d'ouvrir les dossiers demandés de l'extérieur dans de nouveaux onglets de la fenêtre existante, comme l'option « Fichiers d'ouverture » de Dolphin. Le réglage déjà enregistré est conservé.
- Le lancement normal et l'interface FileManager1 utilisée par les navigateurs suivent ce même choix. Quand il est désactivé, une nouvelle fenêtre s'ouvre ; une demande explicite de nouvelle fenêtre reste indépendante du choix.
- La sélection du fichier demandé et l'affichage de ses propriétés sont conservés dans l'onglet ou la nouvelle fenêtre de destination.

## 1.0.0-rc92

- F2 renomme le dossier sélectionné lui-même. Dans son menu contextuel, « Organiser → Renommer le contenu du dossier… » transmet ses éléments immédiats, y compris les éléments masqués et les sous-dossiers, sans descendre dans ces derniers.
- Une seule commande suit le choix utilisé pour « Renommer la sélection… » : outil intégré par défaut, ou outil externe sélectionné dans Configuration → Applications externes. Le renommage intégré vérifie les noms avant application et rafraîchit les autres panneaux concernés.
- Corrige l'action sans effet provoquée par le filtrage des dossiers dans la sélection destinée au renommage ; conserve ce filtrage pour les autres commandes qui exigent des fichiers.

## 1.0.0-rc91

- En vue Détails scindée, les lignes alternées sont visibles uniquement dans le panneau actif ; le panneau inactif conserve un fond uni. Le basculement suit le changement de panneau, sans valeur de couleur ni feuille de style ajoutée.
- Étend le contrôle graphique aux lignes alternées des deux panneaux.

## 1.0.0-rc90

- Corrige le retour à la palette native du panneau réactivé : `QWidget` ne possède pas `unsetPalette()` dans PySide6. Une `QPalette()` sans rôles explicites rétablit l'héritage du thème et évite l'exception dans le contrôle graphique de la RC89.
- Affiche désormais la trace conservée par le lanceur si un contrôle graphique de l'installation échoue, pour ne pas masquer la cause derrière le seul message générique.

## 1.0.0-rc89

- Distingue les deux vues scindées comme Dolphin : le panneau inactif utilise les pinceaux « inactif » du thème Qt/KDE pour le fond, le texte et la sélection, tandis que le panneau actif retrouve sa palette native.
- Met à jour cette palette lors du changement de panneau et de thème. Aucune couleur, transparence ni feuille de style fixe n'est ajoutée.
- Vérifie par interaction Qt que les trois modes de vue basculent entre les palettes active et inactive.

## 1.0.0-rc88

- Laisse le style Qt/KDE peindre la sélection et le survol dans les vues Icônes, Compacte et Détails. Supprime le délégué de sélection qui mélangeait les couleurs du thème et le contour ajouté au-dessus des lignes.
- Retire la composition de couleurs du panneau inactif et la feuille de style des fonds de panneaux. Les deux vues conservent les couleurs et les lignes alternées du thème ; le focus et le titre indiquent le panneau actif.
- Retire la règle de couleur du panneau Emplacements et du titre actif. Le contrôle graphique vérifie que les vues n'imposent plus de rendu de sélection ni de feuille de style aux panneaux.
- Ajoute une liste de vérification visuelle dans Plasma, GNOME et Cinnamon avant toute déclaration de conformité esthétique.

## 1.0.0-rc87

- Raccourcit le menu contextuel des fichiers : le renommage apparaît avec les commandes courantes ; « Modifier les métadonnées… », « Étiquette personnelle » et le choix d’un doublon multimédia se trouvent dans « Média ». Le choix d’un doublon non multimédia reste dans « Organiser ».
- Conserve les autres commandes, y compris « Afficher dans le dossier », « Copier le chemin », « Dupliquer » et les opérations d’archive.
- Clarifie l’étiquette « À supprimer » en « À examiner pour suppression » sans modifier la valeur stockée des anciennes étiquettes.

## 1.0.0-rc86

- Déplace la lecture détaillée des métadonnées des médias du dossier actif depuis le clic droit sur une zone vide vers Outils → Outils Mirivue. La commande indique le nombre de médias concernés et ne lit que les enfants directs du dossier, y compris lorsque l'inventaire récursif est activé.
- Déplace le choix de langue dans Général et supprime la page Apparence et langue, qui ne proposait plus de réglage d'apparence.
- Met à jour les messages d'aide pour distinguer les informations rapides affichées à l'ouverture des détails lus à la demande.

## 1.0.0-rc85

- Déplace l'actualisation automatique des dossiers dans « Général » et retire l'onglet « Fiabilité » qui ne contenait que cette option. La valeur enregistrée est conservée.
- Utilise l'icône colorée de tableau `x-office-spreadsheet` du thème Breeze pour « Colonnes », avec des icônes du thème en repli.

## 1.0.0-rc84

- Réordonne les icônes de Configuration : couleur pour l’apparence, affichage pour les colonnes et associations de fichiers pour les applications externes. L’étoile générique n’est plus utilisée.
- Les intitulés des rubriques et le titre de la page retrouvent la graisse normale observée dans la configuration de Dolphin. La largeur reste calculée par le style, sans dimension fixe.

## 1.0.0-rc83

- Les rubriques de Configuration gardent les icônes du thème KDE quand elles existent. Si un nom manque dans le thème, une icône standard correspondante du style Qt/KDE évite une rubrique sans pictogramme.
- Le contrôle graphique indique désormais les libellés précis des rubriques privées d’icône.

## 1.0.0-rc82

- Le contrôle graphique hors écran sort de son processus enfant immédiatement après une fermeture acceptée, sans invoquer les destructeurs Qt/KF6 qui restent bloqués après `closeEvent` sur la machine de validation. Une fermeture refusée ou une assertion échouée reste un échec explicite.
- Le test imprime désormais si la fermeture a été acceptée, ce qui permet de distinguer un problème de Mirivue d’un blocage au démontage de l’environnement de test.

## 1.0.0-rc81

- Corrige la séquence de fermeture du contrôle graphique hors écran : elle vérifie que `closeEvent` accepte la fermeture, puis quitte sans relancer indéfiniment la boucle d’événements Qt après la fermeture.
- Son résultat final est immédiatement écrit dans la sortie.
- L’ouverture de la configuration n’interroge plus une nouvelle fois le système de fichiers pour les dossiers d’emplacements et le dossier de démarrage enregistré, qui peuvent être sur un disque indisponible.
- Conserve la limite de temps et les repères de la RC80 afin qu’un autre blocage éventuel soit identifiable.

## 1.0.0-rc79

- Remplace les pictogrammes monochromes et parfois peu explicites du panneau de configuration par des icônes thématiques Breeze pour les dossiers, l’apparence, l’affichage des colonnes, les médias, la synchronisation du dossier et les applications externes.
- Les icônes proviennent du thème KDE choisi par KF6, avec une alternative sémantique du même thème pour chaque rubrique. Aucune couleur n’est codée en dur.
- Vérification de l’interface de configuration en simulant aussi une session GNOME : KF6 choisit le thème d’icônes KDE avant la création de QApplication, comme pour les autres composants natifs déjà intégrés.

## 1.0.0-rc78

- Corrige la disparition différée des vignettes : la surveillance du dossier préserve l’aperçu d’un fichier inchangé et recrée celui d’un fichier modifié après la mise à jour des lignes. Les notifications regroupées n’interrompent plus sans cesse la génération.
- Ajoute un scénario de régression pour une notification arrivant après un déplacement.

## 1.0.0-rc77

- La miniature déjà disponible est associée à la ligne de destination avant son insertion dans le panneau. Elle apparaît donc immédiatement après la copie ou le déplacement local.
- Si la source n’avait pas encore de miniature, la destination lance l’aperçu KDE habituel après le transfert ; aucun rafraîchissement manuel n’est nécessaire.
- Un transfert KIO terminé pendant le chargement d’un panneau programme une nouvelle lecture du dossier après ce chargement, afin de ne pas perdre les nouveaux éléments et leurs aperçus.

## 1.0.0-rc76

- Corrige la course entre `FolderSizeWorker` et le registre des tâches Qt : un objet déjà détruit n’est plus interrogé pendant l’actualisation du nombre d’opérations.
- L’annulation d’un calcul de dossier attend désormais la fin du fil avant sa destruction différée. La navigation rapide entre dossiers et panneaux ne doit plus produire cette exception.

## 1.0.0-rc75

- Les copies et déplacements locaux publient leur progression dans les tâches de Plasma avec l’icône de Mirivue, l’emplacement de destination et les commandes Annuler, Pause et Reprendre. Le moteur de transfert sécurisé et sa récupération après incident sont conservés.
- Les opérations KIO utilisent leur propre suivi natif de progression Plasma au lieu de masquer cette information.
- L’installation utilisateur reconstruit les assistants natifs depuis les sources pour éviter de conserver d’anciens binaires.

## 1.0.0-rc74

- Agrandit le dessin de l’icône KDE dans son cadre standard, sans modifier le réglage de taille du dock : à 128 px, son contenu passe de 100 × 92 à 118 × 104 px et garde le même alignement inférieur que sur la capture comparative avec Dolphin.
- Le vérificateur compare désormais les SVG et PNG installés avec ceux de la version et signale une ancienne icône locale susceptible de masquer l’icône système.

## 1.0.0-rc73

- Nouvelle icône KDE retenue parmi trois propositions : dossier bleu saphir plus carré, paysage visible, onde sonore et bouton de lecture ambre. Tous les rendus SVG, PNG, ICO et ICNS ont été régénérés.
- Le lanceur et l’icône du dock utilisent les ressources KDE actualisées. Mirivue GNOME conserve sa propre icône.

## 1.0.0-rc72

- La largeur maximale du groupe de commandes suit désormais le bord du panneau Emplacements. La barre de chemin gauche commence au bord de la vue, en mode simple comme en mode scindé, même lorsque `KToolBar` étire ses actions.
- La largeur reste compressible afin de permettre le redimensionnement de la fenêtre sous GNOME/Wayland.
- Le contrôle dans une vraie session graphique mesure le bord des chemins et des vues avant et après redimensionnement et passage en mode scindé.

## 1.0.0-rc71

- La barre principale est créée comme `KToolBar` par KF6. Les groupes de commandes et les `KUrlNavigator` sont trois actions de cette barre au lieu d’un seul conteneur couvrant toute la fenêtre.
- La largeur du groupe de commandes est demandée avec une taille préférée pour ne pas bloquer le redimensionnement de la fenêtre sous GNOME.
- Les en-têtes des colonnes de la vue détaillée sont alignés à gauche, comme celui de Dolphin.
- Le contrôle dans une session graphique vérifie `KToolBar`, `KFilePlacesView` et `KUrlNavigator`.

## 1.0.0-rc68

- Corrige l’initialisation du thème d’icônes par `KIconTheme::initTheme()` avant `QApplication`, comme le prescrit KF6. Le thème est choisi par KDE et par le thème de plateforme ; Mirivue ne le force plus après le démarrage.
- La barre d’outils emploie des `QToolButton` et la taille d’icônes fournie par `QToolBar` au lieu de petits `QPushButton` et de `PM_SmallIconSize`.
- Le thème GNOME n’est plus remplacé par les valeurs de `kdeglobals` dans cette session. Mirivue GNOME reste indépendante.

## 1.0.0-rc67

- Le contrôle dans GNOME charge explicitement le paquet installé, hors du dossier des sources extrait ; il affiche la cause précise si le panneau KIO échoue réellement.
- Le contrôle FileManager1 vérifie également le paquet installé. Aucun réglage utilisateur n’est modifié.
- Sous GNOME, l’édition KDE lit désormais son thème d’icônes et son style Qt dans `kdeglobals`, comme dans Plasma, et garde ses icônes KDE dans la barre d’outils.
- Le nom d’application Qt correspond au lanceur `org.pdenams.Mirivue.Qt.desktop` pour améliorer l’association de la fenêtre au dock ; le nom affiché reste « Mirivue ».
- Le paquet, le lanceur et l’icône de Mirivue GNOME ne sont pas modifiés.

## 1.0.0-rc66

- Le panneau natif `KFilePlacesView` et ses barres de chemin `KUrlNavigator` se chargent également sous GNOME quand la bibliothèque KF6 est installée.
- Le vérificateur contrôle leur présence dans une véritable session GNOME, en plus des vérifications hors écran.

## 1.0.0-rc65

- La configuration présente ses rubriques avec icône centrée au-dessus du texte. La largeur fixe suit le calcul de KPageListView et la métrique du thème Qt.
- Une recherche filtre les rubriques et le contenu de leurs réglages. Le contrôle hors écran vérifie la navigation et le filtrage.

## 1.0.0-rc64

- la recherche récursive et le calcul de taille des dossiers disposent d’un
  module dédié, sans modification de leur logique ni de leurs signaux ;
- le contrôle d’installation exerce les trois boutons de vue et leurs menus,
  une ancienne disposition de barre d’outils, la vue scindée et la recherche
  dans des réglages isolés ;
- le lancement hors écran détecte également un bouton ou une icône absents.

## 1.0.0-rc63

- le bouton Vue compacte figure dans la barre d’outils et dans sa personnalisation ;
  les dispositions enregistrées auparavant reçoivent aussi le bouton ;
- les icônes des vues Icônes, Compact et Détails reprennent les noms
  employés par KDE et restent visibles en largeur réduite.

## 1.0.0-rc62

- le mode Icônes, Compact ou Détails est mémorisé par dossier, y compris
  après redémarrage ; le tri par dossier déjà présent est conservé ;
- F7 affiche le panneau Dossiers, tout en permettant de conserver le panneau
  Emplacements natif (F9) ; l’icône Opérations reste en bas à gauche ;
- l’ancien arbre Emplacements et ses réglages concurrents ont été retirés.
  Le panneau visible utilise exclusivement KFilePlacesView ;
- la colonne « Débit calculé (comparaison) » n’est plus proposée, même avec
  un profil ou une ancienne configuration. Le calcul de comparaison interne
  et le débit vidéo affiché restent distincts.

## 1.0.0-rc61

- un vidage KIO réussi efface immédiatement les anciennes lignes de tous les
  panneaux affichant `trash:/`, y compris en vue scindée et dans les onglets
  en arrière-plan ; chacun lance ensuite sa propre relecture ;
- un chargement KIO déjà annulé ne peut plus réinsérer ses anciennes lignes
  pendant cette relecture.

## 1.0.0-rc60

- le menu natif des Emplacements conserve l’action et la confirmation KIO
  « Vider la corbeille », mais Mirivue reçoit maintenant la fin de sa tâche
  pour recharger les panneaux `trash:/` ;
- lorsque l’état `trashrc` indique déjà « vide » mais que la vue présente
  encore des éléments, l’action peut être sélectionnée pour que KDE confirme
  l’état réel, puis la liste est actualisée. L’icône reste celle du thème KDE.

## 1.0.0-rc59

- après « Vider la corbeille », tous les panneaux affichant une adresse
  `trash:/` sont rechargés dès la fin réussie de l’opération, y compris ceux
  des onglets en arrière-plan. Les éléments supprimés disparaissent alors
  de la liste sans action manuelle.

## 1.0.0-rc58

- les onglets conservent séparément leurs dossiers, leur historique, leur
  recherche et leur disposition scindée ; les raccourcis Ctrl+T, Ctrl+W,
  Ctrl+Tab et Ctrl+Maj+Tab sont raccordés à ces états ;
- le panneau natif `KFilePlacesView` ouvre un emplacement dans l’onglet actif,
  un nouvel onglet ou une nouvelle fenêtre selon l’action KDE. Les dépôts
  utilisent le menu et les tâches `KIO::drop`, avec retour des erreurs ;
- les barres de chemin utilisent le composant KF6 `KUrlNavigator` et le modèle
  des emplacements KDE dans chaque panneau, y compris les adresses KIO ;
- la validation sur CachyOS a réussi : 237 tests Python, compilation native
  KF6 et contrôles manuels des principales interactions. L’icône Opérations
  reste en bas à gauche du panneau Emplacements.

## 1.0.0-rc57

- la taille des icônes du panneau Emplacements natif suit désormais la
  préférence `PlacesPanel/IconSize` de Dolphin dans `dolphinrc`, avant le
  chargement du modèle KDE ;
- un choix de taille effectué dans le menu natif est enregistré par KConfig
  dans cette même préférence, y compris le mode automatique du style Plasma ;
- aucune couleur ni taille d’icône fixe n’est ajoutée ; l’icône Opérations
  conserve son emplacement au bas du panneau, alignée à gauche.

## 1.0.0-rc56

- les erreurs envoyées par le modèle KDE du panneau Emplacements, notamment
  lors d’un montage ou d’une éjection impossible, sont désormais présentées
  à l’utilisateur ; elles n’étaient pas raccordées à la fenêtre en RC54/RC55 ;
- le panneau natif et l’action « Ouvrir en vue scindée » sont conservés,
  de même que l’icône Opérations au bas du panneau, alignée à gauche.

## 1.0.0-rc55

- le menu natif d’un emplacement ajoute « Ouvrir en vue scindée », comme le
  panneau Dolphin ; l’emplacement s’ouvre dans le panneau opposé, qui devient
  actif, et le mode scindé est activé au besoin ;
- la bibliothèque KDE conserve les menus, les sections et la gestion des
  périphériques de la RC54 ; l’icône Opérations reste en bas à gauche.

## 1.0.0-rc54

- remplacement du panneau Emplacements reconstruit par le véritable
  `KFilePlacesView` de KDE, avec `KFilePlacesModel` et ses sections, menus
  contextuels, emplacements masqués et périphériques partagés avec Dolphin ;
- activation des emplacements et dépôt de fichiers raccordés à la navigation
  et aux opérations de Mirivue ; la bibliothèque est construite et livrée
  avec le paquet CachyOS ;
- l’icône Opérations reste séparée du panneau natif, en bas à gauche.

## 1.0.0-rc53

- le panneau Emplacements conserve sa position et la sélection lors des
  rechargements ; un clic répété n’interrompt plus la navigation déjà engagée
  ni le montage en cours d’un périphérique ;
- les entrées d’une section KDE masquée restent accessibles par « Afficher
  toutes les entrées », puis la section peut être rétablie dans son menu
  contextuel, comme dans Dolphin ;
- les commandes de taille d’icônes et d’ajout figurent dans le menu du fond,
  tandis que « Masquer la section » appartient aux en-têtes et entrées ;
- l’icône Opérations demeure au bas du panneau, alignée à gauche.

## 1.0.0-rc52

- ouverture des fichiers et dossiers par le signal natif d’activation Qt,
  suivant le réglage de Plasma pour le simple ou le double clic dans les
  trois vues des deux panneaux ;
- vue Icônes par défaut pour une nouvelle configuration, conformément au
  réglage initial de Dolphin ; un mode déjà choisi reste conservé.

## 1.0.0-rc51

- les trois modes sont présentés dans l’ordre de Dolphin : Icônes, Compacte,
  Détails, dans la barre, le menu Affichage et le menu de débordement ;
- les listes ouvertes par les chevrons respectent « Éléments cachés » et
  consultent KIO sans figer la fenêtre, y compris pour les dossiers locaux.

## 1.0.0-rc50

- bouton « Vue compacte » dans la barre d’outils, synchronisé avec le menu
  Affichage, Ctrl+2 et le panneau actif en vue scindée ;
- chevrons cliquables dans les barres de chemin : ils présentent les
  sous-dossiers du segment précédent. Les emplacements KIO sont lus sans
  bloquer la fenêtre.

## 1.0.0-rc49

- retrait de la marge issue de `SE_LineEditContents`, qui décalait encore le
  texte du fil d'Ariane vers le bas sous Plasma ;
- répartition du débordement vertical de la zone déroulante des boutons au
  lieu de conserver l'alignement supérieur par défaut. À confirmer à l'écran.

## 1.0.0-rc48

- alignement des deux modes de la barre de chemin sur la zone de contenu
  calculée par le style Qt, sans couleur ni hauteur fixe ;
- centrage vertical du fil d'Ariane dans sa zone déroulante. À valider sur
  Plasma avec les captures de la RC47 comme point de comparaison.

## 1.0.0-rc47

- F6 alterne entre la barre de chemin en boutons et son champ modifiable,
  tandis que Ctrl+L sélectionne le chemin à remplacer, conformément aux
  deux commandes distinctes de Dolphin.

## 1.0.0-rc46

- vue compacte raccordée aux sélections, aperçus, menus contextuels, gestes de
  zoom et glisser-déposer, également dans le second panneau ; son zoom est
  mémorisé indépendamment ;
- menu contextuel de la barre de chemin : Copier, Coller, Modifier, Naviguer,
  Afficher le chemin complet, avec conservation de « Copier le nom du dossier » ;
- fil d'Ariane abrégé à partir des noms du panneau Emplacements KDE actuel ;
- barre de menus masquée par défaut pour les nouvelles configurations, sans
  modifier les préférences déjà enregistrées ;
- correction du test graphique de la structure des menus, resté sur une
  ancienne liste après la refonte des menus.

## 1.0.0-rc45

- menus principaux ramenés à la structure KDE de Dolphin : Fichier, Édition,
  Affichage, Aller, Outils, Configuration et Aide ;
- outils spécifiques et suivi des opérations conservés dans deux sous-menus
  explicites du menu Outils ;
- commande globale « Ouvrir dans le terminal » déplacée dans Outils et associée
  à Maj+F4 comme dans Dolphin ;
- ajout de la vue compacte Qt au choix Icônes/Compacte/Détails, avec le
  raccourci Ctrl+2 de Dolphin et les métriques d'icônes du thème ;
- panneau Emplacements : ajout des tailles Automatique et Très grande (48 px),
  suppression de la commande spécifique d'actualisation et du faux élément
  vide utilisé comme séparateur de sections ;
- hauteurs des barres de chemin, boutons de barre d'outils et en-têtes laissées
  au calcul du style Plasma au lieu d'être imposées en pixels ;
- ajout de tests de non-régression portant sur ces règles de conformité.

## 1.0.0-rc43

- masquage et réaffichage des sections rendus immédiatement visibles, même si
  l’écriture native KIO est encore en cours de propagation ;
- une commande de masquage désactive automatiquement « Afficher toutes les
  entrées », qui reste disponible pour révéler ensuite les éléments masqués ;
- ajout d’un espace neutre de huit pixels entre les sections du panneau.

## 1.0.0-rc42

- panneau Emplacements présenté comme dans Dolphin, avec des sections plates
  dépourvues de chevrons d’ouverture ou de fermeture ;
- ajout de « Masquer la section » et « Afficher la section » dans le menu
  contextuel des en-têtes ;
- masquage des entrées et des sections enregistré par `KFilePlacesModel` dans
  la configuration KDE partagée avec Dolphin ;
- conservation de « Afficher toutes les entrées », des tailles d’icônes, du
  glisser-déposer et des commandes propres aux périphériques.

## 1.0.0-rc41

- hauteur des barres de chemin alignée sur Dolphin : 34 pixels logiques,
  correspondant aux 36 pixels physiques mesurés avec l’échelle Plasma active ;
- suppression des cinq pixels excédentaires dans la zone supérieure ;
- couleurs des états actif et inactif laissées entièrement au thème Breeze,
  sans palette ni valeur RVB imposée par Mirivue.

## 1.0.0-rc40

- remplacement du faux conteneur de barre d’outils par un véritable
  `QToolBar`, afin que Breeze l’intègre automatiquement à la zone d’en-tête ;
- jeu de couleurs KDE `Header` appliqué nativement à la barre de titre et à
  l’espace des outils, sans couleur copiée ni valeur RVB codée en dur ;
- conservation du jeu `View` pour l’intérieur des barres de chemin, qui reste
  naturellement plus sombre selon le thème actif ;
- suppression de la séparation entre la décoration de fenêtre et la zone
  d’outils par le gestionnaire natif des zones d’outils de Breeze.

## 1.0.0-rc39

- suppression du séparateur horizontal ajouté sous la barre d’outils et les
  barres de chemin ; les en-têtes de colonnes conservent seuls leur contour
  dessiné par le style Plasma.

## 1.0.0-rc38

- suppression du texte temporaire « Calcul en attente » : comme Dolphin, la
  cellule d’un dossier reste vide jusqu’à la publication de son résultat ;
- zone supérieure, barre de menus, commandes et états de survol rendus par le
  style Qt/Plasma actif, sans feuille de style ni palette claire/sombre propre ;
- barres de chemin conservées avec leur cadre natif de champ de saisie et les
  couleurs sémantiques du thème KDE, sans valeur de couleur codée en dur.

## 1.0.0-rc37

- calcul du nombre d’éléments ou de la taille des dossiers conservé hors de
  l’interface, sans effacer les valeurs déjà affichées pendant le travail ;
- publication groupée de tous les résultats dans une seule mise à jour du
  modèle, afin d’éviter le scintillement et les retris successifs du panneau.

## 1.0.0-rc36

- publication atomique de l’inventaire initial d’un dossier, comme le modèle
  de fichiers de Dolphin, au lieu d’insérer et retrier des lots visibles ;
- tri et placement des lignes ou icônes effectués une seule fois au chargement ;
- mises à jour ultérieures limitées aux métadonnées et aux changements réels.

## 1.0.0-rc35

- barres de chemin conservées comme les `KUrlNavigator` de Dolphin et
  reconstruites uniquement lorsque l’emplacement du panneau change ;
- changements de sélection, de progression, de focus ou d’état d’un panneau
  sans effet sur les boutons du chemin ;
- suppression du dernier réalignement différé à 80 ms lors de l’affichage.

## 1.0.0-rc34

- préparation de la vue simple ou scindée et des barres de chemin avant le
  premier affichage de la fenêtre, afin de supprimer le scintillement ;
- restauration indépendante du dernier dossier de chaque panneau lorsque le
  démarrage sur le dernier emplacement est choisi ;
- retour sûr au dossier principal lorsqu’un ancien emplacement local, par
  exemple un disque amovible, n’est plus disponible ;
- mémorisation de la position du séparateur et suppression des réalignements
  temporisés redondants au démarrage.

## 1.0.0-rc33

- chargements ordinaires de dossiers rendus silencieux lorsqu’ils se terminent
  en moins de 450 ms, afin d’éviter le clignotement au démarrage ;
- progression affichée après ce délai pour les dossiers plus longs, y compris
  en mode scindé, sans retarder les recherches ni les opérations de fichiers.

## 1.0.0-rc32

- suppression complète de la barre d’état et de son option d’affichage ;
- regroupement des messages et progressions au pied du panneau Emplacements,
  sans séparateur ni espace vide lorsque ces éléments sont inactifs ;
- bouton compact à trois points utilisant le thème KDE pour ouvrir les
  opérations, leurs progressions et leur historique ;
- indicateur temporaire dans la barre d’outils lorsque le panneau Emplacements
  est masqué pendant une activité ;
- priorité visuelle unique entre opération directe, transfert et tâche de fond ;
- retours audio, vidéo, zoom et PDF placés dans le panneau d’aperçu ;
- informations de sélection et d’espace disque conservées sous chaque panneau.

## 1.0.0-rc31

- correction du plantage `NameError: update_values` lors de l’ajout ou de
  l’actualisation d’un fichier visible ;
- tests réels de l’ajout d’un nouvel élément et du remplacement d’une ligne
  préliminaire après lecture des informations ;
- suppression des anciens scanners de calcul/enregistrement de débit et de
  vérification complète des médias, devenus inaccessibles ;
- correction des textes d’aide qui décrivaient encore ces fonctions retirées.

## 1.0.0-rc30

- remplacement de « Nouveau dossier… » dans le menu contextuel du fond par
  le sous-menu KDE « Créer un nouveau » ;
- sous-menu volontairement limité à « Dossier… » et « Fichier texte… », sans
  fichiers HTML, fichiers vides génériques ni liens ;
- création des fichiers texte sans écrasement d’un nom déjà présent ;
- libellé Dolphin « Ouvrir un terminal ici », raccourci affiché Alt+Maj+F4 et
  icône de terminal fournie par le thème KDE.

## 1.0.0-rc29

- suppression de la page Métadonnées de Configuration ;
- choix contextuel « Enregistrer dans le fichier lorsque le format le permet »
  directement dans l’éditeur de métadonnées ;
- bouton de suggestion rendu compact et aligné avec ce choix ;
- aides secondaires déplacées vers des boutons d’information KDE natifs,
  accessibles au survol, au clavier et au clic ;
- avertissements, conflits, destinations et confirmations conservés visibles.

## 1.0.0-rc28

- suppression du menu Analyse et des commandes de mesure, de complétion et
  d’écriture des débits vidéo ;
- lecture rapide du débit déclaré par le média, sans décodage complet et sans
  modification du fichier ;
- déplacement du calcul de durée totale des dossiers dans Organiser ;
- menu Opérations limité au suivi, à l’historique, à la reprise et à l’arrêt
  des tâches en arrière-plan ;
- suppression de la page de configuration consacrée à l’enregistrement des
  débits et retrait automatique des anciennes tâches devenues incompatibles.

## 1.0.0-rc27

- menu Analyse recentré sur les informations, les débits vidéo et la durée
  des dossiers ;
- suppression d’un traitement expérimental trop long et de toutes ses données
  associées ;
- anciennes tâches devenues incompatibles automatiquement retirées de la reprise.

## 1.0.0-rc24

- retrait du diagnostic subjectif des vidéos, de sa configuration, de sa
  colonne, de ses commandes et de ses traitements en arrière-plan ;
- anciens profils de colonnes acceptés sans réafficher l’emplacement retiré ;
- maintien des analyses objectives : intégrité, métadonnées, débits,
  durées et doublons exacts.

## 1.0.0-rc23

- fenêtre Propriétés organisée en onglets Général et Droits d’accès pour un
  élément local sélectionné ;
- réglage simplifié des droits du propriétaire, du groupe et des autres ;
- option « Autoriser l’exécution du fichier en tant que programme » pour les
  fichiers ordinaires ;
- éditeur avancé des neuf droits Unix lecture, écriture et exécution ;
- affichage du propriétaire et du groupe, sans modification implicite de
  l’appartenance ;
- application vérifiée des droits et message explicite lorsque le système de
  fichiers, ses options de montage ou les privilèges refusent le changement ;
- refus de modifier silencieusement la cible d’un lien symbolique.

## 1.0.0-rc22

- remplacement de la note absolue sur 100 par un diagnostic prudent et
  explicable : aucun défaut important, défauts légers, dégradation probable ou
  résultat incertain ;
- présentation séparée de la netteté, du bruit, de la compression, des bandes
  de couleur, du contraste et de la stabilité temporelle ;
- indication d’une confiance faible, moyenne ou élevée selon la couverture et
  la cohérence des images analysées ;
- analyse entièrement locale, sans VMAF, service distant, modèle téléchargé ni
  nouvelle dépendance ;
- suppression des profils et pondérations personnalisées devenus trompeurs ;
- invalidation automatique des anciennes notes.

## 1.0.0-rc21

- remplacement des poids chiffrés par cinq niveaux qualitatifs, de « Ignoré »
  à « Prioritaire », avec un curseur et un résumé immédiatement lisible pour
  chaque critère ;
- affichage des réglages recommandés du profil Standard sous forme verrouillée ;
- choix explicite de la profondeur : Rapide, Légère, Équilibrée, Précise,
  Approfondie ou Maximale, de 5 à 30 images ;
- retrait complet de la définition du calcul de qualité perçue : elle reste une
  donnée technique affichée, sans pouvoir avantager ni pénaliser une vidéo ;
- invalidation des anciennes analyses à la suite de ce changement de méthode.

## 1.0.0-rc20

- nouvelle page « Qualité estimée » dans Configuration, avec profils Standard
  et Personnalisé ;
- activation individuelle et pondération du détail, du bruit, de la
  compression, du contraste, de la définition et de la cadence ;
- choix de 5, 10, 15, 20, 25 ou 30 images et normalisation automatique des
  poids actifs ;
- confirmation avant invalidation des anciennes notes et suppression des deux
  commandes rapide/normale au profit d’une commande d’analyse unique ;
- signature du profil enregistrée avec chaque résultat afin d’empêcher la
  réutilisation d’une note calculée avec un autre barème.

## 1.0.0-rc19

- icônes sémantiques du thème KDE pour les dossiers personnels XDG : Bureau,
  Documents, Téléchargements, Musique, Images, Vidéos, Modèles et Public ;
- prise en charge de la clé `Icon` des fichiers `.directory`, comme Dolphin ;
- même résolution d’icône dans les deux panneaux et dans tous les modes
  d’affichage, avec repli sur l’icône de dossier du thème actif.

## 1.0.0-rc18

- prise en charge de l’interface standard `org.freedesktop.FileManager1` utilisée
  par les navigateurs pour « Afficher dans le dossier » et sélectionner le
  fichier téléchargé ;
- activation D-Bus utilisateur uniquement lorsque Mirivue est le gestionnaire
  de fichiers par défaut, sans conflit de paquet avec Dolphin ;
- prise en charge explicite de QtDBus dans le diagnostic et le contrôle des
  dépendances.

## 1.0.0-rc17

- icônes des fichiers déterminées par leur véritable type MIME et fournies par
  le thème KDE, avec l’icône générique uniquement comme dernier repli ;
- bouton « Corbeille » affiché dans la barre de chemin en mode boutons pour
  l’emplacement virtuel `trash:/`.

## 1.0.0-rc16

- ouverture de la Corbeille comme emplacement virtuel KIO `trash:/`, sans
  exposer son dossier interne dans la barre de chemin ;
- restauration et suppression définitive confiées aux tâches KIO natives afin
  de préserver l’emplacement d’origine et le comportement de Dolphin ;
- catégories du lanceur complétées avec `System` et `FileTools`, conformément
  au contrôle `desktop-file-validate`.

## 1.0.0-rc15

- déclaration native comme gestionnaire de fichiers pour KDE Plasma avec le
  type MIME `inode/directory` ;
- acceptation des chemins locaux et des URL transmises par Plasma grâce au
  paramètre `%U` du lanceur ;
- ouverture directe des URL KIO, notamment la corbeille, SMB, SFTP et MTP,
  au démarrage comme dans une instance déjà ouverte ;
- vérification automatique de la déclaration KDE pendant le contrôle de
  l’installation.

## 1.0.0-rc14

- suppression de « Nettoyage guidé », qui ne faisait que résumer des données
  déjà disponibles et pouvait rendre l’interface instable ;
- intégration des erreurs et de la taille minimale à la recherche unifiée ;
- véritable recherche récursive de doublons exacts, suivie d’un bouton explicite
  pour choisir les fichiers à conserver ;
- comparaison SHA-256 complète conservée, avec nouvelle vérification avant
  toute mise à la corbeille.

## 1.0.0-rc13

- vérificateur unifié pour les installations système gérées par `pacman` et
  les installations utilisateur classiques ;
- contrôle du paquet installé, des cinq assistants KIO recompilés et de
  l’absence d’un lanceur utilisateur masquant l’entrée système.

## 1.0.0-rc12

- correction de l’empaquetage CachyOS/Arch : seuls les cinq exécutables KIO
  sont installés, sans inclure les répertoires CMake `_autogen` ;
- contrôle automatisé interdisant le retour du motif ambigu
  `mirivue-kio-*` pendant l’installation du paquet.

## 1.0.0-rc11

- réintégration des sources exactes des cinq assistants KIO ;
- licence MIT explicitée pour le code natif ;
- compilation des assistants par le paquet CachyOS/Arch avec CMake et Ninja ;
- suppression du dernier obstacle à une construction publique reproductible.

## 1.0.0-rc10

- suppression de la seconde règle de style qui était réappliquée au bouton de
  débordement lors du rafraîchissement du thème Plasma ;
- rendu natif garanti au démarrage, au redimensionnement et après un changement
  de palette.

## 1.0.0-rc9

- suppression de la feuille de style refusée par Qt 6.11 sur le bouton de
  débordement de la barre d’outils ;
- retour au rendu natif du thème Plasma pour ce bouton et ses surbrillances.

## 1.0.0-rc8

- gel des nouvelles fonctionnalités et début de la consolidation 1.0 ;
- test graphique réel de la fenêtre avant remplacement de la version installée ;
- conservation d’une version précédente et commande `--rollback` ;
- déclaration des versions Python et PySide6 compatibles ;
- premiers tests d’interface Qt et scénarios de démarrage ;
- centralisation progressive du suivi des tâches en arrière-plan ;
- nettoyage des outils de validation de la version destinée aux utilisateurs.
- point d’accès unique « Opérations » pour les analyses et les transferts ;
- clés de configuration séparées des textes traduisibles ;
- validation renforcée des archives et écritures durables après remplacement ;
- script autonome de vérification de l’installation et matrice de stabilisation ;
- modèle de paquet local CachyOS/Arch.

## 1.0.0-rc7

- réorganisation complète de la barre de menus ;
- intégration des critères multimédias à la recherche unique ;
- clarification des libellés et des états dynamiques des actions.

