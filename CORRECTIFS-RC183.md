# Correctif RC183

- Défaut : le contrôle natif conclut trop tôt à un refus de rétrécissement et
  valide un chemin vide. La fragilité est reproduite avec une réponse différée.
- Correctif minimal : mirivue/ui_contract.py attend l'exposition puis la réponse
  au redimensionnement ; initialise un dossier temporaire ; conserve les erreurs
  réelles avec diagnostic des minima. Aucun changement des contraintes Qt.
- Tests : tests/test_native_contract_timing.py et son processus isolé
  tests/helpers/native_contract_peer.py. Réponse différée : réussite ; refus
  réel : détection maintenue ; aucune URL vide envoyée à KIO.
- Les deux tests échouent contre RC182 puis réussissent contre RC183.
- Version, références des scripts, paquet et documents mis à jour. Réglages,
  opérations, partage de kservicemenurc et comportement Dolphin inchangés.
- Les durées et limites sont dans VALIDATION-RC183.md ; le diff et les sorties
  brutes sont dans validation/RC183. Aucune validation Wayland n'est prétendue.
