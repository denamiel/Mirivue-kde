# Ouvertures externes — RC181

Implémentation originale de Mirivue, comparée à Dolphin v26.08.2. Les réglages
restent ceux de Mirivue ; cette correction ne change pas les valeurs existantes.

- Le routage d'une fenêtre vivante utilise des appels D-Bus asynchrones Qt.
- Le budget global est de 1 500 ms pour découverte, interrogation et envoi,
  avec une échéance monotone. Les réponses tardives sont ignorées.
- Avant la création de la première fenêtre, le lanceur attend ce même échange
  asynchrone dans une boucle Qt sans entrées utilisateur ; les minuteries Qt
  continuent à être traitées. Aucun bus.call bloquant n'est utilisé par le routage.
- Un échec après une acceptation ne répète que les emplacements restant à livrer.
- Si une réponse manque après un envoi Dispatch, l'état est incertain : le
  destinataire peut avoir accepté. Cet envoi n'est jamais répété automatiquement.
  C'est une garantie contre les doublons, pas une garantie « exactement une fois »
  ni la preuve que la fenêtre destinataire a déjà terminé son ouverture.
- Si le bus de session est absent, les chemins de secours existants restent
  disponibles. La recherche parmi toutes les fenêtres n'est alors pas garantie.

## Validation des entrées

Ces bornes sont propres à Mirivue, pas à Dolphin : 1 Mio de JSON UTF-8 par message,
100 emplacements, 10 000 fichiers sélectionnés au total et 32 768 octets UTF-8
par chaîne (chemin, URL, fichier, jeton). La borne de chaîne permet les URL réseau
longues tout en limitant l'allocation de mémoire ; celle du message est prioritaire.

Locations doit être une liste non vide de dictionnaires folder/files ; folder
et chaque fichier sont des chaînes sans caractère NUL. Les quatre options split,
force_tabs, properties et activate_first sont de vrais booléens. Le jeton est
une chaîne. Les clés inconnues et detached_tab sont rejetées sur Dispatch.
Une URL mal formée ou un JSON trop profond sont rejetés sans exception sortante.
Le détachement de Mirivue conserve sa voie séparée --session-tab.

La normalisation produit une copie typée avant mise en file. L'interface du bus
reste accessible aux autres processus du même utilisateur/de la même session,
comme une interface d'ouverture de gestionnaire de fichiers. Elle n'est pas un
mécanisme d'autorisation à lancer des commandes shell.
