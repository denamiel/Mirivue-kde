# Mirivue KDE 1.0.0-beta.5 — correctifs C1, H1 et H2 (branche locale)

Branche `correctifs/c1-h1-h2-urls-kio`, créée depuis `cb5ed13` (beta.5).
Version visible inchangée : aucun paquet RPM ou Pacman n’est produit par
cette branche.

## Anomalies corrigées

- **C1** — Les assistants natifs relisaient les URL avec `QUrl::fromUserInput()`,
  qui retire les blancs de début et de fin (`userInput.trimmed()` dans qtbase).
  Un nom terminé par un blanc Unicode non encodé (U+0020, U+00A0, U+2003,
  U+3000, U+0085) désignait alors un autre élément : « photo␠ » mis à la
  corbeille, supprimé, renommé, copié ou listé à la place de… « photo ».
- **H1** — Les sources déposées sur la Corbeille, ou envoyées vers une
  destination URI, passaient par `Location.uri`, qui appelle `Path.resolve()`.
  La cible d’un lien symbolique était traitée au lieu du lien lui-même.
- **H2** — Supprimer une ligne KIO non locale (`sftp://`, `smb://`, `desktop:/`,
  `trash:/`…) levait `AttributeError` dans le contrôle d’empreinte local, avant
  toute requête KIO.

## Modifications

- `native/kio-service.cpp` : `QUrl(valeur, QUrl::TolerantMode)` ; une requête
  contenant une source qui n’est pas une URL complète est refusée en entier.
- `native/kio-transfer.cpp` : même analyse ; sources et destination validées,
  refus explicite (`ok: false`, code 2).
- `native/kio-list.cpp` : une URL complète est analysée exactement ;
  `fromUserInput()` reste réservé à une entrée sans schéma.
- `mirivue/movement.py` : `kio_source_url()` construit l’URL des sources sans
  suivre les liens (`drop_operation`, branche URI de `move_entries`).
- `mirivue/app.py` :
  - `delete_selected` ne calcule l’empreinte que pour les chemins locaux et
    transmet les URI inchangées ; dans la Corbeille, Suppr est sans effet et
    Maj+Suppr utilise la suppression définitive de la Corbeille ;
  - comme dans Dolphin, « Mettre à la corbeille » est désactivé dans la vue
    Corbeille, avec une explication ; « Supprimer définitivement » reste actif.
- `tests/test_c1_h1_h2_regressions.py` : 32 tests au premier tour (21 scénarios d’origine,
  refus des URL incomplètes, opérations sur les liens symboliques) ;
  `tests/test_delete_action_state.py` : états des deux actions de suppression.
- `.github/workflows/fedora-package.yml` : ces deux suites rejoignent les
  contrôles graphiques Fedora.

La suite de régression redirige `HOME`, `XDG_*` et `kiorc` vers un dossier
temporaire : la Corbeille et les confirmations KDE de la session ne sont jamais
utilisées. Les hôtes distants emploient le domaine réservé `.invalid` et sont
enregistrés sans être contactés. Un dialogue modal inattendu fait échouer le
test au lieu de le bloquer.

## Validation

Environnement : Fedora 45, Qt 6.11.2, KF6 KIO 6.31.0, PySide6 6.11.2,
Python 3.15, `QT_QPA_PLATFORM=offscreen`, bus D-Bus privé.

- Compilation Release de toutes les cibles natives (`-Wall -Wextra`) : réussie ;
  seuls deux avertissements préexistants dans `native/dolphin-view.cpp`.
- Premier tour — nouvelle suite : **32/32 réussis** sur la branche. Sur le code et les
  assistants beta.5 d’origine, 26 échouent ; les 6 réussis sont les témoins et
  contrôles de non-régression attendus.
- Non-régression, branche comparée au code d’origine dans les mêmes conditions :

  | Lot | Suites | OK | Échecs | Délai | Différences |
  |---|---|---|---|---|---|
  | Non graphiques | 83 | 78 | 5 | 0 | aucune |
  | Graphiques ciblées | 13 | 8 | 4 | 1 | aucune |
  | Graphiques CI Fedora restantes | 4 | 3 | 1 | 0 | aucune |

