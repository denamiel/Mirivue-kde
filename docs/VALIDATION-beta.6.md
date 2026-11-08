# Mirivue KDE 1.0.0-beta.6 — opérations KIO sur l’élément exact

Version visible `1.0.0-beta.6`, Python `1.0.0b6`, révision RPM
`0.201.beta6.1`, paquet Arch/CachyOS `1.0.0beta6-1`.

Cette version reprend les correctifs de la pull request n° 5, fusionnée dans
`main` au commit `d4d5b95`. Le détail des anomalies, des preuves et des essais
figure dans `docs/VALIDATION-C1-H1-H2.md`.

## Contenu

- **C1** — Les assistants natifs n’analysent plus des URL complètes avec
  `QUrl::fromUserInput()`, qui retirait les blancs finaux. Corbeille,
  suppression, renommage, copie, inventaire, fil d’Ariane, Emplacements et
  favoris agissent sur « photo␠ » et non sur « photo ». Une requête contenant
  une source incomplète est refusée en entier.
- **H1** — Les sources ne sont plus résolues : un lien symbolique déposé sur la
  Corbeille, copié ou déplacé reste un lien ; sa cible n’est jamais touchée.
- **H2** — La suppression fonctionne dans les emplacements KIO non locaux.
  « Mettre à la corbeille » n’est proposé que pour les éléments ayant un chemin
  local (règle de Dolphin) ; il est grisé, avec une explication, pour sftp/smb
  et dans la Corbeille. Une mise à la corbeille n’est jamais transformée en
  suppression ; Suppr n’efface jamais définitivement un élément distant.
- Liens symboliques cassés listés comme dans Dolphin, y compris avec une
  extension multimédia.
- Messages d’erreur KIO complets au lieu d’une simple URL.

## Paquets

- Les trois assistants modifiés (`mirivue-kio-service`, `mirivue-kio-transfer`,
  `mirivue-kio-list`) et ceux qui utilisent le nouvel utilitaire
  `native/location-url.h` (`mirivue-kio-places`, `mirivue-kio-open`,
  `libmirivue-kio-places-widget.so`) sont recompilés depuis les sources par le
  spec Fedora et le `PKGBUILD`.
- Les révisions sont strictement supérieures aux précédentes :
  RPM `1.0.0-0.201.beta6.1` > `1.0.0-0.200.beta5.3` ;
  Arch `1.0.0beta6-1` > `1.0.0beta5-3`.
- Comportement des mises à jour inchangé : aucun scriptlet RPM ni fichier
  `.install` Arch n’est ajouté. L’installateur utilisateur historique
  (`Installer.sh`) refuse toujours la mise à jour lorsque Mirivue est ouvert ;
  l’application garde son verrou d’instance unique.

## Validation

- Suite permanente `tests/test_c1_h1_h2_regressions.py` : 49 tests, exécutés
  par la CI Fedora 44, 45 et Rawhide avec les assistants installés par le RPM
  construit.
- Non-régression locale : 100 suites existantes sans différence avec la
  beta.5 dans les mêmes conditions.
- Essais manuels Fedora 45 / KDE Plasma : 19 essais réussis selon le retour de
  l’utilisateur sur la pull request n° 5, après le correctif des liens cassés.
- SFTP vérifié sur un serveur local privé ; SMB non vérifié sur un serveur.

## Limites

- Déposer une ligne `desktop:/` sur un panneau Corbeille transmet son URI à KIO :
  faux échec possible, l’élément étant tout de même mis à la Corbeille.
- Annuler pendant qu’un dialogue de confirmation KDE est ouvert relance le
  service de transferts et efface l’historique d’annulation (comportement
  antérieur).
- `native/clipboard-paste.cpp` et `native/file-properties.cpp` restent absents
  de l’index MIT de `LICENCES-TIERS.md` (défaut antérieur).
