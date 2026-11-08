# Mirivue TestLab — validation des évolutions futures

> État : **proposition en PR brouillon**, pas encore de banc graphique complet.
> Ce projet ne relance **pas** la campagne de 19 essais manuels de la bêta 5.

## Finalité

Pour chaque future évolution de Mirivue KDE, obtenir une preuve reproductible :
tests pertinents, capture d'écran en cas d'échec, journaux des assistants KIO,
résultats d'installation des paquets et distinction explicite entre simulation
et session Plasma réelle. Réduire au strict minimum les vérifications manuelles.

## Capacités déjà présentes sur main (8 novembre 2026)

| Niveau | Déjà disponible | Portée réelle |
|---|---|---|
| A — Python/Qt | Tests PySide6, QtTest, services simulés | Logique et widgets |
| B — KIO natif | Tests avec assistants KIO compilés depuis le RPM | Opérations isolées |
| C — Installation | RPM Fedora 44/45/Rawhide, paquet Arch | Construction et démarrage |
| D — Bureau réel | Non garanti par les workflows existants | Plasma, Wayland, menus/focus/drag-and-drop |
| E — Matériel | Non garanti | Disques externes, NTFS, coupures, intégration à la session |

Les contrôles Fedora existants utilisent notamment `QT_QPA_PLATFORM=offscreen`.
Ils ne sauraient être présentés comme une validation complète de Wayland/Plasma.

## Contrat de validation d'une future PR

Chaque PR affectant le comportement utilisateur doit contenir :

1. **Scénario** : action, résultat attendu, données jetables nécessaires ;
2. **Niveau** : A/B/C/D/E ci-dessus et environnement exact ;
3. **Preuve automatique** : chemin des tests, résultat CI, journaux et captures ;
4. **Limites** : ce qui n'a pas été exécuté et pourquoi ;
5. **Impact** : refus de fusion si le test obligatoire échoue, sauf dérogation documentée.

Les tests nouvellement ajoutés deviennent des tests permanents. Il ne faut
pas demander à l'utilisateur de recommencer les anciens essais à chaque bêta.

## Réalisation progressive

- **Phase 1 — inventaire** : recenser les suites existantes et les regrouper par
  comportement, établir une matrice de couverture sans prétendre rejouer les
  campagnes historiques.
- **Phase 2 — harness graphique isolé** : HOME, XDG_*, corbeille, dossier
  d'essai et D-Bus distincts ; délais maximum ; restauration/effacement des
  seules données jetables ; artefacts de diagnostic même en cas d'échec.
- **Phase 3 — vraie fenêtre de l'application empaquetée** : installer un RPM
  testé, démarrer une session X11/Xvfb et piloter le programme réel avec QtTest
  et les interfaces natives plutôt que des clics par coordonnées ; captures
  des boîtes de dialogue, vérifications d'état et de fichiers.
- **Phase 4 — différence Plasma/Wayland** : valider sur une machine virtuelle
  éphémère Fedora KDE ; évaluer un runner isolé pour CachyOS. Les variantes
  NTFS/périphériques/smb/sftp sont séparées, jamais supposées couvertes.
- **Phase 5 — intégration CI** : rapports JUnit, captures et journaux en
  artefacts GitHub ; exigences bloquantes sur PR ; aucune publication automatique.

## Sécurité non négociable

- Ne jamais exécuter une PR non fiable sur la session personnelle du propriétaire.
- Aucun accès au $HOME réel, à la vraie corbeille, aux disques personnels ou aux
  secrets de signature/COPR dans les tests.
- Aucun service SSH permanent ou runner auto-hébergé non isolé n'est requis.
- Les workflows `publish` COPR/Arch/Pacman restent entièrement inchangés.
- Les captures et journaux ne doivent pas contenir d'informations personnelles.

## Critères de validation de TestLab

Un cas de succès produit une preuve explicite et laisse le système de test propre ;
un cas d'échec provoque un statut CI non nul et conserve les diagnostics ;
les deux chemins sont testés. Définir une limite de temps pour éviter tout job
bloqué et documenter les cas non automatisables.

Suivi du chantier : [issue #8](https://github.com/denamiel/Mirivue-kde/issues/8).
