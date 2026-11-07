# Validation manuelle des corrections C1/H1/H2 — Fedora 45, Plasma

Durée : environ 30 minutes. Ces essais vérifient dans une vraie session Plasma
ce que les tests automatiques ne peuvent pas voir : la souris, le
glisser-déposer, les dialogues KDE et l’aspect des menus.

## Règles de sécurité

- Travaillez **uniquement** dans le dossier d’essai `~/Mirivue-essais-C1H1H2`,
  créé automatiquement. N’ouvrez pas vos propres dossiers pendant les essais.
- Ne cliquez jamais sur « Vider la corbeille ». À la fin, supprimez les
  éléments d’essai un par un (étape 6).
- Aucun serveur n’est à démarrer : SFTP a été vérifié automatiquement sur un
  serveur privé limité à cet ordinateur.
- Le dépôt, la branche `main` et le Mirivue installé ne sont pas modifiés.

## 1. Lancer la version d’essai

1. Fermez toutes les fenêtres de Mirivue.
2. Ouvrez Konsole et copiez ces trois lignes :

   ```bash
   cd ~/Projets/Mirivue-kde
   git fetch origin
   bash <(git show origin/collaboration/c1-h1-h2-beta5:tests/manual/lancer-validation-c1-h1-h2.sh)
   ```

3. Si le script annonce des paquets manquants, répondez `o` : il les installe
   avec `sudo dnf install` et demande votre mot de passe. Répondez `N` pour
   arrêter sans rien installer.
4. Après quelques minutes de construction, Mirivue s’ouvre sur
   `~/Mirivue-essais-C1H1H2/local`. Cette liste y est aussi copiée sous le nom
   `LISTE-DES-ESSAIS.md`.
5. Activez la vue scindée avec **F3**.

Dans Mirivue, un espace à la fin d’un nom est invisible. Les deux fichiers
`photo` se distinguent par la colonne **Taille** : le vrai `photo` fait 6 octets
(contenu « AUTRE ») ; celui dont le nom finit par un espace est plus gros
(contenu « CIBLE… »). En cas de doute, la commande indiquée par le script
(`--verifier`) affiche les noms entre crochets, par exemple `[photo ]`.

## 2. Noms terminés par un espace (C1)

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 2.1 | Sélectionnez le **plus gros** des deux `photo`, puis **Suppr** | Il part à la Corbeille ; le `photo` de 6 octets reste | |
| 2.2 | **Ctrl+Z** | Le gros `photo` revient | |
| 2.3 | Sélectionnez `photo2`, puis **Maj+Suppr** | Le dialogue KDE demande confirmation ; après « Supprimer », seul `photo2` disparaît | |
| 2.4 | **F2** sur le gros `photo`, tapez `renomme`, Entrée | `renomme` a la grande taille ; le `photo` de 6 octets est toujours là | |
| 2.5 | Ouvrez le dossier `Dossier` qui contient `attendu.txt` (l’autre contient `intrus.txt`) | La vue montre `attendu.txt` ; le fil d’Ariane et l’onglet indiquent ce même dossier | |
| 2.6 | Clic droit sur chacun des deux `Dossier` → Ajouter aux emplacements | Deux favoris ; chacun ouvre le bon dossier (`attendu.txt` ou `intrus.txt`) | |
| 2.7 | Glissez `source.txt` vers l’autre panneau ouvert sur le `Dossier` de `attendu.txt` | `source.txt` arrive à côté de `attendu.txt` | |

## 3. Liens symboliques (H1)

Ouvrez la **Corbeille** dans le panneau de droite (panneau Emplacements →
Corbeille). Gardez `local` à gauche.

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 3.1 | Glissez `lien-fichier.txt` dans le panneau Corbeille | Seul le lien part ; `cible.txt` reste | |
| 3.2 | Glissez `lien-dossier` dans le panneau Corbeille | Seul le lien part ; `Photos` et ses images restent | |
| 3.3 | Glissez `lien-casse` dans le panneau Corbeille | Le lien part sans erreur | |
| 3.4 | Maintenez **Ctrl** et glissez `cible.txt` vers `Destination` (copie) | `Destination/cible.txt` apparaît ; l’original reste | |

## 4. Corbeille

Restez dans le panneau Corbeille.

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 4.1 | Sélectionnez un élément d’essai | « Mettre à la corbeille » est grisé (menu Fichier, barre d’outils) ; Suppr ne fait rien | |
| 4.2 | Clic droit sur l’élément | « Restaurer » et « Supprimer définitivement… » sont disponibles | |
| 4.3 | **Maj+Suppr**, puis **Annuler** | L’élément reste dans la Corbeille | |
| 4.4 | **Maj+Suppr**, puis **Supprimer** | L’élément disparaît | |
| 4.5 | Clic droit sur un autre élément d’essai → Restaurer | Il revient dans `local` | |

## 5. Fonctionnement habituel

| # | Action | Résultat attendu | OK ? |
|---|---|---|---|
| 5.1 | Copiez, déplacez puis renommez `cible.txt` dans `Destination` | Tout se passe normalement | |
| 5.2 | **Ctrl+Z** puis **Ctrl+Maj+Z** | Annulation puis rétablissement | |
| 5.3 | **Suppr** sur une image de `Photos` | Elle part à la Corbeille, comme d’habitude | |

## 6. Nettoyage

1. Fermez Mirivue.
2. Ouvrez la Corbeille (Dolphin ou Mirivue installé) et supprimez **un par
   un** les éléments d’essai : leur « emplacement d’origine » contient
   `Mirivue-essais-C1H1H2`.
3. Retirez les deux favoris ajoutés à l’étape 2.6 (clic droit → Supprimer
   l’entrée).
4. Dans Konsole :

   ```bash
   bash /var/tmp/mirivue-validation-$USER/source/tests/manual/lancer-validation-c1-h1-h2.sh --nettoyer
   ```

   Le script affiche le dossier d’essai, demande de taper `oui`, puis supprime
   ce dossier et la version d’essai, et rien d’autre.

## Compte rendu

Sur la pull request n° 5, indiquez les numéros réussis et ceux en échec. Pour
un échec, joignez une capture et, si possible, la sortie de la commande
`--verifier`.
