# Récupération de Mirivue KDE 1.0.0 RC193

## Originaux des médias modifiés

À la première modification d’un fichier, Mirivue conserve à côté de celui-ci
`film.mkv.mirivue-original`, avec les données d’avant toute modification par
cette version de Mirivue. Les modifications suivantes réutilisent cet original
sans le remplacer. Un fichier caché `.film.mkv.mirivue-backup.json` relie cet
original au fichier courant ; ne le supprimer ni le modifier. Le premier
original reste une copie complète qui prend la place du média après son
remplacement, même si sa création par lien matériel a été immédiate.

Depuis la RC151, le suivi compare la taille, la date de modification et une
empreinte de trois zones du contenu (début, milieu, fin). Il ne dépend plus
du numéro de périphérique ou d’inode après un remontage. Cette empreinte
partielle n’est pas une vérification intégrale du média : deux fichiers
distincts pourraient partager ces échantillons. Une modification extérieure
de la date peut aussi imposer une reprise manuelle.

Les sauvegardes antérieures portant les noms `.mirivue-original-<identifiant>`
ou `.mirivue-original.bak` (éventuellement numérotées) sont conservées. Elles
peuvent représenter des versions différentes : Mirivue ne les choisit pas
automatiquement comme original initial et ne les supprime jamais. Pour les
repérer, afficher les fichiers cachés et chercher `mirivue-original` dans le
dossier du média. Vérifier le contenu et la date de chaque copie avant toute
restauration manuelle. Ne jamais écraser le fichier courant sans en conserver
une copie distincte.

Si Mirivue signale que le fichier courant ne correspond plus à son original,
le chemin a pu être repris par un autre média ou le suivi a pu être interrompu.
Les deux fichiers sont conservés ; les examiner et archiver ensemble la
sauvegarde et son fichier de suivi avant d’effectuer une nouvelle écriture.
Pour repartir explicitement avec le fichier présent, fermer Mirivue puis,
dans Dolphin et après vérification des contenus, renommer
`film.mkv.mirivue-original` en `film.mkv.mirivue-original-archive-AAAA-MM-JJ`
et `.film.mkv.mirivue-backup.json` en
`.film.mkv.mirivue-backup-archive-AAAA-MM-JJ.json` (avec la même date).
La prochaine modification créera une nouvelle sauvegarde de `film.mkv` ; les
deux fichiers archivés restent en place. Ne pas adopter une ancienne sauvegarde
en ne vérifiant que la taille et la date. Une fiche créée par la RC150 migre
automatiquement seulement si ses anciens identifiants correspondent encore.

Renommer ou déplacer un média ne déplace pas automatiquement son original et
son fichier de suivi. Les retrouver dans le dossier précédent avant de
modifier le média à son nouvel emplacement ; les conserver ou les archiver
ensemble selon la procédure ci-dessus.

## Installation par paquet CachyOS / Arch

Fermer Mirivue, puis réinstaller un paquet précédent réellement conservé sur
votre machine avec `sudo pacman -U /chemin/vers/paquet-precedent.pkg.tar.zst`.
Vérifier ensuite la version et le lancement. La sauvegarde du paquet dépend de
votre cache `pacman` ou de vos archives personnelles : Mirivue n'en crée pas une
pour le mode paquet. Cette opération ne vise pas les fichiers personnels.

## Installation utilisateur

Fermer complètement Mirivue, y compris son icône de zone de notification, puis
exécuter `./Installer.sh --rollback` depuis les sources RC193 extraites.
L'installateur conserve une seule version utilisateur précédente dans
`~/.local/share/mirivue-kde-previous`. La commande échoue si aucune version
précédente n'a été conservée. Elle ne s'applique pas au paquet `pacman`.

Après une installation ou une restauration, exécuter
`./Verifier-installation-RC193.sh` depuis le dossier extrait si la version
installée est la RC193. Pour une version antérieure, utiliser son propre
vérificateur ou vérifier directement `mirivue-kde --version`.

Journaux locaux : `~/.local/state/mirivue/dernier-lancement.log`,
`~/.local/state/mirivue/mirivue.log` et
`~/.local/state/mirivue/derniere-mise-a-jour.log`.

## Désinstaller le paquet CachyOS / Arch

Fermer Mirivue, puis exécuter `./Desinstaller-paquet-CachyOS.sh` depuis
l'archive extraite, sous le compte utilisateur habituel. Le script appelle
`sudo pacman -R mirivue-kde` si le paquet est présent, puis supprime le service
FileManager1 de **ce compte** uniquement s'il porte la marque de Mirivue et
pointe vers son lanceur. Il ne supprime pas les préférences ni les médias.
Après un `pacman -R` lancé séparément, exécuter ce même script pour nettoyer
le service résiduel. Chaque autre compte utilisateur doit faire son propre
nettoyage s'il a lancé Mirivue en tant que gestionnaire par défaut.
