# Correctifs RC191

- Les sous-processus des tests trouvent le code de l’archive sans dépendre
  d’un PYTHONPATH de développement ni d’une ancienne installation.
- Les menus retirent les références aux actions partagées avec removeAction
  et ne les invalident plus avec clear(). Le test Tab/Maj+Tab fonctionne dans
  les trois vues ; un test supplémentaire reproduit les actions créées par
  QMenu.addAction, absentes des premières fixtures RC190.

81 tests ciblés passent trois fois ; le moteur natif a été recompilé pour les
essais des vues et du clavier. La suite intégrale et Plasma restent à valider
sur CachyOS. Voir VALIDATION-RC191.md pour les preuves et la portée exacte.
