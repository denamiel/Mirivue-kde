# Personnalisation de la barre d'outils — RC193

Configurer → Personnaliser la barre d'outils ouvre le dialogue KDE KEditToolBar.
Le sélecteur propose les commandes avant les chemins et celles après les chemins.
Les chemins eux-mêmes restent disponibles et ne sont pas retirés par l'éditeur.
L'accès au menu est rétabli au besoin lorsque la barre de menus est masquée.

Les commandes peuvent être ajoutées, retirées ou réordonnées. Séparateurs,
espaces extensibles, icônes et textes sont enregistrés avec le document XMLGUI.
Les espaces utilisent la place disponible dans leur groupe de commandes ; ils
ne remplacent pas les barres de chemin. Les commandes présentes dans les deux
groupes pilotent la même action et suivent son état actif ou coché.

Les anciennes dispositions sont lues sans migration destructive. Ouvrir puis
Annuler n'écrit rien. Appliquer prend effet immédiatement ; Annuler ensuite
conserve ce dernier état appliqué, comme KDE. Restaurer les valeurs par défaut
utilise la confirmation KDE, puis applique immédiatement la disposition initiale.

Les préférences restent dans la configuration propre à Mirivue. Les fichiers
XML temporaires de l'éditeur sont privés et supprimés avec le dialogue. Aucun
fichier de Dolphin ni kservicemenurc n'est écrit par cette personnalisation.

Le nouveau fichier C++ est un adaptateur original sous MIT utilisant les API
publiques KEditToolBar/KXMLGUIFactory/KXMLGUIClient. Il ne copie pas Dolphin.
En cas de composant absent ou incompatible, un message l'indique sans effacer
les dispositions précédentes. Il faut recompiler la bibliothèque native.
