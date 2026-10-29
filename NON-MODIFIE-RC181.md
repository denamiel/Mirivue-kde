# Périmètre volontairement conservé — RC181

- Session/dossier de démarrage : choix exclusifs conservés. Dolphin v26.08.2
  utilise aussi deux boutons radio exclusifs (folderstabssettingspage.cpp:53,92).
- Installations existantes : leur choix d'ouverture en onglets est préservé.
- kservicemenurc reste partagé ; la page explique toujours cette portée.
- Gras de l'aperçu du renommage, outils et colonnes médias conservés.
- Les dates de la colonne Année/date viennent de la balise générale date
  (media.py:13, COLUMNS[22]), pas d'un rôle releaseYear : pas de conversion forcée.
- Durée, FPS, débits, canaux, fréquence et profondeur audio restent numériques.
  Ce sont des règles Mirivue, pas une promesse d'identité de tous les rôles Baloo.
- Emplacement d'origine et autres colonnes techniques gardent leurs comparateurs
  actuels ; aucune colonne dormante n'est réintroduite. Voir PARITE-DOLPHIN.md.
- Le dossier local absent d'une session peut encore être remplacé par le dossier
  personnel. Pas de nouveau mécanisme de récupération de disque amovible.
- Sauvegarde de session à la fermeture : pas de nouvelle autosauvegarde continue,
  pas de restauration multi-fenêtre. La dernière sauvegarde reste la référence.
- Pas de nouveau délai pour le test de démarrage : huit secondes conservées.
  Le dépassement de l'audit n'a pas été reproduit dans vingt reprises RC180 ;
  seule une trace diagnostique est ajoutée, sans annoncer sa cause résolue.
- Aucun changement des couleurs, polices, raccourcis, menus principaux ou moteur
  de vues. La modification visuelle se limite aux suffixes de la page des services.
- Les noms génériques fournis par les services KDE (Installer…, Définir comme…)
  ne sont pas devinés/reformulés. Des homonymes peuvent rester, comme chez Dolphin ;
  les identifiants internes distinguent leurs cases, sans être ajoutés au texte.
- Les mentions RC180 et antérieures du CHANGELOG sont historiques et conservées.
- Aucun téléchargement, aucune installation de service tiers, aucune installation
  pacman ni validation de bureau Wayland/Plasma réel n'ont été réalisés ici.

- Raccourcis et configuration de barre d'outils conservés dans ce périmètre :
  F10 ouvre toujours les menus dans Mirivue (menu_visibility.py:38 et app.py:2354).
  Ce correctif ne constitue pas une nouvelle vérification de sa parité avec Dolphin.
- Avertissements préexistants de dépréciation invalidateFilter() et retour de
  write() dans job-progress.cpp : pas de nettoyage général hors des sept points.
- La validation locale des dossiers conserve is_browsable_location() : les
  contrôles d'existence du système de fichiers ne sont pas déplacés vers un
  nouveau service. Le budget de routage borne les attentes D-Bus ; il n'est pas
  une garantie de temps réel pour tous les appels au système de fichiers.
