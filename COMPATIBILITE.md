# Compatibilité de Mirivue KDE 1.0.0 RC193

L'interface de cette candidate 1.0 est en français uniquement. Le brouillon
anglais n'est pas proposé dans les paramètres ; la langue du bureau continue
de régler les formats Qt du système hors des libellés propres à Mirivue.

## Environnement et dépendances

La cible de référence est CachyOS / Arch Linux, KDE Plasma 6, Qt 6 et KF6,
avec une session Wayland. Le paquet accepte Python 3.11 à 3.14 et PySide6 6.8
ou version 6 ultérieure, avec Shiboken6 compatible. Il dépend également de
QtMultimedia, QtPdf, Pillow, Mutagen, KIO/KF6, Ark, FFmpeg/FFprobe, MediaInfo,
7z, unar ou unrar, ExifTool et MKVToolNix. Konsole est facultatif pour le
panneau Terminal intégré.

Le moteur des fichiers est désormais compilé dans `libmirivue-dolphin-view.so`.
Il intègre les sources de Dolphin 26.08.2 et requiert les composants KF6
GuiAddons, IconThemes, WidgetsAddons, TextWidgets, I18n, Config, ColorScheme, CoreAddons, NewStuff et
KIO déjà fournis par les paquets KDE. Ces dépendances sont déclarées directement
par le paquet. Il n’impose aucune version du paquet Dolphin ni de sa bibliothèque
privée. Les couleurs et les polices restent fournies par Qt/KDE.

Le modèle Qt intermédiaire `libmirivue-item-presentation.so` reste utilisé
pour les interfaces existantes de tri et de métadonnées. Les vues ne sont plus
QTableView/QListView : une seule scène native sert aux trois modes de chaque
panneau. Un QHeaderView caché reprend les anciens réglages de colonnes ; il ne
dessine pas les fichiers. Le moteur KDE est requis, sans remplacement silencieux
par l’ancienne vue Python si sa bibliothèque manque.

La matrice de compatibilité historique ne constitue pas un essai de cette
refonte sur toutes les distributions : les bibliothèques natives doivent être
recompilées pour Qt/KF6 présents sur la machine. Les tests de cette modification
ont été exécutés avec Qt 6.12 et des bibliothèques KF6, hors session Plasma.

Le script `Installer.sh --check-dependencies` diagnostique les modules Python,
les outils externes et l'intégration native sans installer Mirivue. Si le paquet
système est installé, il vérifie son assistant KIO. Pour une installation
utilisateur depuis les sources extraites, il configure CMake dans un dossier
temporaire pour vérifier la disponibilité des fichiers de développement Qt/KF6 ;
l'installation compile ensuite les assistants. Les sources ne contiennent plus
d'exécutables précompilés.

## Installation et sessions

Sur CachyOS, `Construire-paquet-CachyOS.sh` produit un paquet local recompilant
les assistants natifs. Il s'installe avec `pacman -U`. `Installer.sh` reste
réservé à l'installation utilisateur et refuse de superposer une seconde copie
à un paquet système installé. Il prépare et teste la nouvelle copie avant de la
publier, conserve une version précédente et propose `--rollback`.

L'application KDE utilise KIO pour les associations de fichiers, les
opérations et `trash:/`, y compris lorsqu'elle est lancée depuis une session
GNOME. Elle ne doit pas prendre la place du gestionnaire GNOME pour les
demandes FileManager1 dans cette session. L'intégration GNOME n'a pas le statut
de plateforme cible pour Mirivue KDE.

## Systèmes de fichiers et portée des essais

Les scénarios historiques sur ext4 et NTFS3, y compris les transferts entre
ces deux systèmes, ont été réussis dans des versions antérieures. Ils doivent
être rejoués sur la RC193 avant publication stable. Btrfs, exFAT, FAT32, SMB,
SFTP et MTP ne disposent pas encore d'une validation équivalente ; KIO peut
fournir certaines opérations sans que cela constitue une garantie de parité.
L'application n'est pas encore distribuée comme paquet natif sur d'autres
distributions Linux.

## Reprise des anciens réglages

