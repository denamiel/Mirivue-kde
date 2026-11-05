# Mirivue KDE 1.0.0-beta.4 — collage natif KDE

Version visible `1.0.0-beta.4`, version Python `1.0.0b4`, première révision RPM
`0.199.beta4.1`. Les transferts de fichiers restent ceux de la bêta 3.

Le collage de texte et d’images utilise maintenant l’API publique `KIO::paste`,
comme Dolphin. Le dialogue de nommage, les formats proposés, la gestion des
conflits et l’écriture sont assurés par KIO. Le writer Python spécifique est
supprimé. L’accès au presse-papiers reste dans le processus Qt de Mirivue pour
ne pas dépendre de l’accès d’un helper au presse-papiers Wayland.

## Changement visible

Un fichier existant peut désormais être remplacé **après confirmation dans le
dialogue KDE**, au lieu d’être systématiquement refusé par Mirivue. Ce parcours
ne promet pas le refus atomique de tout remplacement concurrent que fournissait
l’ancien writer. Le choix des formats suit les types MIME du presse-papiers ;
une image n’est plus systématiquement convertie en PNG par Python.

Les fichiers créés sont sélectionnés après actualisation du dossier. Les
opérations de collage restent accessibles dans Opérations et empêchent la
fermeture effective de l’application tant qu’elles ne sont pas terminées.
L’historique distingue le gestionnaire KIO du processus Qt et celui du service
avec contrôle de l’identifiant de commande avant annulation, pour adresser Annuler/Rétablir à celui qui a exécuté l’opération. Les dépôts
natifs sur les emplacements et la barre de chemin sont associés au premier.
L’annulation d’une création de fichier utilise le comportement KIO, notamment
sa corbeille ; un remplacement confirmé ne garantit pas la restauration des
anciens octets par Annuler.

## Validation

La suite `test_native_clipboard_gui.py` utilise la bibliothèque native compilée,
les vrais dialogues KIO et des fichiers jetables. Elle vérifie le texte Unicode,
les images PNG et leur sélection, l’annulation du nommage et du conflit, le
remplacement confirmé, le changement du presse-papiers pendant le choix du
format, Annuler/Rétablir et l’ordre avec une copie effectuée par le service KIO.
Les résultats sont ceux du workflow GitHub Actions du commit publié.

Les tests automatisés utilisent Qt offscreen avec D-Bus isolé : ils ne constituent
pas une validation d’échanges entre toutes les applications d’une session
Wayland. Une vérification manuelle sous Plasma/Wayland reste utile.

L’extraction RAR n’est pas modifiée : Ark effectue la décompression ; les
contrôles de chemins, d’espace temporaire et de publication restent présents.
