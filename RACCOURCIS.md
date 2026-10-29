# Raccourcis de Mirivue KDE — audit RC168, conservé dans la RC170

Audit du 18 octobre 2026, comparé aux sources de Dolphin **26.08.2**, version du moteur intégré, et aux raccourcis standard de KDE Frameworks **6.31**. Les valeurs standard sont lues par **KStandardShortcut sur la machine qui lance Mirivue**. Les réglages KDE et les personnalisations de Mirivue peuvent donc remplacer les combinaisons indiquées ci-dessous.

## Défauts corrigés

Avec les menus masqués, l’essai initial sur la RC167 a montré **30 raccourcis inactifs**, soit 180 échecs sur 540 scénarios. Leurs QAction étaient rattachées aux menus mais pas à la fenêtre. Toutes les commandes du registre sont désormais rattachées une seule fois à la fenêtre, indépendamment de l’affichage des menus et de la présence d’un bouton de barre d’outils.

Les transferts vers l’autre panneau reprennent **Maj+F5 / Maj+F6**, au lieu de Ctrl+F5 / Ctrl+F6. Les variantes KDE manquantes sont reprises, notamment Ctrl+Inser, Maj+Inser, Alt+Entrée du pavé numérique, Ctrl+=, Alt+D et Alt+point. Maj+Suppr reste réservé à la suppression définitive dans les fichiers ; il coupe le texte dans un éditeur.

Les commandes existantes sans raccourci retrouvent les accès correspondants de Dolphin : miniatures F12, copie des chemins Ctrl+Alt+C, autre panneau Ctrl+F3, onglets et configuration. La commande de terminal distingue le dossier courant des emplacements sélectionnés ; le lancement utilise **KTerminalLauncherJob**, donc le terminal choisi dans KDE. Le choix du terminal intégré reste KonsolePart.

Retour arrière fonctionne depuis le moteur natif. Échap quitte la saisie du chemin et rend le focus aux fichiers. Ctrl+I rappelle et sélectionne le filtre existant au lieu de le fermer. Le contournement global de F2, devenu inutile après l’enregistrement correct des actions, est retiré : les commandes d’édition des champs de texte restent prioritaires.

La personnalisation englobe également le presse-papiers, les onglets, l’aide et les miniatures. Les conflits sont cherchés dans toutes les variantes, pas seulement dans la combinaison principale. L’aide affiche les combinaisons effectivement utilisées. Les réglages personnels déjà enregistrés restent conservés ; rétablir les valeurs par défaut reprend les valeurs KDE et Dolphin de cette version.

## Combinaisons par défaut

