# Mirivue TestLab Wayland — KWin virtuel

> État : **étude de faisabilité et première tranche** (PR distincte, empilée sur la PR n° 9).
> Un **KWin Wayland virtuel n'est pas une session Plasma complète**. Il complète le
> TestLab X11/Xvfb, il ne valide pas un bureau Plasma réel.

## Faisabilité vérifiée sous Fedora 45 (8 novembre 2026)

Paquets : `kwin` 6.8.2, `qt6-qtwayland` 6.11.2, `wl-clipboard` 2.3.0, `dbus-tools`, `systemd`
(pour `busctl`), et le RPM Mirivue testé. Aucun Xwayland ni xdotool n'est utilisé.

### Interfaces réellement disponibles dans `kwin_wayland --virtual`

| Besoin | Mécanisme retenu | Résultat |
|---|---|---|
| Composition sans GPU physique | Backend virtuel avec un nœud de rendu DRM | ✅ si `/dev/dri/renderD*` existe (voir ci-dessous) |
| Application en Wayland natif | `QT_QPA_PLATFORM=wayland`, KWin **sans** `--xwayland`, aucun `DISPLAY` | ✅ greffon `libqwayland` chargé, aucun greffon `xcb` |
| Clavier et pointeur | Protocole `org_kde_kwin_fake_input` v6, client Python pur `tests/testlab/wayland.py` | ✅ raccourcis, saisie, mouvements absolus, boutons |
| Fenêtres, focus, activation | Scripts KWin chargés par D-Bus (`workspace.windowList()`, `workspace.activeWindow`) | ✅ titre, PID, état actif, géométrie, boîtes de dialogue |
| Retour des scripts | `callDBus` vers un nom fictif, observé par `dbus-monitor` | ✅ JSON par exécution, numéroté |
| Presse-papiers | `wl-paste` via `ext_data_control_manager_v1` | ✅ |
| Captures | `org.kde.KWin.ScreenShot2.CaptureWorkspace` via `busctl` (passage de descripteur), conversion PNG en Python | ✅ RGBX8888 1280×800 |
| Glisser-déposer | Pointeur `fake_input` : pression, déplacement par étapes, relâchement, transmis par KWin (`wl_data_device`) | ✅ menu de dépôt Mirivue, « Déplacer ici » exécuté par KIO |
| `xdg_activation_v1` | Demandé par Qt à l'ouverture d'une fenêtre (Ctrl+N) | ✅ la nouvelle fenêtre obtient l'activation |
| Saisie `virtual-keyboard` (wtype) | — | ❌ protocole absent de KWin |
| `ydotool` | `/dev/uinput` | ❌ inexistant en conteneur et non souhaitable |
| EIS / libei (`org.kde.KWin.EIS.RemoteDesktop`) | Présent | Non utilisé : aucun client Python empaqueté ; `fake_input` suffit |

`KWIN_WAYLAND_NO_PERMISSION_CHECKS=1` ouvre les interfaces restreintes (`fake_input`,
ScreenShot2, scripts) **uniquement pour ce KWin jetable**.

### Deux obstacles trouvés et contournés

1. **Capacité de fichier.** `/usr/bin/kwin_wayland` porte `cap_sys_nice=ep` : un conteneur
   refuse de l'exécuter (« Operation not permitted »). Le harness lance une copie privée,
   qui a perdu cette capacité ; la priorité temps réel n'est pas nécessaire aux tests.
2. **Plantage de KWin sans nœud de rendu.**
   - En KWin 6.8, le backend virtuel ne propose plus QPainter (« Configured compositor not
     supported by Platform »). Sans `/dev/dri/renderD*`, il démarre **sans composition**.
   - KWin plante alors (SIGSEGV) dès qu'un client demande un jeton `xdg_activation`. Pile :
     `XdgActivationV1Integration::requestToken` → `EffectsHandler::startupAdded`, avec un
     `EffectsHandler` absent.
   - Mirivue le déclenche au démarrage, et toute application Qt qui active une fenêtre le
     déclencherait aussi.
   - Le harness refuse donc de démarrer sans nœud de rendu (code 2).
   - Ce défaut de KWin pourrait être signalé en amont.

### Nœud de rendu en CI

Les runners GitHub n'ont pas de GPU. Le job `testlab-wayland` charge le module noyau
`vgem` sur le runner (`sudo modprobe vgem`), qui crée un nœud de rendu virtuel sans
matériel, puis le transmet au conteneur Fedora (`--device /dev/dri`). Le rendu est
alors logiciel (Mesa).

**Ce point est validé par l'exécution CI de la PR**. S'il échouait, le job resterait
informatif, et la seconde étape (VM) deviendrait nécessaire pour Wayland.

## Scénarios