Échecs préexistants, identiques avant et après :
`test_compact_activity_area` et `test_freeze_documents` (tests obsolètes) ;
`test_native_contract_timing`, `test_native_view_palette`,
`test_rc181_package`, `test_context_providers` et une erreur de
`test_rc181_freeze` (outils de test natifs non construits) ; l’autre échec de
`test_rc181_freeze` signale que `native/clipboard-paste.cpp` et
`native/file-properties.cpp` manquent dans l’index MIT de `LICENCES-TIERS.md` ;
`test_native_kio_transfers_integration` (exige `/sys` en lecture seule, comme
en conteneur) ; `test_native_file_management_gui` et `test_native_clipboard_gui`
(libellés anglais attendus : les deux réussissent en `LANG=C.UTF-8`) ;
`test_pane_regressions_gui` se bloque sur la boîte modale « Opérations en
cours » ouverte par `rename_f2` lorsque le renommage KIO asynchrone du
sous-test précédent n’est pas terminé.

## Second tour, après la revue indépendante

### Constats démontrés

- **Corbeille sur sftp/smb.** Sur un vrai serveur SFTP (privé, `127.0.0.1`),
  `KIO::trash()` échoue avec `ERR_ACCESS_DENIED` (« Accès refusé à
  trash:/… »), et non `ERR_TRASH_NOT_AVAILABLE`. `DeleteOrTrashJob` affiche donc
  une erreur sans jamais supprimer : il ne bascule vers une suppression que pour
  `ERR_TRASH_NOT_AVAILABLE` ou `ERR_TRASH_FILE_TOO_LARGE`, et toujours avec
  `ForceConfirmation`. L’action restait néanmoins proposée alors qu’elle échoue
  toujours ; Dolphin la désactive (`isLocal() && supportsMoving()`).
- **Navigation et Emplacements.** Avec un favori sur « Dossier » et un dossier
  « Dossier␠ », le titre d’emplacement et le dernier bouton du fil d’Ariane
  désignaient le favori « Dossier ». `add_place` créait le favori sans l’espace.
- **Messages d’erreur.** Pour une copie, un déplacement ou un lien en échec, le
  service renvoyait `errorText()` : souvent une URL seule, sans explication.

### Corrections

- `native/location-url.h` : `mirivueLocationUrl()`. Un chemin absolu passe par
  `fromLocalFile`, une URL complète est analysée exactement, `fromUserInput`
  reste réservé à une saisie libre. Utilisé par `kio-places-widget.cpp` (titre,
  Emplacements, fil d’Ariane), `kio-places.cpp`, `kio-list.cpp` et `kio-open.cpp`.
- `mirivue/app.py` : `add_place` n’appelle plus `fromUserInput` ;
  `selection_supports_trash()` reprend la règle de Dolphin, à partir du
  `UDS_LOCAL_PATH` conservé dans les lignes KIO (`metadata.remote_entry`).
  Pour une sélection non locale, « Mettre à la corbeille » est grisé avec une
  explication, le menu contextuel ne propose que « Supprimer définitivement… »,
  et Suppr n’envoie aucune requête.
- `native/kio-service.cpp` : le message complet `errorString()` est transmis
  lorsqu’une erreur a un texte ; une erreur sans texte reste vide, comme le
  suppose la reconnaissance des conflits annulés.

**Différence volontaire avec Dolphin.** Dans un dossier distant, Dolphin associe
Suppr à la suppression définitive ; si l’utilisateur a désactivé la
confirmation de suppression, Suppr y efface donc sans question. Mirivue
n’envoie rien sur Suppr et réserve la suppression définitive à Maj+Suppr ou au
menu, conformément à l’exigence : « Mettre à la corbeille » ne devient jamais
une suppression.

### Expériences SFTP réelles

Serveur `sshd` non privilégié sur `127.0.0.1`, clés jetables ; client KIO dans
un espace de noms utilisateur et de montage où `$HOME/.ssh` est un `tmpfs` de
test : la configuration SSH de la session n’est ni lue ni modifiée.

| Essai | Résultat avec la branche |
|---|---|
| Corbeille sur un fichier sftp | aucune requête KIO, message explicite, fichier conservé |
| Suppression définitive, confirmation désactivée | fichier supprimé |
| Suppression définitive, confirmation active, sans réponse | fichier conservé |
| « photo␠ » et « photo » distants, suppression de « photo␠ » | seul « photo␠ » est supprimé |
| Suppression d’un lien distant | le lien seul est supprimé, la cible reste |
| Copie d’un lien local vers sftp | KIO crée un fichier ordinaire portant le nom du lien (comportement de KIO) |
| « Créer un lien ici » vers sftp | refusé par KIO, sans rien créer |

### Tests et résultats

- Suite `test_c1_h1_h2_regressions.py` : 41 tests, dont 9 ajoutés au second
  tour (corbeille non locale, titre et fil d’Ariane, `add_place`, favori de
  bout en bout, `kio-list` sur un chemin absolu, confirmations KDE actives sans
  réponse, message d’erreur complet). **41/41** sur la branche, trois exécutions.
  Les nouveaux tests d’anomalie échouent sur la beta.5 et sur `65af341` ; les
  tests de confirmation réussissent partout, comme garde-fous.
