# Mirivue KDE 1.0.0-beta.3 — moteur de fichiers et validation

Version visible : `1.0.0-beta.3` ; Python : `1.0.0b3` ; première révision RPM :
`0.198.beta3.1`. Les versions suivantes sont publiées après réussite des contrôles
obligatoires GitHub Actions, via la branche `publication` utilisée par COPR.

## Un seul moteur de transfert pour l’interface

Copier, couper/coller, déplacer entre panneaux, glisser-déposer et regrouper
utilisent KIO. La duplication et les destinations renommées utilisent ses
opérations `copyAs`/`moveAs`. Les fichiers compagnons XMP sont ajoutés aux
opérations. Corbeille, restauration et suppression définitive utilisent KIO.

L’ancien moteur Python (`MoveWorker`, `move_one`) et sa file d’attente sont
retirés. Ils n’étaient déjà plus appelés par les commandes de l’interface en
bêta 2. Il n’y a pas de reprise automatique en Python après un échec de KIO.
L’interface refuse le transfert si le service natif nécessaire est indisponible.

Les validations de noms et sélections, le suivi des opérations, les réservations
de chemins dans Mirivue et l’actualisation des panneaux restent en place.
Les renommages spécialisés, créations de fichiers depuis le presse-papiers,
traitements multimédias et certaines opérations d’archives restent du code
Python : ce ne sont pas un second moteur de copie/déplacement généraliste.
L’utilitaire de publication sans écrasement est notamment utilisé par les
archives et la création d’une copie MKV.

KIO gère les conflits, la progression détaillée, les erreurs et l’annulation.
Les opérations compatibles sont enregistrées dans son historique Annuler /
Rétablir. Une fermeture de fenêtre pendant un transfert laisse travailler
Mirivue en arrière-plan, puis l’application se ferme après les opérations.
Une exception inattendue du worker KIO produit un échec visible et journalisé,
plutôt qu’une opération restant indéfiniment affichée en cours.

## Contrôles obligatoires

| Domaine | Vérification | Périmètre |
|---|---|---|
| Copie et déplacement | inventaires, SHA-256 des résultats, fichiers vides/cachés, Unicode, liens | service KIO compilé réel, fichiers jetables |
| Deux systèmes de fichiers | aller et retour entre le disque du runner et `/dev/shm` | déplacement KIO réel ; source retirée après succès |
| Conflit et annulation | destination existante inchangée, source conservée ; annulation après soumission d’un déplacement | KIO réel ; ne prétend pas tester l’annulation à tous les instants d’une copie |
| Destination pleine | échec d’un déplacement d’un fichier vers un petit tmpfs privé réellement rempli ; source intacte | KIO réel, `/dev/shm` du conteneur CI uniquement |
| Destination en lecture seule | échec et source intacte | KIO réel, `/sys` monté en lecture seule dans le conteneur |
| Erreur inattendue | résultat d’échec émis une fois ; pas de seconde tentative | frontière du worker KIO contrôlée |
| Deux panneaux | copie/déplacement entre les vues, sélection des arrivées et miniatures | interface Qt ; transport substitué pour isoler la présentation |
| Opérations et fermeture | accès à l’historique, annulation ciblée, chargement des dossiers indépendant, fermeture en arrière-plan | interface Qt et scénarios de fin contrôlés |
| Dolphin | gestes, sélection, onglets, styles de vue, session et renommage | suites graphiques avec moteur de vue natif |
| Distribution | construction, installation, lancement, documents installés | Fedora 44/45 et contrôle Rawhide ; construction Arch séparée |

Les résultats effectivement réussis sont ceux du workflow correspondant dans
GitHub Actions. La présence d’un scénario ici ne constitue pas son résultat.

## Garanties et limites

**Mirivue n’ajoute pas un contrôle SHA-256 intégral à chaque copie KIO.** Les
empreintes ci-dessus sont calculées par les tests sur leurs résultats. Les
anciennes vérifications internes du moteur Python ne s’appliquaient déjà pas
aux transferts ordinaires de l’interface ; les conserver dans un moteur
inutilisé ne fournissait pas cette garantie.

Une opération portant sur plusieurs fichiers n’est pas une transaction : en
cas d’échec ou d’annulation, certains fichiers peuvent être déjà traités.
Vérifier les deux emplacements avant de recommencer. Ne pas supposer que KIO
publie toujours atomiquement une arborescence entière, ou supprime tout fichier
partiel dans tous les cas. Les réservations internes à Mirivue ne verrouillent
pas les autres applications qui écrivent dans les mêmes fichiers.

Les essais Qt offscreen et D-Bus isolé ne remplacent pas une session
Plasma/Wayland réelle. Le petit tmpfs ne valide pas tous les disques : NTFS,
SMB/SFTP, retrait physique d’un périphérique, suspension et coupure électrique
restent des scénarios à vérifier séparément. Cette version reste une bêta.