| Scénario | Vérifie |
|---|---|
| `wayland-essentiel` | Démarrage natif sans Xwayland ; focus donné par KWin à « Premiers pas » puis **rendu seul** à la fenêtre principale ; Ctrl+L, Échap, Ctrl+A et Ctrl+C avec contenu exact via wl-paste ; Ctrl+Maj+N avec dialogue activé et dossier créé par KIO ; recherche clavier ; Ctrl+N : la nouvelle fenêtre obtient l'activation ; le clavier suit l'activation (chaque fenêtre copie sa propre sélection) ; Ctrl+Q avec code 0 |
| `wayland-glisser-deposer` | Glisser `note.txt` sur `Existant` au pointeur ; menu de dépôt ; « Déplacer ici » ; fichier déplacé par KIO |
| `wayland-controle-echec` | Contrôle négatif : code 1, capture `echec.png`, liste des fenêtres KWin et journal `kwin.log` |

Contrairement à Xvfb, KWin gère réellement le focus. Les scénarios **vérifient** donc son
retour automatique au lieu de le forcer.

Les positions des icônes du glisser-déposer sont fixes (fenêtre en 0,0, 1280×800,
décorations KWin). Un changement de disposition fait échouer le scénario avec une capture :
il ne peut pas réussir par erreur.

## Rapports

Le format est identique à celui du TestLab X11 : `rapport.json`, `junit.xml`, `captures/`
et `journaux/` (`kwin.log`, `dbus.log`, journaux Mirivue, harness). On y trouve en outre :
- `environnement.moteur = wayland-kwin-virtuel` ;
- les greffons Qt réellement chargés, dans les détails de la première étape ;
- la couverture déclarée :

| Domaine | Couverture déclarée |
|---|---|
| Wayland | `couvert` |
| KWin | `couvert (backend virtuel, sans Xwayland)` |
| Plasma, X11 | `non couvert` |
| Glisser-déposer | `couvert` seulement après un scénario de glisser-déposer réussi |

Le confinement est le même que pour le TestLab X11 :
- **KWin, le bus, `dbus-monitor` et `busctl`** tournent sous le compte dédié (`uid`) ;
- **l'application** tourne sous ce même compte, ou dans bubblewrap (`bwrap`) ;
- **le nettoyage** est vérifié et le rapport est garanti.

Les tests avec l'application réelle ne s'exécutent qu'avec `MIRIVUE_TESTLAB_RUN_REAL=1` ou
`MIRIVUE_TESTLAB_REQUIRE_WAYLAND=1` (CI), jamais par accident dans une session personnelle.

## Ce qui exige une véritable session Plasma (seconde étape)

Ces fonctions ne peuvent pas être validées par un KWin seul :

- **plasmashell :** tableau de bord, gestionnaire de tâches, notifications (KNotification),
  zone de notification, menu global ;
- **portails :** `xdg-desktop-portal-kde` (sélecteurs de fichiers natifs, ouverture avec) ;
- **services de session :** `kded6` et ses modules (montages Solid, statut réseau),
  `kactivitymanagerd`, `ksmserver` (restauration de session), `kglobalacceld` complet,
  thèmes et configuration utilisateur Plasma ;
- **intégration du bureau :** glisser-déposer **vers d'autres applications** ou le bureau,
  et activation depuis une autre application avec un jeton transmis ;
- **matériel :** GPU réel, mise à l'échelle fractionnaire sur écrans réels, multi-écran
  physique, périphériques amovibles, NTFS, MTP.

### Proposition : VM Fedora KDE 45 éphémère

- **Image :** Fedora KDE 45 officielle, plus le RPM testé, préparée par un script
  reproductible (cloud-init ou kickstart), sans compte personnel et sans secret.
- **Exécution :**
  - une VM QEMU/KVM jetable par exécution, démarrée en session Plasma Wayland avec
    connexion automatique sur un compte de test ;
  - le même harness, avec `fake_input`, les scripts KWin et ScreenShot2, auxquels s'ajoute
    AT-SPI pour l'introspection des widgets ;
  - les rapports sont copiés hors de la VM, puis la VM est détruite.
- **Hôte :**
  - de préférence, un runner GitHub hébergé avec KVM (les runners Linux standard exposent
    `/dev/kvm`) ;
  - à défaut, une machine dédiée et isolée, éphémère, qui n'exécute pas les PR de forks ;
  - **jamais** le poste personnel du propriétaire.
- **Coût :** de l'ordre de 10 à 15 minutes par exécution (démarrage de la VM compris), donc
  à lancer sur les PR qui touchent l'intégration au bureau, ou chaque nuit.

## Intégration progressive

1. **Aujourd'hui :** le job `testlab-wayland` tourne sur chaque PR, mais il est
   **informatif**. Il ne bloque ni la publication COPR ni la fusion :
   `packaging/protection-main.py` le classe dans `INFORMATIVE_CHECKS`.
2. **Après plusieurs exécutions CI stables :**
   - le déplacer dans `REQUIRED_CHECKS` ;
   - l'ajouter à `publish.needs` ;
   - ces deux modifications sont soumises à revue.
3. **Ensuite :** la VM Plasma, d'abord la nuit, puis sur les PR concernées.