- `test_delete_action_state.py` : 5/5.
- Non-régression après ce tour, mêmes conditions que la référence : 100 suites,
  **aucune différence** avec le code d’origine ; les deux suites dépendant de la
  langue réussissent en `LANG=C.UTF-8`.

## Troisième tour, après la deuxième revue

### Constat démontré : éligibilité et URL envoyée à KIO

`selection_supports_trash()` admettait une ligne KIO grâce à son
`UDS_LOCAL_PATH`, mais `delete_selected()` envoyait ensuite son URI à
`KIO::trash()`. Mesure directe (sonde C++, worker Plasma `desktop`) :
`KIO::trash("desktop:/fichier")` déplace bien le fichier dans la Corbeille,
mais la tâche signale un échec (`ERR_UNSUPPORTED_ACTION`, « Changing the
attributes of files is not supported with protocol trash »). Dans Mirivue,
l’erreur s’affichait en boîte modale dans le service : la requête restait sans
réponse jusqu’à l’arrêt du service, alors que l’élément était déjà dans la
Corbeille. Il n’y avait pas de suppression, mais un faux échec. Le même essai
par `file://` (le chemin local) réussit sans erreur.

### Correction

Pour une mise à la corbeille, une ligne KIO admise par son chemin local est
transmise par ce chemin (`file://`). Ce chemin est aussi soumis au contrôle
d’empreinte avant envoi. La suppression définitive garde l’URI d’origine.

### Tests

- `test_trash_of_kio_row_uses_its_local_path_end_to_end` : vrai service, vraie
  Corbeille isolée ; vérifie l’URL réellement envoyée, la réussite signalée et
  l’entrée de Corbeille. Fonctionne sans le worker Plasma (CI comprise).
- `test_trash_of_real_desktop_row_reports_success` : chaîne réelle
  `kio-list desktop:/` → ligne Mirivue → mise à la corbeille. Exécuté seulement
  si le worker `desktop` est installé ; ce n’est pas le cas dans le conteneur
  de CI.
- `test_permanent_deletion_of_kio_row_keeps_its_url` : la suppression
  définitive envoie toujours l’URI.
- Sur `6b54b73`, les deux premiers échouent : URI envoyée au lieu du chemin
  local, puis faux échec. Sur la branche : **43/43**, aucun test sauté en local.

### Procédure manuelle

La procédure ne démarre plus de serveur SSH : `sshd` écoute par défaut sur
toutes les interfaces, et la zone de pare-feu Fedora Workstation peut
l’autoriser. Un seul script prépare tout :
`tests/manual/lancer-validation-c1-h1-h2.sh`. Il ne change pas de branche, ne
touche pas au paquet installé, demande avant tout `sudo dnf install`, et
travaille uniquement dans `/var/tmp/mirivue-validation-$USER` et
`~/Mirivue-essais-C1H1H2`.

## Limites

- Aucune session Plasma réelle : rendu, focus, glisser-déposer à la souris et
  dialogues de confirmation KDE ne sont pas observés.
- Les confirmations KIO sont désactivées dans les essais automatisés.
- SFTP est vérifié sur un serveur local réel ; SMB ne l’est pas (même chemin
  KIO, à confirmer sur un partage de test maîtrisé).
- Déposer une ligne `desktop:/` sur un panneau Corbeille passe encore son URI à
  KIO : faux échec possible, l’élément étant tout de même mis à la Corbeille.
  Le glisser-déposer ne connaît pas le chemin local de la ligne.
- 31 suites graphiques et les tests natifs C++ (`native/tests`) n’ont pas été
  exécutés.

## Risques résiduels

- Annuler une opération pendant qu’un dialogue de confirmation KDE est ouvert
  laisse le service sans réponse ; Mirivue le redémarre après 5 s, ce qui
  efface l’historique d’annulation KIO de la session (comportement antérieur).
- Copier un lien vers sftp crée un fichier ordinaire : KIO déréférence le lien.
- Copier ou déplacer un lien vers une URI transmet désormais le lien, comme
  Dolphin ; une destination sans liens symboliques peut produire une erreur KIO.
- `Location.uri` résout toujours les liens pour les propriétés natives et la
  navigation.
- Les assistants natifs doivent être recompilés et livrés pour que C1 soit
  corrigé.

## Validation manuelle restant à faire

Procédure complète, avec fichiers d’essai isolés :
`docs/VALIDATION-MANUELLE-C1-H1-H2.md`, lancée par
`tests/manual/lancer-validation-c1-h1-h2.sh`.
