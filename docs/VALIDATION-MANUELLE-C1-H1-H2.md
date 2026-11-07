# Validation manuelle C1/H1/H2 dans Plasma — Fedora 45

Ces essais complètent les tests automatisés, exécutés hors écran. Ils vérifient
dans une vraie session Plasma les dialogues KDE, la souris, le glisser-déposer
et l’aspect des menus. Comptez environ 30 minutes.

**Sécurité.** Tous les fichiers manipulés sont créés par le script d’essai
dans `~/Mirivue-essais-C1H1H2`. N’utilisez aucun autre dossier. Ne videz pas
toute la Corbeille à la fin : supprimez seulement les éléments d’essai.

## 0. Préparer la version à tester (sans toucher au paquet installé)

1. Quitter toutes les fenêtres Mirivue (une instance déjà ouverte recevrait
   les demandes à la place de la version d’essai).
2. Dans un terminal :

   ```bash
   sudo dnf builddep ~/Projets/Mirivue-kde/packaging/fedora/mirivue-kde.spec
   git clone --branch collaboration/c1-h1-h2-beta5 \
       https://github.com/denamiel/Mirivue-kde.git /tmp/mirivue-essai
   cd /tmp/mirivue-essai
   cmake -S native -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
   cmake --build build
   mkdir tools
   find build -maxdepth 1 -type f \( -name 'mirivue-*' -o -name '*.so' \) -exec cp {} tools/ \;
   ls tools
   ```

3. Créer les fichiers d’essai, puis lancer la version d’essai :

   ```bash
   bash tests/manual/preparer-essais-c1-h1-h2.sh
   python3 -m mirivue ~/Mirivue-essais-C1H1H2/local
   ```

   À tout moment, `bash tests/manual/preparer-essais-c1-h1-h2.sh --verifier`
   affiche l’état réel des fichiers. Les noms y sont entre crochets pour
   rendre les espaces finaux visibles.

4. Dans Mirivue, ouvrir la vue scindée (F3). Les confirmations KDE sont
   partagées avec Dolphin (fichier `kiorc`) : dans Dolphin, Configurer Dolphin
   → Confirmations, laisser « Supprimer » cochée. La case « Mettre à la
   corbeille » sert à l’essai 3.6.

## 1. Noms terminés par un espace (C1)

Le dossier contient `photo` (« AUTRE ») et `photo ` (« CIBLE »), avec un
espace final. Repérez-les avec `--verifier`.

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 1.1 | Sélectionner `photo ` puis Suppr | `photo ` va à la Corbeille ; `photo` reste. Dans la Corbeille, l’élément s’appelle `photo ` | |
| 1.2 | Maj+Suppr sur `photo2 ` | Le dialogue KDE nomme `photo2 ` ; après confirmation seul `photo2 ` disparaît | |
| 1.3 | Ctrl+Z après 1.1 | `photo ` revient, avec son espace final | |
| 1.4 | F2 sur `photo `, renommer en `renomme` | `renomme` contient « CIBLE » ; `photo` contient toujours « AUTRE » | |
| 1.5 | Ouvrir `Dossier ` | La vue montre `attendu.txt` (pas `intrus.txt`) ; le fil d’Ariane et l’onglet affichent `Dossier ` | |
| 1.6 | Clic droit sur `Dossier` → Ajouter aux emplacements, puis la même chose sur `Dossier ` | Deux favoris distincts ; celui de `Dossier ` ouvre le dossier contenant `attendu.txt` | |
| 1.7 | Copier `source.txt` dans `Dossier ` (glisser vers l’autre panneau ouvert sur `Dossier `) | `source.txt` arrive dans `Dossier `, pas dans `Dossier` | |

## 2. Liens symboliques (H1)

