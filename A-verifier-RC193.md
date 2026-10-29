# Essais restant à réaliser sur Plasma — RC193

Référence : Dolphin v26.08.2. Ces scénarios ne sont PAS déclarés validés par
les tests hors écran. Employer des fichiers jetables et conserver le paquet antérieur.

## Wayland : rappel des fenêtres

1. Ouvrir Mirivue agrandi, avec deux onglets et une seconde fenêtre.
2. Depuis une autre application, utiliser « Afficher dans le dossier ».
3. Répéter avec un dossier déjà ouvert, un nouveau, puis Mirivue réduit.
4. Contrôler la fenêtre active et le maintien de l'état agrandi.

Attendu : pas de doublon ; choix onglets/fenêtres respecté. Le jeton ne contourne
pas les décisions de focus de KWin. Un délai après Dispatch n'est pas réémis.

## Construction, pacman et retour arrière

1. Exécuter Valider-RC193.sh puis Construire-paquet-CachyOS.sh.
2. Installer le paquet produit et exécuter Verifier-installation-RC193.sh.
3. Vérifier la version, les raccourcis et les préférences conservées.
4. Revenir au paquet précédent, puis réinstaller RC193.

Attendu : un seul lanceur actif, mêmes préférences et licences présentes dans
/usr/share/licenses/mirivue-kde. Les scripts ne valident pas à eux seuls Wayland.

## Corbeille KIO réelle et transferts

1. Préparer deux dossiers et un petit fichier, sur ext4 puis NTFS3.
2. Mettre à la corbeille dans Mirivue et vérifier dans Dolphin ; restaurer.
3. Copier/déplacer entre panneaux et annuler avec Ctrl+Z.
4. Fermer un onglet pendant le chargement d'un autre dossier.

Attendu : bon fichier et bonne destination, une seule opération/confirmation prévue,
aucune action sur un panneau fermé. Le test de service doit utiliser DeleteOrTrashJob.

## Dépôt sur onglet

1. Ouvrir deux dossiers dans deux onglets.
2. Glisser un fichier sur l'autre onglet, attendre son activation.
3. Déposer et choisir Copier ; refaire avec Déplacer puis annulation.

Attendu : activation au délai prévu, bon dossier, aucune ouverture supplémentaire.

## Détachement

1. Ouvrir trois onglets dont un scindé ; personnaliser son titre/proportions.
2. Détacher cet onglet pendant son chargement.
3. Vérifier ses deux dossiers et son panneau actif dans la nouvelle fenêtre.
4. Rappeler l'un de ses dossiers depuis une autre application.

Attendu : une seule fenêtre, contenu conservé, fenêtre détachée retrouvée sur le bus.
En cas d'échec de lancement, l'onglet d'origine doit rester disponible.

## Services et styles

1. Ouvrir les réglages sous Breeze et Union ; vérifier les libellés sans suffixe technique.
2. Modifier une case KDE, appliquer et constater le même choix dans Dolphin.
3. Vérifier le chemin de provenance au survol et deux services homonymes distincts.
4. Saisir un chemin, valider puis changer de panneau.

Attendu : mêmes identifiants de stockage ; aucun service installé/exécuté par la seule
ouverture des réglages. Les couleurs/cadres de l'application ne sont pas modifiés.

## Style de date

Dans Général → Affichage, choisir Relative puis Absolue et appliquer. Les deux
panneaux doivent refléter le choix, le tri restant chronologique. Fermer puis
rouvrir les paramètres : le choix doit persister. Ce scénario Plasma n'a pas
été exécuté ici ; les formulaires et le contrôleur ont été testés hors écran.

## Accès au renommage

Le clic droit ne répète plus Renommage avancé dans Organiser. L'outil reste
dans Outils → Renommer et organiser. F2 et le renommage multiple restent identiques.
Les contrôles ciblés sont décrits dans VALIDATION-RC193.md ; Plasma non déclaré validé.

## Disponibilité des commandes

- Créer une archive reste inactif pour une sélection distante dans Outils et au clic droit.
- Les commandes de modification sont inactives pendant un chargement, dans une
  archive ou si la sélection est utilisée par une opération.
- L'outil externe se configure même avec l'outil intégré choisi pour F2.
- Les deux destinations des commandes de terminal sont expliquées au survol.

Ces essais en session Plasma ne sont pas déclarés exécutés sur cet hôte.

## Barre d’outils et disposition

- Style Breeze/Union et écran à mise à l'échelle : ouverture du dialogue KDE.
- Ancienne disposition personnalisée : même ordre et même côté des chemins.
- Appliquer une disposition avec séparateur et espace ; relancer Mirivue et vérifier.
- Annuler sans Appliquer conserve les réglages ; Annuler après Appliquer conserve
  le dernier état appliqué ; Réglages par défaut suit la confirmation KDE.
- Le séparateur des panneaux et les chemins restent utilisables après ces changements.

Ces essais en session Plasma ne sont pas déclarés exécutés ici. Les scénarios
Wayland, pacman, Corbeille KIO, glisser d'onglet et détachement restent distincts.

## Recherche dans les paramètres

Le contrôle graphique doit réussir après la recherche Colonnes et la sélection
de Configurations de colonnes. Il reste inclus dans ./Valider-RC193.sh et dans
le vérificateur d'installation. La suite complète n'a pas été rejouée ici.

## Menus, raccourcis et groupes de paramètres

Les points suivants restent à observer sous Plasma ; ils ne sont pas déclarés
validés sur cet hôte. Le parcours automatique Valider-RC193.sh reste obligatoire.

- Ouvrir le menu principal avec F10, puis afficher/masquer la barre de menus ;
  toutes les commandes spécialisées doivent rester accessibles dans les menus.
- Personnaliser la barre d’outils avec deux boutons Menu, puis en retirer un :
  chaque bouton restant doit ouvrir le menu natif sans erreur.
- Modifier une touche principale et une touche secondaire, valider et relancer :
  les deux choix doivent rester ; Annuler ne doit rien changer.
- Vérifier le dialogue KDE avec Breeze et Union et une mise à l’échelle.
- Dans Aperçus et lecture, retrouver les trois groupes et leurs valeurs.
- Retrouver les commandes de chemins dans Édition et la durée dans Outils.
- Wayland, installation pacman, corbeille KIO, glisser d’onglet et détachement :
  les scénarios existants restent requis ; ils ne sont pas couverts par les
  contrôles ciblés RC193.

## Navigation au clavier

La validation automatique conserve le parcours complet. Le test Tab/Maj+Tab
entre les panneaux doit réussir dans Détails, Icônes et Compacte. Plusieurs
passages au clavier sur le bouton Menu ne doivent altérer ni Propriétés ni
Coller ni les autres commandes. Les essais Plasma/Wayland et pacman déjà
listés ne sont pas déclarés validés par le présent correctif.

## Ouverture multiple — correctif RC193

Sélectionner plusieurs vidéos puis ouvrir le menu contextuel. Les applications
proposées en tête et dans Ouvrir avec doivent être celles communes à la sélection,
comme dans Dolphin avec les mêmes associations KDE. L’action choisie doit recevoir
la sélection complète. Refaire avec deux formats vidéo ; les applications qui
ne prennent en charge qu’un seul format ne doivent pas être proposées pour tous.
Les contrôles automatiques utilisent des associations jetables et n’ouvrent pas
de lecteur réel ; le comportement de mpv et des fenêtres sous Plasma reste non
validé sur cet hôte. Les autres scénarios de session existants sont conservés.
