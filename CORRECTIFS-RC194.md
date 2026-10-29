# Correctifs RC194

Les trois blocages de menus sont reproduits avec Qt 6.11.2 et le code
KHamburgerMenu de KDE 6.30.0 : les tests attendaient le retour d’un appel
qui pouvait attendre lui-même la fermeture du menu. Les vérifications se font
désormais depuis la boucle Qt ; aucun délai ni assertion n’est supprimé.

Le bus privé préfère le transport Linux Unix avec authentification EXTERNAL.
Le repli TCP anonyme ne sert qu’aux environnements qui interdisent Unix.
Les variables D-Bus d’activation héritées sont retirées pour les sous-processus
de ce test. En cas de refus, le diagnostic contient l’état connecté et lastError.
La cause exacte sur Fedora n’est pas prouvée par le résumé fourni : ce changement
est une correction de fidélité du banc, pas une garantie de résolution sur Fedora.

Valider conserve les journaux complets et le code de sortie même après l’effacement
des répertoires temporaires. L’installation reste bloquée si la validation échoue.
Le code applicatif et les sources natives n’ont pas été modifiés.
