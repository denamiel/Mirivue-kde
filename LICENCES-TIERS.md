# Composants provenant de Dolphin

La distribution combinée est proposée sous GPL-3.0-or-later (LICENSE et
LICENSES/GPL-3.0-or-later.txt). Les parties originales de Mirivue gardent
également les droits MIT déjà accordés (LICENSES/MIT.txt).

Le moteur de vues est chargé dans le processus de Mirivue : sa séparation
en bibliothèque ne dispense pas de respecter les conditions GPL pour la
distribution combinée. L’archive inclut les sources correspondantes et les
scripts nécessaires à la construction ; les mentions tierces sont conservées.
Il ne s’agit pas d’une certification juridique.
Le moteur compilé `libmirivue-dolphin-view.so` incorpore les sources de
Dolphin 26.08.2 de KDE, principalement sous GPL-2.0-or-later, avec certains
fichiers sous BSD-2-Clause. Leurs auteurs, mentions et textes de licence sont
conservés dans `native/dolphin-engine` et `native/dolphin-engine/LICENSES`.
L’adaptateur `native/dolphin-view.cpp` est sous GPL-2.0-or-later.

La provenance fichier par fichier et les adaptations locales sont décrites
par `native/dolphin-engine/UPSTREAM.json` et son README.md. L’archive contient
les sources du moteur et les instructions de construction. Le paquet installé
inclut ces mentions dans `/usr/share/licenses/mirivue-kde/`.

## Comparaison naturelle des noms

`native/natural-sort.cpp` reprend les fonctions de comparaison naturelle de
`src/kitemviews/kfileitemmodel.cpp`, Dolphin 26.08.2, sous GPL-2.0-or-later.
Les auteurs et identifiants SPDX sont conservés en tête du fichier. La provenance
et l’empreinte du fichier source KDE figurent dans `native/NATURAL-SORT-UPSTREAM.json`.
La bibliothèque Qt de présentation relie ce comparateur au modèle de Mirivue.

Le groupement chronologique native/date-groups.cpp adapte également la fonction
timeRoleGroups de Dolphin v26.08.2, sous GPL-2.0-or-later ; les modifications
d’adaptation et la provenance sont consignées dans native/DATE-GROUPS-UPSTREAM.json.

## Adaptations des onglets et des libellés — RC177

mirivue/tab_ui.py adapte les interactions et menus de
src/dolphintabbar.cpp de Dolphin v26.08.2 (Emmanuel Pescosta), sous
GPL-2.0-or-later : routage Python des signaux, API des panneaux et dépôts
propres à Mirivue. Son en-tête conserve auteur, provenance et licence.

La fonction mirivue_places_location_identity dans native/kio-places-widget.cpp
adapte la résolution des libellés de DolphinViewContainer::caption(),
src/dolphinviewcontainer.cpp (Peter Penz), GPL-2.0-or-later, avec un résultat
JSON pour le pont Python et une icône fournie par KIO.

Référence commune : https://invent.kde.org/system/dolphin/-/tree/v26.08.2/src

Le reste des bibliothèques Qt, PySide6 et KF6 est fourni séparément par la
distribution Linux et conserve ses licences. La distribution combinée choisit
GPL version 3 ou ultérieure, compatible avec le code GPL-2.0-or-later du moteur
et les dépendances utilisées sous LGPL version 3 ; aucun droit MIT antérieur
n’est retiré. Les textes de licence installés accompagnent le paquet.

## Configuration des services — RC178

native/context-menu-settings.cpp adapte la découverte et la configuration des
services de src/settings/contextmenu/contextmenusettingspage.cpp, Dolphin
v26.08.2, Peter Penz (2009–2010), GPL-2.0-or-later. L’en-tête conserve ces
mentions ; les adaptations emploient un modèle Qt natif, une liaison JSON et
les préférences des commandes intégrées de Mirivue. Référence :
https://invent.kde.org/system/dolphin/-/blob/v26.08.2/src/settings/contextmenu/contextmenusettingspage.cpp

mirivue/servicemenu.knsrc reprend la configuration du même tag, fichier
src/settings/contextmenu/servicemenu.knsrc. KNewStuff et servicemenuinstaller
restent fournis par KDE/la distribution, sans copie de leurs exécutables.

## Code natif original sous MIT

Les vingt fichiers suivants portent un en-tête MIT ; les sources Dolphin ne
sont pas incluses dans cette liste.

- `native/desktop-dialogs.cpp`
- `native/desktop-shortcuts.cpp`
- `native/item-presentation.cpp`
- `native/job-progress.cpp`
- `native/kio-applications.cpp`
- `native/kio-empty-trash.cpp`
- `native/kio-list.cpp`
- `native/kio-open.cpp`
- `native/kio-places.cpp`
- `native/kio-preview.cpp`
- `native/kio-service.cpp`
- `native/kio-transfer.cpp`
- `native/open-with-menu.cpp`
- `native/path-navigator.cpp`
- `native/path-navigator.h`
- `native/terminal-widget.cpp`
- `native/toolbar-editor.cpp`
- `native/tests/open-with-reference.cpp`
- `native/tests/navigator-check.cpp`
- `native/tests/view-palette-check.cpp`

Les modules session_state.py, window_instances.py, view_policy.py et
external_locations.py sont des implémentations originales de Mirivue comparées
au comportement de Dolphin ; ils ne reproduisent pas son code source.

## Menu principal — RC190

mirivue/menu_visibility.py adapte le regroupement des commandes de
DolphinMainWindow::updateHamburgerMenu, src/dolphinmainwindow.cpp:1540–1626,
Dolphin v26.08.2. Peter Penz, Stefan Monov et Cvetoslav Ludmiloff sont cités
dans l’en-tête GPL-2.0-or-later. Les parties originales préexistantes de Mirivue
conservent leur permission MIT antérieure.

native/desktop-dialogs.cpp et les modules native_desktop_dialogs.py et
native_shortcuts.py sont des adaptateurs originaux sous MIT des API publiques
KHamburgerMenu et KShortcutsDialog. Leurs implémentations KDE ne sont pas copiées.
La distribution combinée reste sous GPL-3.0-or-later.

## Ouverture multiple — RC193

native/open-with-menu.cpp est un adaptateur original MIT de l’API publique
KFileItemActions::insertOpenWithActionsTo. Dolphin v26.08.2 utilise cette même
API dans src/dolphincontextmenu.cpp:495–498 ; son implémentation n’est pas copiée.
La référence native/tests/open-with-reference.cpp est un client de test de la
même API, non installé. La provenance est dans native/OPEN-WITH-REFERENCE.json.
Les licences de la distribution combinée restent inchangées.
