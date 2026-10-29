# Menu contextuel et aperçu de renommage — RC193

## Personnaliser le clic droit

Dans Configurer Mirivue → Menu contextuel, rechercher une commande puis cocher
ou décocher son entrée. Appliquer enregistre le choix ; Annuler abandonne les
changements non appliqués. Réglages par défaut prépare les valeurs initiales,
qui ne sont enregistrées qu’en appliquant.

Les commandes intégrées configurables concernent notamment les modes de vue,
le tri, les ouvertures de dossiers, le terminal, les actions vers l’autre panneau
et les groupes Organiser, Outils multimédias et Fichiers associés. Les commandes essentielles
Ouvrir, Couper, Copier, Coller, Renommer, Corbeille et Propriétés restent disponibles.
Masquer une entrée retire seulement sa présence dans le menu du clic droit :
les menus principaux, la barre d’outils et les raccourcis restent utilisables.
L’option Supprimer définitivement réutilise le réglage existant ; le comportement
habituel de Maj pour les actions de suppression est conservé.

La liste inclut les services de kio/servicemenus et les extensions KF6 installées,
avec leurs libellés et icônes. Leurs cases utilisent kservicemenurc, groupe Show,
comme Dolphin : un changement de service est donc partagé avec Dolphin et les
applications qui utilisent cette configuration KDE. Les commandes intégrées
restent des préférences propres à Mirivue ; dolphinrc n’est pas modifié.
Les extensions de gestion de versions spécifiques à Dolphin ne sont pas proposées.

Télécharger des services utilise le bouton natif KNewStuff et la configuration
Dolphin Service Menus. Le composant servicemenuinstaller fourni avec Dolphin est
nécessaire ; en son absence, le bouton est désactivé avec une explication.
Les services peuvent exécuter des programmes : leur installation reste une action
explicite dans le dialogue KDE. Aucun service n’est installé pendant la validation.
Le bouton Raccourcis ouvre la configuration existante des raccourcis de Mirivue.

Si la bibliothèque native est indisponible, la page de secours ne propose que
les commandes intégrées et indique la limite. Les paquets compilent cette
bibliothèque et déclarent knewstuff comme dépendance directe.

## Repérer les renommages proposés

Dans l’outil intégré, seul le nouveau nom effectivement modifié et sans conflit
est en gras. Un nom inchangé reste dans la présentation normale du thème.
Revenir au nom initial retire immédiatement le gras. Les règles automatiques et
les retouches manuelles passent par la même validation.

La légende « En gras : noms qui seront modifiés » explique cette indication.
Une proposition invalide ou en conflit garde le diagnostic de validation ; elle
n’est pas présentée comme un renommage applicable. La colonne Nom actuel ne
change pas de présentation. Aucune couleur, famille ou taille de police n’est
imposée. Le gras est un choix de lisibilité pour cet outil propre à Mirivue,
pas la reproduction revendiquée d’un aperçu équivalent de Dolphin.

Ce changement ne modifie ni les règles de nommage ni les opérations sur disque.

## Fournisseurs et doublons — RC193

La liste présente les libellés KDE, sans leur ajouter un identifiant technique
ou un nom de fournisseur. Le chemin du fichier reste accessible au survol,
comme dans Dolphin v26.08.2. Le libellé seul ne sert jamais à fusionner des commandes.

Konsole n’a qu’une case quand le service runInKonsole est installé : elle
utilise la préférence KDE. Le menu préfère cette action quand KIO la propose
pour la sélection. Une éventuelle commande de secours respecte la même case.
Sans service installé, le réglage propre à Mirivue reprend son rôle.
La même règle s’applique à la création d’archives et au fournisseur Ark ; les
commandes de secours sont retirées seulement si une action native équivalente
est effectivement présente. L’extraction est identifiée par son fournisseur,
sans recherche du mot « Extraire » dans la traduction.

Les services restent insérés quand Organiser ou Outils multimédias est masqué.
Les groupes ordinaires de KIO sont construits ensemble pour éviter plusieurs
sous-menus Actions. Les extensions d’archive sont demandées une fois chacune
par les API publiques de KFileItemActions ; KIO garde ses contrôles de types,
de protocoles, d’autorisation et ses mécanismes de chargement.

Déplacer vers un nouveau dossier conserve la commande intégrée à Mirivue et
son service KIO qui suit l’annulation, y compris pour un seul fichier. Une seconde action issue de l’extension
movetonewfolderitemaction de Dolphin n’est plus ajoutée au menu de Mirivue.
Sa préférence globale dans Dolphin reste inchangée. Une nouvelle case propre
à Mirivue permet de masquer sa commande ; au premier usage elle reprend le
choix KDE existant si aucune préférence Mirivue n’a encore été enregistrée.

Renommage avancé et Renommer à partir des métadonnées restent deux accès à
l’outil intégré, avec leurs propositions initiales respectives. Exécuter le
fichier reste différent d’Ouvrir un terminal ici ou d’afficher le panneau F4.

Les noms génériques fournis par KDE (Installer…, Définir comme…) restent ceux
de KDE ; les identifiants internes distincts conservent les cases des homonymes.

## RC193 — accès au renommage

« Renommage avancé… » reste dans Outils → Renommer et organiser et n'est plus
répété dans Organiser au clic droit. Renommer (F2) conserve le renommage direct
pour un fichier et le choix de l'outil configuré pour une sélection multiple.
L'accès explicite au logiciel externe reste dans le menu contextuel.

## Cohérence des commandes RC193

Les actions de modification des sous-menus Organiser et Métadonnées utilisent
les mêmes gardes que le menu Outils. La création d'archive est réservée à une
sélection locale, disponible et hors consultation d'archive. Les conditions
d'affichage propres au type de média restent inchangées.
