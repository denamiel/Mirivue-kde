# Correctifs RC181 — dossier de preuve

Référence : archive RC180 fournie, SHA-256
`78868e773334cd7c942ec0d407a5b7af79f13f3d4969b5a573af62639ff8f04d`,
Dolphin v26.08.2 et KStringHandler de KF6 v6.31.0. Les préférences existantes,
les outils médias et le partage volontaire de kservicemenurc restent conservés.
Ce document distingue les contrats ciblés réussis de l'acceptation globale.

## 1. Commandes d'un panneau fermé

- Fichiers : mirivue/panes.py, mirivue/app.py, mirivue/dolphin_view.py.
- Garde _closed dans pane_command et activate_pane ; arrêt du minuteur des
  colonnes ; rejet direct d'une relance de métadonnées ; contrôle isValid du
  QWidget avant révélation différée du chemin de secours.
- Tests : test_rc181_freeze (trois contrats de durée de vie),
  test_rc181_panes_gui (dix fermetures, panneaux scindés, vrais DeferredDelete,
  livraison volontairement tardive et relance de métadonnées).
- Rouge : rc180-contrats-rouge.log et rc180-panneaux-rouge.log.
- Vert ciblé : cibles-finales.log et rc181-panneaux.log.
- L’instabilité découverte pendant les répétitions provenait d’un autre défaut
  de durée de vie : le wrapper de la surface native de dessin restait déclaré
  valide après sa destruction C++. Le test direct échoue aussi sur RC180
  (rc180-canvas-rouge.log). Le signal destroyed invalide désormais ce wrapper,
  empêchant Shiboken de le réutiliser pour une nouvelle adresse de widget.
- Vert : rc181-canvas-et-panneaux-vert.log ; trente répétitions du scénario
  de dix fermetures, soit 300 cycles, réussissent (stress-onglets-corrige.log).
  Les essais intermédiaires en échec sont conservés et exclus de l’acceptation.

## 2. D-Bus

- Fichiers : window_instances.py, external_locations.py, app.py.
- Normalisation centralisée avant mise en file ; types, taille, nombre,
  URL invalide et JSON profond contrôlés ; detached_tab refusé par Dispatch.
- Échange asynchrone, budget monotone global de 1 500 ms ; conservation du
  reste non livré, sans réémission d'un envoi accepté ou incertain. Avant la
  première fenêtre seulement, une boucle Qt attend le même échange asynchrone.