| Commande | Combinaisons |
| --- | --- |
| Nouvelle fenêtre ; nouvel onglet | Ctrl+N ; Ctrl+T |
| Fermer l’onglet ; rouvrir le dernier fermé | Ctrl+W ; Ctrl+Maj+T |
| Onglet suivant | Ctrl+Tab, Ctrl+Page suivante, Ctrl+] |
| Onglet précédent | Ctrl+Maj+Tab, Ctrl+Page précédente, Ctrl+[ |
| Onglets 1 à 9 ; dernier onglet | Alt+1 à Alt+9 ; Alt+0 |
| Nouveau dossier | Ctrl+Maj+N |
| Ouvrir ; renommer | Entrée ; F2 |
| Propriétés | Alt+Entrée, y compris la touche du pavé numérique |
| Corbeille ; suppression définitive | Suppr ; Maj+Suppr |
| Couper ; copier ; coller | Ctrl+X ; Ctrl+C ou Ctrl+Inser ; Ctrl+V ou Maj+Inser |
| Dupliquer ; copier les chemins sélectionnés | Ctrl+D ; Ctrl+Alt+C |
| Annuler ; rétablir une opération | Ctrl+Z ; Ctrl+Maj+Z |
| Tout sélectionner ; inverser la sélection | Ctrl+A ; Ctrl+Maj+A |
| Agrandir ; réduire ; réinitialiser la taille | Ctrl++ ou Ctrl+= ; Ctrl+- ; Ctrl+0 |
| Détails ; icônes ; compact | Ctrl+3 ; Ctrl+1 ; Ctrl+2 |
| Précédent ; suivant ; parent ; dossier personnel | Retour arrière ou Alt+← ; Alt+→ ; Alt+↑ ; Alt+Début |
| Saisir un emplacement | Ctrl+L, Alt+D |
| Basculer saisie / fil d’Ariane | F6 |
| Rechercher ; filtrer le dossier | Ctrl+F ; Ctrl+I ou / |
| Éléments cachés ; miniatures | Ctrl+H ou Alt+point ; F12 |
| Vue scindée ; activer l’autre panneau | F3 ; Ctrl+F3 |
| Copier ; déplacer vers l’autre panneau | Maj+F5 ; Maj+F6 |
| Panneaux Emplacements ; Dossiers ; Terminal ; Aperçu | F9 ; F7 ; F4 ; F11 |
| Terminal externe, dossier courant | Maj+F4 |
| Terminal externe, emplacements sélectionnés | Maj+Alt+F4 |
| Focus terminal intégré / fichiers | Ctrl+Maj+F4 |
| Actualiser | F5, touche multimédia Actualiser |
| Menu principal ; barre de menus | **F10** ; Ctrl+M |
| Configurer Mirivue ; aide ; quitter | Ctrl+Maj+virgule ; F1 ; Ctrl+Q |

KDE ajoute aussi certaines touches de navigation matérielles et Ctrl+Échap à Fermer. Leur interception éventuelle par le bureau reste du ressort de Plasma. **F10 ouvre bien le menu dans les sources actuelles de Dolphin** ; il ne faut pas reprendre l’ancienne convention qui lui attribuait Nouveau dossier.

Dans la vue de fichiers, le contrôleur de Dolphin conserve Flèches, Début/Fin, Maj pour étendre la sélection, Ctrl+Espace pour basculer l’élément courant, Entrée pour ouvrir et Échap pour désélectionner. Dans un champ de texte, Suppr et Retour arrière éditent le texte ; copier, couper, coller, annuler et tout sélectionner conservent leur sens d’édition.

## Validation et limites

**385 tests réussis, aucun échec ni test ignoré**, avec le moteur de Dolphin réellement compilé, Qt/PySide6 6.12 et KF6 6.31 hors écran. Le processus de validation doit également se terminer avec le code 0.

Le test d’acheminement envoie **960 combinaisons** : 80 combinaisons enregistrées × 3 vues × 2 panneaux × menus visibles ou masqués. Les effets des commandes qui ouvriraient un programme, un dialogue ou une opération de fichiers sont neutralisés dans ce test, afin de vérifier séparément leur déclenchement sans effectuer de suppression.

Des tests fonctionnels supplémentaires vérifient la sélection et son inversion, le filtre, la recherche, les champs de texte, le presse-papiers réel, les chemins copiés, les éditeurs de renommage, les onglets, le changement de vue, les panneaux, le zoom, les miniatures, le focus et les personnalisations. Un processus séparé vérifie la lecture des raccourcis de kdeglobals et la priorité d’un choix personnel. Les événements de menu contextuel au clavier sont testés dans chaque vue ; le plugin Qt hors écran ne synthétise pas l’événement natif des touches Menu/Maj+F10.

La compilation complète des assistants et de la bibliothèque d’intégration KDE réussit également. Un contrôle automatisé supplémentaire avec le vrai panneau Emplacements et le vrai KUrlNavigator a vérifié Ctrl+L, Alt+D, F6 et Échap dans les trois vues. KonsolePart et le lancement d’un terminal réel ne sont pas disponibles dans cet environnement ; le calcul de leurs cibles et l’appel du lanceur sont testés sans ouvrir de terminal.

Ces résultats vérifient l’application et ses combinaisons, pas les raccourcis globaux éventuellement réservés par le compositeur, la disposition physique d’un clavier ou les opérations KIO réelles sur chaque support. Le paquet CachyOS n’a pas été installé dans cet environnement. Les fonctions propres à Dolphin que Mirivue ne propose pas, comme sa barre de sélection ou Stash, ne sont pas ajoutées par cet audit.

## Sources de comparaison

- [Actions de la fenêtre de Dolphin 26.08.2](https://raw.githubusercontent.com/KDE/dolphin/v26.08.2/src/dolphinmainwindow.cpp)
- [Actions des vues de Dolphin 26.08.2](https://raw.githubusercontent.com/KDE/dolphin/v26.08.2/src/views/dolphinviewactionhandler.cpp)
- [Onglets de Dolphin 26.08.2](https://raw.githubusercontent.com/KDE/dolphin/v26.08.2/src/dolphintabwidget.cpp)
- [Liste des raccourcis standard de KF6 6.31](https://raw.githubusercontent.com/KDE/kconfig/v6.31.0/src/gui/kstandardshortcut.cpp)
- [API KStandardShortcut](https://api.kde.org/kstandardshortcut.html)

## Personnalisation RC193

Configurer les raccourcis clavier ouvre le véritable KShortcutsDialog KDE,
sans bloquer la fenêtre principale. Les anciennes valeurs Mirivue restent
comprises ; les touches secondaires peuvent être conservées ou désactivées.
Annuler ne change pas les raccourcis. Les valeurs validées sont enregistrées
dans les réglages propres à Mirivue, pas dans ceux de Dolphin.

KDE conserve globalement la taille de ce dialogue, exception acceptée par
l’utilisateur. Les schémas explicitement créés dans le dialogue sont ceux du
composant org.pdenams.Mirivue.Qt. Les résultats ci-dessus sont historiques ;
les contrôles actuels et leurs limites figurent dans VALIDATION-RC193.md.
