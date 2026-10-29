# Critères de publication de Mirivue KDE 1.0

État courant : RC194. Référence : Dolphin v26.08.2.

Les fonctions sont gelées depuis la RC192. Les changements de portée
intervenus depuis les premières annonces de gel font partie du développement
antérieur ; les anciens résultats ne suffisent pas à valider la version actuelle.
RC192 est limitée aux coûts de refiltrage, de recherche des lignes, de comptage
et à la cohérence de la documentation. Aucun nouveau changement d’ergonomie,
composant graphique ou moteur n’est prévu avant la version stable.

## Documents qui font foi

- `LISEZ-MOI-KDE.txt` : installation et point d’entrée des documents.
- `VALIDATION-RC194.md` : exécutions réellement effectuées et limites.
- `PARITE-DOLPHIN.md` : comportements comparés et écarts volontaires.
- `A-verifier-RC194.md` : scénarios Plasma restant à valider.
- `CHANGELOG.md` : historique. Les autres rapports CORRECTIFS/VALIDATION sont
  historiques ; ils ne remplacent pas le bilan courant.

## Parcours de référence sur CachyOS KDE

1. Dans les sources extraites, exécuter `./Valider-RC194.sh`. Ce script compile
   le moteur, les assistants KIO et les contrôles graphiques dans un dossier
   jetable, puis lance la suite intégrale. Tous les tests doivent réussir,
   sans échec ni test graphique ignoré sur la machine de référence.
2. Exécuter `./Construire-paquet-CachyOS.sh`, puis installer le paquet produit :
   sudo pacman -U ./mirivue-kde-1.0.0rc194-1-x86_64.pkg.tar.zst
3. Exécuter `./Verifier-installation-RC194.sh` dans la session Plasma : version,
   lanceur, intégration KDE et démarrage réel doivent réussir.
4. Conserver les résultats des scénarios de `A-verifier-RC194.md`. Les opérations
   destructives se vérifient uniquement sur des fichiers jetables.

## Conditions pour la version stable

- Trois suites complètes consécutives réussies, avec journaux bruts, nombre de
  tests, durée et code de sortie. Les suites ciblées ne satisfont pas ce critère.
- Compilation native neuve et contrôle du paquet installé sur la machine cible.
- Scénarios de fichiers ext4 et NTFS3, conflits, annulation, corbeille et
  restauration réussis ; toute perte ou écrasement non demandé bloque la sortie.
- Protocoles distants et systèmes de fichiers non essayés clairement annoncés
  comme non validés ; aucune extension de garantie par simple lecture du code.
- Contrôle de PipeWire, des aperçus et d’une session prolongée avec plusieurs
  opérations ; mise à jour et retour arrière vérifiés pour chaque mode distribué.

Aucun de ces essais n’est déclaré réussi par le seul numéro RC192. Les limites
et les exécutions actuelles sont consignées dans `VALIDATION-RC194.md`.

## Correction d’un défaut après le gel

Refuser les nouvelles fonctions, les refontes, les retouches d’apparence sans
défaut reproduit et les nettoyages généraux. Pour un défaut : le reproduire,
ajouter un test qui échoue, appliquer le correctif minimal, publier un correctif
tracé dans le changelog et rejouer les suites et les scénarios concernés.
Une régression bloquante rouvre la validation : elle ne devient pas un écart
volontaire pour permettre la publication. Conserver l’archive précédente.

RC193 est un correctif de conformité demandé pour le menu d’une sélection de
plusieurs fichiers : ouverture via KFileItemActions comme Dolphin v26.08.2.
Il conserve les autres fonctions et réouvre la validation de ce parcours ;
il ne vaut pas validation de la version stable. Voir VALIDATION-RC194.md.

RC194 corrige uniquement le protocole automatique de validation des menus et
l’isolation du bus de test. L’application et ses sources natives restent
identiques à RC193. Sur Fedora, utiliser Valider-RC194.sh puis Installer.sh,
sans construire de paquet CachyOS. Les journaux complets sont conservés dans
$XDG_STATE_HOME/mirivue-kde/validation (par défaut ~/.local/state).
La réussite de Fedora 44 KDE reste à établir ; voir VALIDATION-RC194.md.
