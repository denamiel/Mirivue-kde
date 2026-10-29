# Union et Brise — corrections de la RC169

## Documentation et sources utilisées

La documentation officielle décrit Union comme un moteur de styles. Son
module Qt Widgets fournit un `QStyle` : Mirivue conserve donc ses composants
Qt Widgets et KDE, sans passage à Qt Quick et sans style imposé au lancement.

- [Documentation Union](https://api.kde.org/union-index.html)
- [Utilisation dans les applications](https://api.kde.org/applications.html)
- [Module Qt Widgets et limites](https://api.kde.org/qtwidgets-index.html)
- [Union 6.8.0 : UnionStyle.cpp](https://invent.kde.org/plasma/union/-/blob/v6.8.0/src/output/qtwidgets/UnionStyle.cpp)
- [Dolphin 26.08.2 : conteneur des navigateurs](https://invent.kde.org/system/dolphin/-/blob/v26.08.2/src/dolphinnavigatorswidgetaction.cpp)
- [Dolphin 26.08.2 : palette des vues](https://invent.kde.org/system/dolphin/-/blob/v26.08.2/src/views/dolphinview.cpp)
- [Brise 6.8.0 : polishScrollArea](https://invent.kde.org/plasma/breeze/-/blob/v6.8.0/kstyle/breezestyle.cpp)

## Cadre des fils d’Ariane

Union tient compte de la hiérarchie des éléments Qt. Dans Dolphin, le
conteneur des navigateurs est un QSplitter, qui dérive de QFrame. Mirivue
utilisait un QWidget : avec Union, ce contexte différent faisait disparaître
le cadre du KUrlNavigator dans la barre d’outils.

La RC169 emploie un QFrame sans dessin propre à cet endroit. Union retrouve
ainsi le contexte Frame de Dolphin. La disposition et l’alignement existants
sont conservés ; KUrlNavigator et le QStyle actif dessinent toujours le cadre.
Aucune couleur, bordure CSS ni propriété privée d’Union n’est ajoutée.
L’activation d’un panneau ne force pas une bordure de focus.

## Fond des fichiers et panneau inactif

L’adaptateur retirait le cadre natif du KItemListContainer. Brise traite
spécialement cette classe lorsqu’elle est sans cadre : il change le rôle du
fond et rend ses viewports transparents. La RC169 conserve le conteneur natif
comme DolphinView.

Elle reprend ensuite DolphinView::updatePalette : la couleur du fond vient
de KColorScheme::View et est appliquée au véritable QGraphicsView. Son alpha
est de 150 pour le panneau inactif, comme dans Dolphin. Cette valeur exprime
une opacité ; les couleurs viennent entièrement du thème KDE. L’activation
de la fenêtre et les changements de palette ou de style actualisent ce fond.

Les trois façades Python ne remplacent plus la palette de sélection et les
bandes alternées ne sont plus désactivées dans le panneau inactif. Les
préférences de colonnes, de zoom et de disposition restent conservées.
KF6 ColorScheme était déjà une dépendance ; Union reste facultatif.

## Vérification et limites

La validation compile le moteur de fichiers et deux contrôles C++. Le
contrôle des navigateurs compare les pixels du composant de Mirivue avec un
KUrlNavigator placé dans le contexte de conteneur de Dolphin. Il couvre
Brise et Union, les polices, les palettes, la saisie et l’activation.

Le contrôle des vues compare le véritable viewport de l’adaptateur à la
règle de palette de Dolphin, appliquée indépendamment à un second conteneur
du même moteur. Il vérifie le fond dessiné, les groupes actif/inactif, les
changements de palette, les trois vues et des configurations claires et
sombres. Les tests Qt de la fenêtre vérifient aussi le conteneur du chemin
et l’activation des deux panneaux.

Les contrôles utilisent les vrais plugins Brise et Union 6.8.0, Qt/PySide6
6.12 et KF6 6.31, hors écran. Union est testé automatiquement lorsqu’il est
installé ; il n’est pas ajouté aux dépendances de Mirivue. La compilation de
tous les assistants natifs est également vérifiée. Ce résultat ne constitue
pas une validation d’une session Plasma/Wayland complète ni du paquet
CachyOS installé. Aucun nouvel essai manuel n’est demandé pour la RC169.
