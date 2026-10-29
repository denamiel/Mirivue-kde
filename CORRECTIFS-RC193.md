# Correctif RC193

Pour plusieurs fichiers sélectionnés sans dossier, utiliser l’ouverture KDE
KFileItemActions comme Dolphin v26.08.2. Les applications communes et la
sélection complète sont gérées par KDE ; le bloc d’ouverture générique ne fait
plus doublon. Les autres fonctions du menu restent en place.

Sept tests ajoutés ; deux reproduisent l’écart sur RC192. Le pont C++ et une
référence indépendante ont été compilés et comparés avec des associations
jetables. 49 tests ciblés passent trois fois. La suite intégrale et Plasma
restent à valider. Voir VALIDATION-RC193.md pour la portée et les versions.
