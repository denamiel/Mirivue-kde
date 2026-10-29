# Copie et déplacement entre panneaux — RC170

## Défauts reproduits et corrections

Le contrôleur natif issu de Dolphin appelle supportsDropping(-1) lorsque la
souris survole le fond d’une vue. L’adaptateur de Mirivue renvoyait seulement
isDir(index), donc faux pour cet index. L’entrée du glissement était acceptée,
mais son déplacement dans la vue était refusé dans les trois modes. Un test
qui injectait directement le dépôt final pouvait réussir malgré ce refus ;
il vérifie désormais aussi l’acceptation des événements intermédiaires.

L’adaptateur accepte maintenant le fond de la vue, y compris un dossier vide.
Le contrôleur de Dolphin conserve la gestion du glissement et des cibles.
Les vérifications des destinations et des fichiers réservés restent actives.

Les dépôts vers Emplacements et les fils d’Ariane restent confiés à
KFilePlacesView, KUrlNavigator et KIO::drop. Leur retour appelait auparavant
refresh_other_panes, qui exclut le panneau actif et recharge les autres.
La nouvelle méthode native_drop_completed synchronise les dossiers visibles,
y compris la source active. Une copie conserve sa source ; un déplacement
réussi la retire d’après le système de fichiers, sans deviner le choix fait
dans le menu de KIO.

La reconfiguration de la surveillance conserve désormais les différences en
attente dans les dossiers déjà suivis. La synchronisation vérifie aussi les
lignes connues qui manquent dans l’inventaire : cela couvre un fichier arrivé
puis déplacé avant que la surveillance ait enregistré son arrivée. Les liens
symboliques cassés ne sont pas confondus avec des fichiers supprimés. Les
modèles locaux sont mis à jour par lignes, sans réinitialisation des panneaux.
Si le dossier affiché lui-même a disparu, le retour vers un parent existant
est conservé. Les emplacements distants conservent leur parcours de liste KIO.

Les liens créés entre panneaux bénéficient aussi de la mise à jour locale et
de la sélection du résultat, tout en conservant la source. Les URL KIO sont
conservées dans la sélection et le presse-papiers ; la recherche locale des
fichiers associés ne transforme plus une URL distante en chemin local. Le
collage distant vérifie le service permanent réellement utilisé.

## Contrôles automatisés

tests/test_panel_transfers_gui.py construit une vraie fenêtre scindée et
utilise le moteur natif. Les événements Qt passent par les vues et leurs
gestionnaires, puis par le vrai KioTransferWorker et son retour dans l’interface.
Les essais utilisent exclusivement des fichiers et dossiers jetables.

- Copie et déplacement dans les neuf couples de vues, dans les deux sens :
  36 transferts, avec vérification du contenu, de la présence de la source,
  des lignes affichées et de la sélection du résultat.
- Ctrl+C/Ctrl+V, Ctrl+X/Ctrl+V et Maj+F5/Maj+F6 dans les trois vues : 12 transferts.
- Menu réel de dépôt, piloté au clavier : Copier ici, Déplacer ici, Créer un
  lien ici et Annuler. Le choix Annuler ne lance aucune opération.
- Ctrl+Maj crée un lien dans chacune des trois vues et conserve la source.
- Dépôt dans un sous-dossier, sélection multiple, noms accentués et avec
  espaces, et déplacement d’une arborescence.
- Autorisation de démarrage d’un glissement depuis la sélection native.
- Six scénarios de retour d’une opération native, copie ou déplacement dans
  les trois vues, avec reconfiguration des surveillances avant le retour :
  la source active et la destination sont synchronisées sans navigation ni
  réinitialisation de modèle.
- Conservation des URL SMB/SFTP dans la sélection et le presse-papiers, puis
  transmission au parcours de collage KIO.

tests/test_dolphin_view_engine.py vérifie également le survol du fond des
trois vues, vides et remplies, et l’acceptation de chaque événement jusqu’au
dépôt. Les scénarios antérieurs de sélection, miniatures et durée sont conservés.

## Portée et limites

Le transport KIO des nouveaux essais de fichiers est remplacé par une
implémentation de test écrivant dans le dossier jetable. Les véritables
événements Qt, le travailleur, les signaux de fin, les fichiers et les mises
à jour des modèles sont exercés ; les 55 transferts de ce parcours ne sont
pas présentés comme des opérations du vrai service KIO.

Cet environnement refuse la création de la session D-Bus nécessaire aux
essais de bureau. La connexion à un serveur SMB/SFTP, les conflits natifs,
les opérations interdisques et le glissement physique sous Wayland ne sont
donc pas validés par ces nouveaux tests. Le code KIO de ces opérations reste
inchangé ; Verifier-installation-RC170.sh contrôle toujours le service natif
sur la machine d’installation. Aucun nouvel essai manuel n’est demandé.
