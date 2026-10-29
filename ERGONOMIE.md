# Affichage simplifié de la RC193

La colonne État est retirée des vues et des paramètres de colonnes.
Les noms de fichiers suivent les couleurs normales du thème KDE. Les anciens
réglages de colonnes sont repris sans réafficher État ni décaler les autres
informations. Les données d’analyse restent disponibles dans les infobulles,
les rapports d’opérations et les outils de recherche de doublons.
Les étiquettes personnelles restent conservées et lisibles au survol du fichier.

Les critères d’informations techniques manquantes suivent le type du média :
aucune résolution d’image n’est demandée aux fichiers audio. Un champ absent
ne signifie pas que le fichier est endommagé.

La vérification historique de ce changement comptait 358 tests, dont quatre contrôles spécifiques à ce
changement et les 15 interactions ergonomiques introduites dans la RC164.
Les tests sont exécutés hors écran avec le moteur natif ; ils ne constituent
pas une observation de la session Plasma ni une installation de paquet CachyOS.

Les menus et réglages corrigés conservent les widgets, couleurs, polices,
actions KIO et moteur de fichiers natifs existants. Les outils spécialisés
complètent les commandes habituelles de Dolphin.

| Besoin | Accès dans la RC164 |
|---|---|
| Renommer un fichier | F2, modification directe du nom |
| Renommer une sélection avec l’outil configuré | F2 sur plusieurs éléments |
| Utiliser explicitement l’outil intégré | Outils → Renommer et organiser → Renommage avancé |
| Proposer des noms à partir des balises | Méthode À partir des métadonnées dans le même aperçu |
| Utiliser un autre logiciel | Renommer avec le nom du logiciel configuré |
| Changer les colonnes du panneau actif | Affichage → Colonnes de la vue détaillée, ou menu de l’en-tête |
| Changer les informations en vues Icônes et Compacte | Affichage → Informations sous les icônes |
| Appliquer une configuration de colonnes | Affichage → Configurations de colonnes |
| Modifier les configurations proposées | Configurer Mirivue → Configurations de colonnes ; aucun changement implicite de la vue actuelle |
| Suivre les opérations | Outils → Opérations ; onglets Transferts et Analyses dans une seule fenêtre |
| Ouvrir une nouvelle fenêtre | Fichier → Nouvelle fenêtre, Ctrl+N |
| Filtrer ou rechercher | Ctrl+I filtre les noms affichés ; Ctrl+F recherche depuis le dossier actif |

Les anciennes dispositions de barre d’outils sont conservées. La disposition
initiale allégée regroupe les trois modes de vue dans un bouton de sélection ;
les boutons individuels restent configurables. Les informations communes aux
médias ne figurent qu’une fois dans le menu des colonnes.

Les paramètres sont regroupés et défilables. Leur recherche indique les
correspondances et l’absence de résultat. Le réglage du panneau d’aperçu au
démarrage est enregistré sans ouvrir ou fermer le panneau de la session.
Le résumé du dossier utilise les éléments réellement affichés après filtrage.
L’historique de lecture sans interface d’exploitation n’est plus alimenté ni
proposé ; les données existantes sont conservées. La liste des fichiers récents
reste disponible avec son choix de confidentialité indépendant.

## Vérification historique

Les résultats qui suivent proviennent des versions antérieures. Les essais
propres à RC193 sont détaillés dans VALIDATION-RC193.md.

- Suite de 358 tests exécutée avec succès, dont 15 tests d’interactions
  ergonomiques et quatre contrôles du retrait de la colonne État et des couleurs.
  Les sources C++ sont identiques à la RC164 et le moteur natif compilé est utilisé.
- Le renommage réel d’un fichier jetable est vérifié en présence d’un autre nom
  en conflit : le fichier existant n’est pas remplacé et la proposition valide
  est exécutée.
- Vérification visuelle hors écran des paramètres Général, Colonnes, Aperçus
  et de la fenêtre des opérations, avec Qt/PySide6 6.12 et un style Qt natif.
- Syntaxe de tous les scripts shell et compilation syntaxique Python vérifiées.

Ces contrôles ne sont pas une observation de la session Plasma de l’utilisateur.
Le paquet CachyOS n’a pas été construit ou installé sur cet hôte Ubuntu.
Une tentative complémentaire de liaison de tous les assistants KIO sur cet
hôte est limitée par des bibliothèques système absentes (Solid/WindowSystem) ;
ces sources natives sont inchangées dans la RC164. Le script de construction
fourni compile toutes les cibles sur la machine CachyOS cohérente.
