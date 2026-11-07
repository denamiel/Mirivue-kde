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
- `tests/test_c1_h1_h2_regressions.py` : 32 tests (21 scénarios d’origine,
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
- Nouvelle suite : **32/32 réussis** sur la branche. Sur le code et les
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

## Limites

- Aucune session Plasma réelle : rendu, focus, glisser-déposer à la souris et
  dialogues de confirmation KDE ne sont pas observés.
- Les confirmations KIO sont désactivées dans les essais automatisés.
- sftp et smb ne sont pas essayés contre de vrais serveurs ; la mise à la
  corbeille distante reste décidée par KIO (`KIO::trash` ne gère que les
  fichiers locaux).
- 31 suites graphiques et les tests natifs C++ (`native/tests`) n’ont pas été
  exécutés.

## Risques résiduels

- La navigation et les Emplacements utilisent encore `fromUserInput()`
  (`kio-places-widget.cpp`, `kio-places.cpp`, `add_place`) : un fil d’Ariane
  ou un favori sur « Dossier␠ » peut viser « Dossier », sans modifier de fichier.
- Copier ou déplacer un lien vers une URI transmet désormais le lien, comme
  Dolphin ; une destination sans liens symboliques peut produire une erreur KIO.
- `Location.uri` résout toujours les liens pour les propriétés natives et la
  navigation.
- Les assistants natifs doivent être recompilés et livrés pour que C1 soit
  corrigé.

## Validation manuelle restant à faire

Dans une session Plasma réelle, confirmations KDE actives, dans un dossier de
test : Suppr et Maj+Suppr sur « x␠ » et « x » ; F2 sur « x␠ » ; glisser un lien
vers un panneau affichant la Corbeille ; Suppr et Maj+Suppr dans un partage
sftp ou smb de test ; vérifier dans la Corbeille que « Mettre à la corbeille »
est grisé et que « Supprimer définitivement » reste disponible.
