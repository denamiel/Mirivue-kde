# Correctifs RC192

- Filtre de noms actualisé uniquement quand il change ; API Qt récente avec
  compatibilité ancienne conservée.
- Miniatures du panneau inactif appliquées sans synchroniser toute l’interface.
- Index des chemins et compteur de médias incomplets entretenus par le modèle,
  pour supprimer les recherches et recomptages complets par résultat/sélection.
- Instructions de gel actuelles, changelog classé, point d’entrée des documents.

Treize nouveaux tests : onze de traitement et deux de documentation. Les défauts
sont reproduits sur RC191 ; le contrôle des résultats périmés préserve une
protection déjà correcte. 134 tests ciblés passent trois fois ; la suite
intégrale et Plasma ne sont pas déclarés validés ici. Voir VALIDATION-RC192.md.