Ouvrir la Corbeille dans le panneau de droite (Emplacements → Corbeille) et
`~/Mirivue-essais-C1H1H2/local` à gauche.

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 2.1 | Glisser `lien-fichier.txt` sur le panneau Corbeille | Seul le lien va à la Corbeille ; `cible.txt` reste | |
| 2.2 | Glisser `lien-dossier` sur le panneau Corbeille | Seul le lien part ; `Photos` et ses images restent | |
| 2.3 | Glisser `lien-casse` sur le panneau Corbeille | Le lien cassé est mis à la Corbeille, sans erreur | |
| 2.4 | Ctrl+glisser `lien-fichier.txt` vers `Destination` | `Destination/lien-fichier.txt` est un lien ; `cible.txt` est inchangée | |

## 3. Corbeille et confirmations

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 3.1 | Dans la Corbeille, sélectionner un élément d’essai | « Mettre à la corbeille » est grisé (menu Fichier, barre d’outils) avec une explication ; Suppr ne fait rien | |
| 3.2 | Clic droit sur l’élément | « Restaurer » et « Supprimer définitivement… » sont actifs | |
| 3.3 | Maj+Suppr, puis Annuler dans le dialogue KDE | L’élément reste dans la Corbeille | |
| 3.4 | Maj+Suppr, puis confirmer | L’élément disparaît définitivement | |
| 3.5 | Restaurer un autre élément d’essai | Il revient à son emplacement d’origine | |
| 3.6 | Dans Dolphin, cocher la confirmation « Mettre à la corbeille » ; dans Mirivue, Suppr sur `source.txt` puis Annuler | `source.txt` reste en place (remettre ensuite le réglage d’origine) | |

## 4. Emplacement distant SFTP (facultatif)

Cette étape démarre temporairement le serveur SSH de Fedora, qui n’accepte
que les connexions de ce poste si le pare-feu est actif. KIO demandera
d’accepter l’empreinte de `localhost` ; elle sera ajoutée à `~/.ssh/known_hosts`.

```bash
sudo systemctl start sshd
```

Dans la barre d’adresse de Mirivue :
`sftp://VOTRE_IDENTIFIANT@localhost/home/VOTRE_IDENTIFIANT/Mirivue-essais-C1H1H2/distant/`

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 4.1 | Sélectionner `distant.txt` | « Mettre à la corbeille » est grisé avec une explication ; le menu contextuel ne propose que « Supprimer définitivement… » | |
| 4.2 | Suppr | Rien n’est supprimé ; un message invite à utiliser Maj+Suppr | |
| 4.3 | Maj+Suppr, puis Annuler | `distant.txt` reste | |
| 4.4 | Maj+Suppr sur `photo `, puis confirmer | Seul `photo ` disparaît ; `photo` reste | |
| 4.5 | Maj+Suppr sur `lien.txt`, puis confirmer | Le lien disparaît, `cible.txt` reste | |

Arrêter ensuite le serveur :

```bash
sudo systemctl stop sshd
```

Un partage SMB (NAS) peut être vérifié de la même façon avec un dossier de test
créé sur ce partage. Le comportement attendu est identique.

## 5. Non-régression rapide

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 5.1 | Copier, déplacer et renommer `cible.txt` dans `Destination` | Opérations normales, sans message d’erreur | |
| 5.2 | Ctrl+Z puis Ctrl+Maj+Z | Annulation et rétablissement corrects | |
| 5.3 | Supprimer une image de `Photos` avec Suppr | Elle va à la Corbeille comme avant | |

## 6. Nettoyage

1. Dans la Corbeille, supprimer définitivement **un par un** les éléments
   d’essai (leur emplacement d’origine est sous `Mirivue-essais-C1H1H2`).
2. Supprimer le dossier d’essai :

   ```bash
   bash /tmp/mirivue-essai/tests/manual/preparer-essais-c1-h1-h2.sh --nettoyer
   rm -rf /tmp/mirivue-essai
   ```

3. Si un favori d’essai a été ajouté (étape 1.6), le retirer du panneau
   Emplacements (clic droit → Supprimer l’entrée).

## Compte rendu

Reportez les numéros en échec, avec une capture et la sortie de
`--verifier`, dans la pull request n° 5.
