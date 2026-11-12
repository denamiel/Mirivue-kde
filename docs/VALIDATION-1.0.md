# Qualification de Mirivue KDE 1.0

Version préparée : **1.0.0**, 12 novembre 2026. Aucun paquet n'est publié par
cette préparation. La [PR #28](https://github.com/denamiel/Mirivue-kde/pull/28)
conserve les références exactes du candidat et des contrôles du paquet final.
Les fonctions restent gelées.

## Corrections retenues

- Corbeille `desktop:/` : toutes les sources sont résolues avant la première
  opération ; une source introuvable fait refuser le lot. Le nom exact et le
  lien symbolique sont conservés.
- Annulation d'une confirmation KDE : le dialogue de l'opération est fermé,
  le service KIO reste vivant et l'historique d'annulation précédent est conservé.
- Renommage KIO d'un dossier : le volet d'origine est rafraîchi.
- Lecteur : les paquets fournissent les plugins GStreamer « good » requis par
  le backend choisi par le lanceur. L'installateur source contrôle ses sorties.
  Le défaut avait produit un signal 11 dans `QGstreamerMediaPlayer::setAudioOutput`.
  Le même backend a ensuite réussi la campagne ; aucun remplacement de backend
  n'a servi à transformer l'échec en réussite.
- Index MIT des composants natifs complété et documents de sortie harmonisés.

## Campagne fonctionnelle avant versionnement

Référence : `4f4dac082e514d0b47bff6ee951304ccd29dbcc0`, encore marquée bêta 6.
Toutes les nouvelles exécutions ont lieu dans le cloud, sur données jetables.

| Contrôle | Résultat lu |
|---|---|
| Suite intégrale Fedora 45 | Trois passes consécutives, **139 suites et 818 tests par passe**, aucun échec ni suite vide. Le seul test intentionnellement ignoré sous root est rejoué avec succès sous le compte jetable, dans un journal identifié. |
| RPM | Compilation native neuve, installation, contrôle des guides, lancement et régressions Fedora 44/45/Rawhide réussis. Rawhide reste informatif. |
| Arch | Paquet construit sans privilèges, installation et cycle de mise à jour/retour arrière réussis. |
| ext4 et NTFS3 | Images réellement formatées et montées sous le type demandé ; copie/déplacement avec empreintes, conflit annulé sans écrasement, Corbeille/restauration, espace final et cible du lien préservés. |
| X11 et KWin virtuel | Fenêtres réelles, scénarios clavier/glisser-déposer et confirmation KDE effectivement visible réussis ; permissions du nœud virtuel inchangées. |
| Médias Fedora 45 | PNG/PDF, WAV et WebM, image vidéo décodée, flux audio actif/non muet identifié par le PID de son client, pause/reprise et son vidéo réactivé ; **600 secondes, 457 cycles**, sortie normale. |
| Médias Arch | Mêmes critères ; **600 secondes, 456 cycles**, sortie normale. Le backend est celui que sélectionne le lanceur installé. |
| Plasma complet | ISO Fedora KDE vérifiée par signature et empreinte, RPM exact installé hors ligne, SELinux actif, Mirivue Wayland natif, interaction FileManager1 et création au clavier. Dossier appartenant à liveuser, témoin intact, captures et nettoyage vérifiés. Aucun changement des permissions KVM de l'hôte. |

Preuves : [Fedora 43297404679](https://github.com/denamiel/Mirivue-kde/actions/runs/43297404679)
et [Arch 43297404639](https://github.com/denamiel/Mirivue-kde/actions/runs/43297404639).
Le premier résultat du prototype Plasma réutilisé est également conservé dans
[43295814988](https://github.com/denamiel/Mirivue-kde/actions/runs/43295814988).
Ce prototype reste informatif ; son exécution ne constitue pas une promotion
ou une mesure de stabilité générale du banc VM.

## Contrôle du paquet versionné 1.0

Le candidat final reprend les mêmes contrôles. Les cycles de paquets démarrent
cette fois de la **bêta 6 publiée, épinglée par SHA-256**, puis passent à 1.0,
reviennent à la bêta 6 et réinstallent 1.0. Chaque étape lance l'application et
vérifie les témoins de données/configuration. Arch exige aussi que `vercmp`
classe 1.0 après la bêta 6 ; RPM utilise `Release: 1` après `0.201.beta6.1`.

La réussite de cette campagne doit être lue sur le commit final de la PR #28
avant toute décision de fusion/publication. Les résultats ci-dessus restent
attribués à leur référence, sans être transférés à un autre commit par anticipation.

Identités préparées : application/Python/AppStream **1.0.0**, RPM **1.0.0-1**,
Arch **1.0.0-1**. L'archive source s'appelle `Mirivue-1.0.0-KDE.tar.gz`.

## Portée et limites

Les 19 essais Plasma utilisateur de la bêta sont conservés dans
[VALIDATION-beta.6.md](VALIDATION-beta.6.md), sans nouvelle campagne demandée.
Le SFTP privé demeure une preuve historique ; SMB n'est pas validé.
Les autres protocoles et systèmes de fichiers non essayés ne reçoivent aucune
qualification par analogie. Les nouvelles cibles sont x86_64.

Les médias sont exercés sur sorties audio virtuelles et rendu vidéo logiciel,
pas sur un périphérique audio physique. La session mesurée dure dix minutes.
Les preuves Plasma portent sur le scénario décrit, avec présence des services
et portails ; elles ne qualifient pas toutes les applications qui les utilisent.

Aucune fusion, publication, modification des protections ou secrets, aucun
appel Claude et aucune exécution sur un poste personnel dans cette préparation.