- Tests : test_rc181_freeze, test_rc181_routing, test_window_instances_dbus.
- Rouge : rc180-contrats-rouge.log ; ancien routage de vingt pairs simulés :
  rc180-routage-bloquant.json (aucun battement Qt pendant l'appel).
- Vert : cibles-finales.log, routage-final-cible.log, dbus-reel.log.
  Ce dernier utilise un vrai bus jetable, pas le bus personnel de l'utilisateur.
- Bornes propres à Mirivue et traitement des réponses perdues : IPC-RC181.md.

## 3. Sessions au-delà de cent onglets

- Fichier : session_state.py.
- Suppression de la troncature à cent ; contrôle QSettings.status après sync ;
  signalement de l'échec d'enregistrement, sans empêcher de quitter la fenêtre.
- Tests : test_rc181_freeze ; 100 puis 101 onglets, titres/panneaux actifs/
  proportions différents ; deux cycles sauvegarder/restaurer, état complet comparé.
- Rouge explicite : rc180-session-101-rouge.log (100 != 101).
- Vert explicite : rc181-session-101-vert.log ; retour d'erreur QSettings couvert
  aussi dans le contrat principal. Aucun mécanisme d'autosauvegarde ajouté.

## 4. Titres automatiques

- Fichiers : panes.py, places.py, native/kio-places-widget.cpp.
- Esperluettes doublées puis KStringHandler::rsqueeze(..., 40), comme
  dolphintabwidget.cpp:557 ; KStringHandler v6.31.0 coupe la fin et utilise trois
  points ASCII. Les titres personnalisés restent exempts de rsqueeze.
  Le QString est placé directement dans QTabBar par le pont, sans conversion
  de sortie UTF-8 qui perdrait une demi-paire de substitution à la coupure.
- Test : test_rc181_freeze.test_titles_use_rsqueeze_ascii_dots ; 39/40/41/50,
  esperluette proche de la coupure, caractères hors plan de base, split et titre libre.
- Rouge : rc180-contrats-rouge.log (ancienne ellipse Unicode au milieu).
- Vert : contrats-finaux.log, dont la vérification native des quarante unités QString.

## 5. Cinq comparaisons de tri

- Fichiers : app.py, metadata.py, native/kio-list.cpp.
- Résolution : largeur puis hauteur ; piste : entier avant « / », inconnu = 0 ;
  auteur : texte brut ; texte équivalent vide en dernier en ordre croissant ;
  égalités : nom affiché, nom réel, URL. Le nom réel de KFileItem est transporté
  séparément du nom affiché, sans changement de la présentation des fichiers.
- Non modifié : Année/date correspond à la balise date générale de Mirivue,
  pas au rôle releaseYear de Dolphin (media.py:13, COLUMNS[22]). La convertir en entier perdrait de
  l'information. Les autres règles sont décrites dans PARITE-DOLPHIN.md.
- Tests : test_rc181_freeze, test_kio_visibility_identity ; cinq contrats
  indépendants rejouables avec verifier-cinq-tris.py.
- Rouge : rc180-cinq-tris-rouge.log (cinq échecs distincts).
- Vert : rc181-cinq-tris-vert.log (cinq réussites), cibles-finales.log.

## 6. Captures du navigateur et initialisation

- Fichiers : native/tests/navigator-check.cpp, tests/support/native_style_checks.py,
  tests/test_dolphin_parity_gui.py.
- Avant : vingt répétitions Union spontanées n'ont pas reproduit l'échec.
  En décalant volontairement la capture de 550 ms, le clignotement du curseur
  produit exactement une différence de 46 pixels, deux colonnes sur 23 lignes.
- Correction du test seulement : curseur non clignotant dans le programme
  de comparaison ; aucune couleur, bordure ni logique du produit changée.
  Les images actual/reference/diff restent enregistrées lors d'un échec.
- Après : vingt répétitions Union et vingt Breeze réussies, ainsi que le même
  décalage forcé de 550 ms ; résultats bruts navigateur-avant/apres.json,
  curseur.log et diagnostic-curseur/*.png.
- Le dépassement d'initialisation à huit secondes n'a pas été reproduit dans
  les vingt essais isolés RC180. Le délai de huit secondes n'est pas augmenté ;
  un diagnostic de threads et d'état des panneaux est conservé en cas d'échec.
  Cela ne prouve pas que toute cause possible de lenteur au démarrage est corrigée.

## 7. Licences et contenu du paquet

- Fichiers : session_state.py, window_instances.py, view_policy.py,
  external_locations.py, LICENSE, LICENCES-TIERS.md, PKGBUILD.template, Installer.sh.
- Les quatre modules Python sont du code original Mirivue sous MIT, comparé
  aux comportements de Dolphin ; aucun auteur KDE ne leur est attribué par
  simple ressemblance. Les sources adaptées de Dolphin gardent leurs en-têtes.
- Index des seize fichiers natifs MIT ; textes et fichiers de provenance installés
  sous /usr/share/licenses/mirivue-kde ; servicemenu.knsrc inclus dans le paquet.
- Tests : test_rc181_freeze et test_rc181_package ; la véritable fonction
  package() est exécutée dans une racine jetable, sans installation pacman.
- Rouge : rc180-paquet-rouge.log et rc180-contrats-rouge.log.
- Vert : rc181-paquet.log et cibles-finales.log.
- Contrôle de cohérence technique, pas certification juridique.

## 8. Libellés de services dans Configuration

- Fichier : native/context-menu-settings.cpp ; tests de fournisseurs et de page
  contextuelle mis à jour. Aucun identifiant technique ni suffixe de provenance
  ajouté au nom affiché, y compris pour les homonymes.
- Dolphin v26.08.2, contextmenusettingspage.cpp:289 et 304, affiche le nom du
  service. Son chemin source reste une info-bulle (:339–349), comme ici.
- Les identifiants demeurent internes pour enregistrer la bonne case ; deux
  services homonymes ne sont pas fusionnés. Les libellés génériques fournis
  par KDE ne sont pas reformulés arbitrairement.

## Lecture des preuves

Les journaux rouges utilisent le code RC180 intact avec les contrats nouveaux.
Une erreur d'import de l'ancienne API de routage n'est pas présentée comme une
mesure de performance : la mesure séparée de l'ancien appel est conservée.
Les contrats verts ciblés ne remplacent pas les trois suites complètes exigées.
Les résultats complets, y compris les essais intermédiaires invalides, figurent
avec leur code de sortie dans VALIDATION-RC181.md et le dossier validation/RC181.
