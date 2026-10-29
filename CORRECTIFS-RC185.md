# Correctif RC185

Un test de tests/test_ergonomics_gui.py attendait l'ancienne liste des groupes
de la page Général. Il inclut désormais Affichage. Une seule valeur attendue
est ajoutée ; l'égalité exacte et toutes les autres assertions restent.

Les fichiers applicatifs sont identiques à RC184, sauf la version dans
mirivue/__init__.py ; les fichiers natifs sont identiques. Les références de
version des scripts et des documents sont mises à jour.

La reproduction et les limites sont détaillées dans VALIDATION-RC185.md.
Le test complet avec son setUp natif n'a pas été rejoué ici ; son corps a été
reproduit avec le formulaire réel et un contrôleur isolé. Les onze contrôles
ciblés réussissent trois fois.
