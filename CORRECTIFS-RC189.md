# Correctif RC189

Une seule attente du contrôle graphique est corrigée : le titre de la rubrique
est Configurations de colonnes, et non Colonnes. L'expression reste une égalité
exacte. Aucun autre contrôle du parcours n'est retiré.

La recherche réelle, les réglages et l'affichage restent inchangés. Les sources
C++ sont identiques à RC188. Un test sans Qt détecte la divergence entre le
libellé réel et la condition de validation ; il échoue avant et réussit après.
Dix tests ciblés passent trois fois. La suite complète n'est pas rejouée ici.

Le journal utilisateur prouve la compilation complète RC188 et son arrêt avant
installation. Voir VALIDATION-RC189.md pour la portée exacte des résultats.
