# Matrice de gel — Mirivue RC194 / Dolphin v26.08.2

Référence unique : [sources officielles Dolphin v26.08.2](https://invent.kde.org/system/dolphin/-/tree/v26.08.2/src). Les lignes sont celles de l'archive de ce tag, téléchargée pendant l'audit. Aucun résultat de la branche de développement n'est utilisé.

Cette matrice décrit la RC194, limitée aux corrections autorisées. Les autres écarts sont conservés et explicités. « Identique » signifie le comportement circonscrit décrit, lu dans le code et, lorsque indiqué, testé hors écran. Cela ne remplace pas les scénarios Plasma. « Écart volontaire justifié » peut inclure une décision recommandée pour le gel, explicitement indiquée ; ce n'est pas une autorisation de transformer un défaut non vérifié en choix volontaire.

| Comportement | Classement | Preuve Mirivue RC186 | Référence Dolphin v26.08.2, sous `src/` | Niveau de preuve / décision |
|---|---|---|---|---|
| Nouvelle installation : demande externe dans une nouvelle fenêtre | identique | `app.py:73–81`, `external_locations.py:151–155` | `settings/dolphin_generalsettings.kcfg:41–44`, `global.cpp:111–115` | Code et tests de routage hors écran |
| Ancienne installation : conserver le choix onglets/fenêtres | écart volontaire justifié | `app.py:76–79` | Même réglage Dolphin ci-dessus | Compatibilité recommandée ; ne pas migrer silencieusement |
| Plusieurs dossiers manquants : une seule fenêtre pour le lot | identique | `external_locations.py:72–98`, `:151–155` | `global.cpp:41–58`, `:130–138` | Routage/batch testé ; activation réelle à valider |
| Dossier déjà ouvert : réutilisation d'un onglet/fenêtre | identique | `window_instances.py:102–117`, `:285–333` | `global.cpp:86–128`, `dolphintabwidget.cpp:139–147` | Test de bus privé ; réserve sur pannes partielles ci-dessous |
| Fenêtre détachée/`--new-window` connue des autres fenêtres | identique | `window_instances.py:151–167` | `global.cpp:145` et suite, `dolphintabwidget.cpp:396–414` | Enregistrement bus testé ; détachement visuel à éprouver |
| Rappel d'une fenêtre agrandie | identique | `app.py:5626–5635` | `dolphinmainwindow.cpp:339–351`, `main.cpp:249–255` | `show()` sans `showNormal()` dans Mirivue ; vérification graphique finale requise, pas une mesure KWin |
| Jeton d'activation Wayland transmis | identique | `window_activation.py:8–23`, `external_locations.py:88–89`, `:109` | `global.cpp:124–127` | Transmission testée ; politique KWin non validée hors écran |
| `--select`, `--split` et lot d'emplacements | identique | `launch_targets.py:35–84`, `external_locations.py:156–183` | `main.cpp:202–211`, `:254–271`, `global.cpp:123` | Tests ; un passage a échoué en initialisation du test, cause non établie |
| Découverte/routage D-Bus avec fenêtres bloquées | écart volontaire justifié | `window_instances.py:184–388` | `global.cpp:62–139` | `test_rc181_routing` : budget global et Qt vivant ; robustesse Mirivue autorisée. Dolphin attend les réponses avec waitForFinished dans son routage de lancement ; pas de prétention au même mécanisme interne |
| Validation du JSON privé | écart volontaire justifié | `window_instances.py:33–97` | `global.cpp:22–34` valide les URL ; pas de JSON équivalent | `test_rc181_freeze` et bus jetable : types/bornes/URL/JSON profond ; garanties propres à Mirivue |
| Nouvel onglet après l'onglet courant | identique | `panes.py:295` et suite | `dolphintabwidget.cpp:205–210` | Code et tests de gestes |
| Retour à l'onglet précédemment actif à fermeture | identique | `tab_ui.py:19`, logique MRU `panes.py` | `dolphintabbar.cpp:44` | Code et tests |
| Clic du milieu ferme l'onglet au relâchement | identique | `tab_ui.py:32–47` | `dolphintabbar.cpp:133–154` | Code et tests de gestes |
| Double-clic : duplication du dossier de l'onglet concerné | identique | `tab_ui.py:49–62` | `dolphintabbar.cpp:158–172` | Pas limité à la seule zone vide |
| Menu de la barre d'onglets, renommer/détacher/fermer groupes | identique | `tab_ui.py:64` et suite | `dolphintabbar.cpp:175–230` | Code ; menu adapté aux fonctions Mirivue |
| Survol d'onglet pendant un dépôt : 800 ms | identique | `tab_ui.py:23–26` | `dolphintabbar.cpp:53`, `:250–267` | Timer testé ; vrai glisser-déposer sous Plasma restant |
| Toujours afficher la barre / boutons de fermeture | identique | `panes.py:479–481`, `configuration.py` : options onglets | `dolphintabbar.cpp:234–247`, `dolphin_generalsettings.kcfg:45–53` | Tests de réglages et relance |
| Icône et libellé des Emplacements pour les onglets | identique | `panes.py:283–293`, `:531–533`, `places.py:36` | `dolphinviewcontainer.cpp:581` et suite, `dolphintabwidget.cpp:533–557` | Vrai signet local testé ; la version RC179 corrige le mauvais type d'enum QUrl |
| Coupure d'un titre automatique long | identique | `panes.py:512–533`, `places.py:103`, pont `mirivue_tab_set_text` | `dolphintabwidget.cpp:557` | `test_rc181_freeze.test_titles_use_rsqueeze_ascii_dots` ; KStringHandler natif, & puis fin ASCII |
| Titre personnalisé long non coupé par rsqueeze | identique | `panes.py:519–530` | `dolphintabwidget.cpp:126–134` | Conserver cette exception lors du correctif |
| Fermer un onglet pendant le chargement | identique | `panes.py:452`, `:1581`, `:1643` | `dolphintabwidget.cpp:306–321` | `test_rc181_panes_gui` : dix fermetures, split et destruction C++ réellement traitée ; wrapper natif invalidé (`dolphin_view.py:112`) ; stress de 300 cycles réussi |
| Restauration de session exclusive du dossier de démarrage | identique | `configuration.py:282–287`, `session_state.py:37–39` | `settings/interface/folderstabssettingspage.cpp:53–58`, `:92–94` | Deux boutons radio exclusifs chez Dolphin : ne pas séparer les réglages |
| Option supplémentaire « dernier dossier » | écart volontaire justifié | `configuration.py:283` | Page de démarrage précédente | Extension Mirivue existante ; garder ses réglages |
| Confirmation de fermeture de plusieurs onglets selon restauration | identique | `session_state.py:110–136` | `dolphinmainwindow.cpp:632` et suite | Code et tests de boîte à trois choix |
| Session de plus de 100 onglets | identique | `session_state.py:37–82` | `dolphintabwidget.cpp:92–107` | `test_rc181_freeze` : 100/101, deux restaurations/sauvegardes ; état complet comparé |
| Session de la dernière fenêtre fermée | identique | `session_state.py:13–35` | `main.cpp:249–255` | Même principe ; documenter et tester concurrence, sans prétendre restaurer toutes les fenêtres |
| Sauvegarde de session lors d'un arrêt brutal | écart à corriger | `app.py:5722` | `main.cpp:274` active l'autosauvegarde | Écart de garantie à résoudre ou limiter explicitement ; ne pas ajouter une refonte multi-fenêtre |
| Styles communs : mode, cachés, miniatures, zoom | identique | `view_policy.py:11–13`, `:29–45`, `:64–77`, `:91` et suite | `settings/dolphin_generalsettings.kcfg:90–93`, `views/viewproperties.cpp:159–230` | Tests navigation ; anciens styles conservés mais ignorés en mode commun |
| Styles particuliers Corbeille/Récents/Téléchargements | identique | `view_policy.py:16–45` | `views/viewproperties.cpp:171–219`, `:263` et suite | Code/tests des styles ; protocoles réseau à vérifier |
| Fichiers cachés : point initial et `.hidden` | identique | `file_visibility.py:12–51`, `native/kio-list.cpp:38–39` | `kitemviews/kfileitemmodel.cpp:2389–2397` ; lecture dans KCoreDirLister | Essais réels .hidden ; illisible seulement simulé |
| Cachés en dernier, dossiers en premier | identique | `app.py:824–831` | `kitemviews/kfileitemmodel.cpp:2389–2408` | Tests deux sens ; option taille/comptage des dossiers à compléter |
| Tri naturel des noms, accents et nombres décimaux | identique | `native/natural-sort.cpp`, `app.py:882–898` | `kitemviews/kfileitemmodel.cpp:75–261`, `:2616–2643` | Code repris avec provenance et tests de comparaison ; aucune généralisation aux colonnes non équivalentes |
| Taille et dates filesystem connues | identique | `app.py:836–862`, `metadata.py:363–365` | `kitemviews/kfileitemmodel.cpp:2464–2548` | Principe numérique ; inconnu et tailles de dossiers à éprouver |
| Résolution, piste, auteur, valeurs vides et départages | identique | `app.py:821–895`, `metadata.py:332`, `kio-list.cpp` | `kitemviews/kfileitemmodel.cpp:2557–2607`, `.h:600–605` | `test_rc181_freeze` : résolution/piste/auteur/vides/nom réel ; origine traitée séparément ci-dessous |
| Durée/FPS/débits : comparaison numérique | écart volontaire justifié | `app.py:836–862` | `kitemviews/kfileitemmodel.cpp:2576–2588` ; fournisseur Baloo : texte formaté | Choix Mirivue expressément conservé dans le périmètre RC181 ; ce n’est pas une parité de ces rôles |
| Colonnes média sans équivalent, renommage enrichi | écart volontaire justifié | `column_groups.py`, `media.py:13`, outil de renommage | Catalogue des rôles `kfileitemmodel.cpp:3115–3167` | Ne pas inventer un équivalent Dolphin ; documenter chaque règle de tri |
| Moteur de dessin/en-tête et palette | identique | `native/dolphin-engine`, `native/dolphin-view.cpp` | `kitemviews/kitemlistview.*`, `kstandarditemlistwidget.*` | Sources embarquées ; ce n'est plus la table Python décrite dans les anciennes RC |
| Réglages des services contextuels partagés | identique | `context_menu_settings.py:200`, `native/context-menu-settings.cpp:166`, `:213` | `settings/contextmenu/contextmenusettingspage.cpp:173`, `:267` | **Partage voulu et également natif KDE** : ne pas privatiser ce fichier |
| Installation d'un service uniquement par action explicite | identique | `native/context-menu-settings.cpp:95–103` | `settings/contextmenu/contextmenusettingspage.cpp:67–80` | Aucun téléchargement/installation exécuté dans l'audit ; code natif de plugins déjà installés soumis à confiance KDE |

## Règle de mise à jour de cette matrice

- Après correction, remplacer le statut uniquement avec le test de non-régression et la nouvelle ligne de code.
- Ne pas qualifier une propriété « identique » sur le seul nom de classe Qt ; comparer le comportement et les options du composant.
- Les lignes nécessitant Plasma gardent leur réserve tant que le scénario n'a pas été réellement effectué.
- Aucune nouvelle fonction ou refonte pour remplir une case de cette matrice pendant le gel.

## Limites conservées et règles de tri des autres colonnes

Les modes d'affichage, options de démarrage et préférences historiques ne changent
pas. kservicemenurc reste partagé. Les états « identique » portent sur le comportement
indiqué et ses tests ; ils ne certifient pas un essai réel sous Plasma.

- Taille, modification, accès et suppression : valeurs numériques/dates internes.
- Durée, FPS, débits vidéo/audio, canaux, fréquence et profondeur audio : numériques,
  choix Mirivue conservé. Dolphin peut comparer un texte formaté pour certains rôles.
- Titre, artiste, album, genre, mots-clés, artiste d'album, compositeur et description :
  comparaison humaine dans le mode sélectionné ; les colonnes propres à Mirivue
  ne deviennent pas des rôles Dolphin par la seule ressemblance de leur nom.
- Auteur : comparaison brute corrigée ; codecs, HDR/SDR, format, droits, disque,
  extension suggérée et type de média : comparaison brute conservée.
- Année/date : texte général de la balise date, pas un rôle releaseYear.
- Prise de vue et emplacement d'origine : règles actuelles conservées dans ce lot.
- Les rôles techniques masqués ne sont pas réintroduits.
- Les valeurs vides sont placées après les valeurs renseignées en ordre croissant
  pour les seuls rôles textuels équivalents traités par le correctif.
- Tout départage demandé passe par nom affiché, nom réel puis URL ; le nom réel
  est transporté par KFileItem::name() et conservé séparément du nom affiché.

Écart volontaire dans ce périmètre : **Emplacement d'origine** garde sa comparaison
brute. Référence Dolphin : kfileitemmodel.h:600–605. Pas de modification de cette
colonne parmi les cinq corrections de tri autorisées.

La sauvegarde reste effectuée à la fermeture ; le comportement en cas d'arrêt
brutal et de disque absent n'est pas transformé par le correctif des 101 onglets.
Voir NON-MODIFIE-RC181.md, VALIDATION-RC186.md et A-verifier-RC186.md.

## Réglages du menu contextuel

Comme Dolphin v26.08.2 (contextmenusettingspage.cpp:289,304,339–349), la page
montre le libellé fourni par KDE, sans suffixe technique ajouté. Le fichier source
reste en infobulle. Le stockage des préférences utilise toujours l'identifiant
natif ; deux homonymes peuvent rester deux cases distinctes.

## Validation RC186

Les demandes externes ne deviennent pas synchrones. Les tests attendent la fin du routage (test_dolphin_navigation_policy.py, pending_routes/settle) et la validation complète utilise un bus jetable actif. Les assertions de comportement restent conservées.

## Contrôle après installation RC186

Le contrôle natif attend une fenêtre exposée puis une réponse au redimensionnement
et utilise un dossier jetable valide. Deux tests couvrent une réponse différée et
un refus persistant. Les contraintes et le rendu de l'application ne changent pas ;
aucun statut de parité fonctionnelle n'est modifié par ce correctif de contrôle.

## Style de date — RC186

| Comportement | Classement | Preuve Mirivue | Référence Dolphin v26.08.2 | Portée |
|---|---|---|---|---|
| Deux choix Relative / Absolue, exemples à trente minutes | identique | configuration.py:339–351 ; test_date_style_configuration | src/settings/viewmodes/contentdisplaytab.cpp:78–92 | Formulaires Qt, application et réouverture du réglage testés |
| Date relative courte : même API KFormat | identique pour l'API et les chaînes produites | native/kio-places-widget.cpp:218–230 ; date_display.py ; comparaison-kformat.json | src/kitemviews/kfileitemlistwidget.cpp:55–64 | Fonction compilée isolément avec KCoreAddons 6.31.0 ; 15 cas comparés au formateur natif ; pont KIO complet non compilé ici |
| Placement du réglage | écart volontaire justifié | Général → Affichage | Affichage → Affichage du contenu | Organisation propre à Mirivue demandée par l'utilisateur |
| Choix par défaut et préférences existantes | écart volontaire justifié | défaut absolu régional antérieur conservé ; valeurs informal/locale inchangées | src/settings/dolphin_contentdisplaysettings.kcfg:28–31 : défaut relatif | Ne pas changer les préférences existantes à l'occasion d'un déplacement de réglage |

L'ancien ISO n'est plus proposé ; il reste lisible et n'est remplacé qu'à
l'application du dialogue. Le repli sans bibliothèque native n'est pas présenté
comme une reproduction de KFormat. Aucun autre statut de la matrice ne change.

## Validation RC186

Le test des groupes de configuration attend désormais Affichage. Aucune règle
de comportement ni aucun statut de parité n'est modifié. Voir VALIDATION-RC186.md
pour les contrôles ciblés et les limites de validation.

## RC186 — suppression d'un accès redondant

L'outil de renommage avancé propre à Mirivue reste accessible dans Outils. Son
entrée est retirée du menu contextuel Organiser. Ce choix d'organisation ne
change aucun statut de parité Dolphin, ni le comportement F2.

## RC187 — cohérence interne des commandes

Les gardes des commandes de modification sont partagées entre Outils et le
menu contextuel. Création d'archive désactivée pour les emplacements distants,
que la fonction de Mirivue ne prend pas en charge. Les textes du renommage,
des terminaux et de l'aide aux miniatures sont clarifiés. Ces corrections
internes ne changent aucun statut de parité Dolphin. Les commandes de terminal
conservent leurs deux destinations et leurs raccourcis.

## RC188 — conventions KDE et XMLGUI

KEditToolBar est le vrai dialogue KDE, appelé par un adaptateur original MIT
(native/toolbar-editor.cpp). Deux groupes encadrent les chemins, qui restent
hors de l'éditeur. Les paramètres sont propres à Mirivue ; kservicemenurc reste
le seul partage volontaire déjà documenté. Les séparateurs, espaces, propriétés
d'icône et de texte ne sont pas perdus. Une commande présente dans les deux
groupes conserve un comportement partagé via des boutons miroirs. L'accès au
menu reste assuré si la barre de menus est masquée.

Ce point ne transforme aucun statut de la matrice en parité visuelle complète
avec Dolphin. La nouvelle organisation des préférences est un choix de Mirivue
conforme au regroupement recommandé par les HIG KDE, pas une copie du panneau
de Dolphin. Les références Dolphin v26.08.2 et KF6 6.31.0 restent inchangées.
Le niveau exact de validation est précisé dans VALIDATION-RC188.md.

## Validation RC189

Le contrôle de recherche attend le titre Configurations de colonnes ajouté en
RC188. Aucun comportement ni statut de parité n'est modifié. Les autres
assertions du scénario graphique sont conservées. Voir VALIDATION-RC189.md.

## Composants d’interface RC190

| Comportement | Statut et portée | Code Mirivue | Référence / preuve |
|---|---|---|---|
| Menu principal KDE et accès aux menus complets | Même composant natif ; contenu adapté aux fonctions Mirivue | native/desktop-dialogs.cpp, menu_visibility.py | Dolphin v26.08.2 dolphinmainwindow.cpp:1540–1626 ; test_native_desktop_dialogs, cas curated/context/clone/visibility |
| Personnalisation des raccourcis | Même dialogue KShortcutsDialog ; stockage volontairement propre à Mirivue | native_shortcuts.py, keyboard.py, desktop-dialogs.cpp | API publique KF6 KShortcutsDialog ; cas alternates/cancel/defaults/modeless/save-failure |
| Taille du dialogue des raccourcis | Réglage de géométrie KDE partagé, exception acceptée par l’utilisateur | KShortcutsDialog fourni par le système | kxmlgui 6.31.0 kshortcutsdialog.cpp ; seule la taille est globale |
| Groupes d’aperçus et commande de durée | Organisation propre à Mirivue, sans prétendre reproduire une fonction média de Dolphin | configuration.py, app.py | test_interface_groups ; valeurs conservées |

Les tests natifs ont été exécutés hors écran sur KF6 6.13.0 ; les sources
de comparaison restent celles de KF6 6.31.0 et de Dolphin v26.08.2. Ces essais
ne valident pas une session Plasma, Union, Wayland ni le moteur complet. Les
anciens statuts de cette matrice ne sont pas requalifiés par ces tests ciblés.

## Correctifs RC191

Aucun statut de parité n’est changé. Le menu reste un KHamburgerMenu natif.
menu_visibility.py retire ses références aux actions empruntées avec removeAction,
sans clear() qui invalide certains wrappers PySide6 créés par QMenu.addAction.
Le test test_menu_rebuild_keeps_actions_created_by_other_menus_alive reproduit
la régression puis vérifie les commandes après plusieurs reconstructions. Le
test existant Tab/Maj+Tab entre panneaux réussit de nouveau dans les trois vues.
Les imports des sous-processus des tests sont indépendants d’un PYTHONPATH de
développement. Voir VALIDATION-RC191.md pour les résultats et les limites.

## Réactivité RC192 — aucun changement de comportement voulu

Les filtres, critères de recherche et colonnes média restent ceux de RC191.
Le changement de contexte d’un panneau conserve son filtre s’il est identique.
Le filtre de noms utilise beginFilterChange/endFilterChange sur Qt compatible,
et conserve un repli sur les versions 6.8/6.9 acceptées par le paquet.
Les résultats de miniatures utilisent le contexte discret du panneau d’origine,
sans synchroniser l’espace disque et les dates de l’autre panneau.

model_inventory.py entretient un index par chemin et un compteur de médias
incomplets à partir des signaux du modèle. Les chemins identiques restent
associés à toutes leurs lignes ; les insertions, remplacements, renommages,
suppressions et réinitialisations sont couverts par les contrôles. Les changements
de miniature et de palette ne recomptent pas les métadonnées. L’index prend une
mémoire proportionnelle au nombre de lignes et reste attaché au modèle.

Aucun statut ancien n’est promu à une validation Plasma par ces corrections.
Tests : test_reactivity_inventory et test_freeze_documents ; résultats et
limites dans VALIDATION-RC192.md. Les classes de dessin restent celles de
Dolphin v26.08.2 ; le traitement des métadonnées reste propre à Mirivue.

## Ouverture d’une sélection multiple — RC193

Portée : plusieurs fichiers, sans dossier sélectionné. Le constructeur du menu
passe toutes leurs URL à KFileItemActions::insertOpenWithActionsTo, avec exclusion
de l’identifiant de Mirivue comme Dolphin exclut le sien. Référence exacte :
Dolphin v26.08.2, src/dolphincontextmenu.cpp:269–310 et :495–498.
La provenance et l’empreinte du fichier sont dans native/OPEN-WITH-REFERENCE.json.

La partie d’ouverture est fournie par le même composant KIO ; noms, icônes,
classement, application préférée et choix d’une autre application suivent KDE.
Aucune liste d’applications n’est codée en dur. Ce constat ne déclare pas tout
le menu contextuel identique : les outils multimédias propres à Mirivue restent
présents. Les fichiers seuls et sélections contenant des dossiers sont inchangés.

Code : native/open-with-menu.cpp, open_with.add_native_open_with et branche
native_open_with de file_context_menu. Sept tests dans test_multi_open_with :
constructeur réel du bloc, transmission de toutes les URL, repli, maintien des
cas existants, résultat natif vide et comparaison de menus KIO avec associations
jetables. Comparaison native effectuée sur KF6 6.13.0 ; aucune capture Plasma
comparative ni lancement réel de mpv n’est déclaré validé. Voir VALIDATION-RC193.md.

## RC194 — validation uniquement

Aucun statut de parité de comportement n’est changé. Le banc de test corrige
le pilotage de QToolButton/KHamburgerMenu sous Qt 6.11 et privilégie un bus privé
Unix, comme le transport d’une session Linux. Cela ne change ni les réglages,
ni le menu, ni le routage D-Bus de l’application. Les quatre échecs du journal
Fedora ne deviennent pas automatiquement quatre parcours validés sur Fedora.