Les clés de colonnes des anciennes RC, les préférences VideoInfoTable et les
marqueurs de métadonnées MFM restent lus lors d’une mise à jour. La migration
FileManager1 de la RC93 garde aussi son rôle dans une session GNOME. Aucune
version minimale de mise à jour n’est encore fixée : ces lectures ne seront
retirées qu’après avoir défini cette limite et vérifié la reprise des données
des versions encore prises en charge.

La liste de vérifications courante est `A-verifier-RC193.md` ; les critères de
publication figurent dans `STABILISATION.md` et l'historique dans `CHANGELOG.md`.

## Vérifications historiques

Les résultats ci-dessous concernent des versions antérieures. Ils ne constituent
pas une nouvelle exécution sur RC193 ; le bilan courant est VALIDATION-RC193.md.

La suite complète a réussi : 400 tests, aucun échec et aucun test ignoré,
avec Qt/PySide6 6.12 et KF6 6.31, puis à nouveau avec le plugin Union 6.8.0
chargé pour l’interface. Les contrôles C++ utilisent les vrais plugins Brise
et Union, des configurations claires et sombres et le moteur recompilé.
Ils vérifient le cadre des navigateurs dans le contexte de Dolphin, le fond
des vues, l’activation, la saisie et les changements de palette. La compilation
du moteur Qt/KF6 réussit également. Les corrections de la RC169 sont conservées ;
voir UNION.md pour leurs sources et leurs vérifications.

Les nouveaux scénarios de transfert utilisent de vrais événements Qt, les
travailleurs, des fichiers jetables et les mises à jour des modèles. Leur
transport KIO est substitué : cet environnement ne permet pas de créer la
session D-Bus nécessaire à un essai du service réel. TRANSFERTS.md détaille
les 55 transferts de ce parcours, les six retours d’opération native simulés
et les limites pour les serveurs distants et les opérations interdisques.

Les scénarios de clavier de la RC168 sont conservés : 960 combinaisons de
déclenchement, les trois vues, les menus masqués ou affichés, le panneau
actif, les champs de saisie et les préférences personnelles.

Le paquet CachyOS n’a pas été construit ni installé dans cet environnement
Ubuntu. Sa construction et sa vérification sont incluses dans la commande
proposée. Ces essais hors écran ne sont pas présentés comme une validation
dans la session Plasma de l’utilisateur. Aucun nouvel essai manuel n’est
demandé pour cette correction.

## Raccourcis depuis la RC168

Les raccourcis communs passent par KStandardShortcut, fourni par la dépendance
KF6 Config déjà requise. Le registre n’est plus limité aux actions visibles
des menus ; les variantes KDE et les préférences personnelles sont conservées.
Le terminal externe passe par KTerminalLauncherJob de KIO. Aucun paquet
supplémentaire n’est ajouté. Les résultats de l’audit figurent dans RACCOURCIS.md.

## RC193 : fenêtres et session

L’activation utilise KWindowSystem et son jeton Wayland. La découverte de toutes
les fenêtres exige un bus de session D-Bus fonctionnel. Sans celui-ci, le secours
local ne garantit que l’accès à la fenêtre principale. Voir PARITE-DOLPHIN.md.

## Style de date — RC193

Général → Affichage propose Relative et Absolue. Le format relatif natif utilise
KFormat de KDE ; le format absolu suit les paramètres régionaux Qt. Les valeurs
informal et locale restent compatibles. Un ancien choix ISO est conservé en
lecture et sur Annuler ; Appliquer/OK adopte le choix Absolue présenté.
Le défaut antérieur absolu régional reste conservé, sans modification des
préférences existantes. Les anciens formatages de secours servent uniquement
si le pont natif est indisponible dans une exécution depuis les sources.

## Interface RC193

Le menu principal et le dialogue de personnalisation des raccourcis utilisent
KHamburgerMenu et KShortcutsDialog de KDE. La taille du dialogue est un
réglage KDE partagé, accepté par l’utilisateur ; les raccourcis restent ceux
de Mirivue. Aucune nouvelle dépendance n’est ajoutée : KConfigWidgets et
KXmlGui étaient déjà requis. La suite complète du paquet reste à exécuter
sur CachyOS ; les essais de cette version sont détaillés dans VALIDATION-RC193.md.
