# Audit de préparation à Mirivue KDE 1.0 stable

Audit du 12 novembre 2026. Base : main
`faa828e0929dd91d3fe439a05b25048e7ebbe38b` (1.0.0-beta.6).
Candidat préparé : **1.0.0**, dans la [PR #28](https://github.com/denamiel/Mirivue-kde/pull/28).
Aucune publication ni fusion effectuée. Les fonctions sont gelées.

## Ce que l'audit a produit

La PR #26 a corrigé les critères et les notices, dont les deux composants MIT
manquants dans l'index des 23 fichiers natifs. La PR #27 a corrigé les deux
incidents KIO connus : Corbeille `desktop:/` et annulation d'une confirmation
sans perdre l'historique. La PR #28 cumule ces modifications sans fusion de
ces PR, rétablit le scan après renommage KIO d'un dossier et complète les
preuves de sortie.

La suite intégrale a révélé des assertions devenues obsolètes et des attentes
asynchrones absentes. Les assertions de résultat ont été conservées : contenu,
focus, sélection, fermeture effective et rafraîchissement restent exigés.
Les tests des confirmations KDE sont aussi exécutés avec un dialogue visible.

Les premiers contrôles d'images avaient masqué une commande absente derrière
`tee` : ces faux verts ne sont pas comptés. Le code d'échec est désormais
propagé et un contrôle négatif vérifie cette propriété. La comparaison des
permissions Wayland attend la fin d'udev, sans changer les permissions de l'hôte.

La campagne média a ensuite reproduit un arrêt natif dans
`QGstreamerMediaPlayer::setAudioOutput`. Les dépendances GStreamer « good »
manquaient au paquet. Elles sont désormais explicites sous Fedora/Arch et
vérifiées par l'installateur source. La lecture avec le même backend est réussie.
Le pilote vérifie le PID sur le client PipeWire lorsque le flux natif n'en
répète pas les propriétés ; les états audio sont conservés en artefacts.

## Preuves acquises

Campagne fonctionnelle `4f4dac0`, avant le changement d'identité de version :

- Trois suites intégrales consécutives : **139 suites, 818 tests à chaque passe**,
  aucun échec. Le seul test refusant root est effectivement rejoué sous le
  compte jetable ; aucun test non couvert n'est accepté.
- RPM Fedora 44/45/Rawhide, Python 3.11/3.x, Arch, X11 et Wayland réussis.
- Opérations réelles ext4 et NTFS3 avec contrôle des contenus, conflit annulé,
  Corbeille/restauration, nom exact et lien préservés.
- Cycles de paquets et témoins de données/configuration préservés.
- Aperçus image/PDF et lecture audio/vidéo par les paquets installés ; flux
  PipeWire, pause/reprise, son vidéo et sessions de 600 secondes Fedora/Arch.
- Prototype de la PR #14 réutilisé pour une session Plasma complète : image
  officielle vérifiée, RPM exact hors ligne, Wayland natif, FileManager1,
  création de dossier au clavier, propriétaire et témoin contrôlés. Aucun
  changement des permissions KVM de l'hôte ; aucune fusion de #14.

Détail, liens et limites : [VALIDATION-1.0.md](VALIDATION-1.0.md).
Les 19 essais Plasma historiques restent des preuves historiques ; ils ne
sont ni annulés ni redemandés à l'utilisateur.

## Décision de sortie

Les défauts démontrés sont traités et la campagne fonctionnelle est acquise.
Le paquet portant l'identité **1.0.0** doit réussir la même qualification,
avec mise à jour/retour arrière depuis la bêta 6 actuellement publiée.
La PR #28 consigne le commit final et les résultats de cette campagne avant
la décision de fusion/publication. Aucun résultat n'est anticipé.

Les nouveaux jobs sont seulement classés informatifs dans le vérificateur :
les six contrôles requis et les protections effectives sont inchangés.
Aucun appel d'application des protections n'est effectué.

La comparaison Claude
[43272225925](https://github.com/denamiel/Mirivue-kde/actions/runs/43272225925)
a échoué sur les deux voies `invalid_request`. Cette méthode reste arrêtée ;
elle ne conditionne pas la sortie du produit. Les autres PR d'infrastructure
ne sont pas des fusions nécessaires à la version stable.

Tout le travail et les nouvelles validations sont réalisés dans le cloud,
sans opération sur les ordinateurs personnels, publication ou modification de secrets.
