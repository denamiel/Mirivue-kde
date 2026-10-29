# Paquets CachyOS / Arch Linux et Fedora

Le code est commun aux deux distributions. La version de référence est
`mirivue/__init__.py` : actuellement **1.0.0-beta.1**.
Le paquet Arch porte `1.0.0beta1`. Le RPM encode cette même version
dans ses champs Version/Release pour conserver un ordre de mise à jour correct.

## Construction automatique CachyOS

Chaque modification de main et chaque pull request lance le workflow
**Paquet CachyOS et Arch Linux** dans un environnement Arch Linux.
Le paquet x86_64 contient les assistants C++ compilés et les sources Python.
La construction vérifie la syntaxe Python, le lanceur desktop et les dépendances
liées des assistants KIO principaux. Cela ne remplace pas un essai graphique sur CachyOS.

Pour récupérer une construction : ouvrir l'onglet Actions, la dernière exécution
réussie, puis télécharger l'artefact `mirivue-kde-arch-x86_64` et extraire le ZIP.
Les artefacts Actions ont une durée de conservation limitée.

À la publication d'une Release GitHub, le workflow reconstruit les sources de
cette publication et joint le paquet et son fichier SHA256SUMS à la Release.
Créer le tag sur le commit dont la version a été mise à jour et vérifiée.
Aucun secret personnel supplémentaire n'est nécessaire.

## Installation et mise à jour CachyOS

Fermer Mirivue, ouvrir un terminal dans le dossier du paquet extrait, puis :

```bash
sha256sum -c SHA256SUMS
sudo pacman -U ./mirivue-kde-*.pkg.tar.zst
```

Pacman installe les dépendances déclarées et gère le paquet.
Pour les versions suivantes, télécharger le nouveau paquet et répéter ces commandes.
Aucun dépôt Pacman ni publication AUR n'est configuré : `pacman -Syu` seul
ne téléchargera donc pas les nouvelles versions de Mirivue.

Si une ancienne installation manuelle dans le dossier personnel masque le
lanceur du paquet, la migration doit être vérifiée avant de supprimer cette installation.

## Construction locale

Sur un système CachyOS/Arch à jour :

```bash
sudo pacman -Syu --needed base-devel git python
git clone https://github.com/denamiel/Mirivue-kde.git
cd Mirivue-kde
bash Construire-paquet-CachyOS.sh
```

Exécuter le script sans sudo. makepkg demande sudo uniquement pour installer
les dépendances manquantes. Le dossier source peut porter n'importe quel nom.

## Publier une correction commune

1. Corriger et tester le code commun.
2. Incrémenter la version dans `mirivue/__init__.py` et `pyproject.toml`,
   puis les sources/metadonnées et Version/Release du conditionnement Fedora.
3. Envoyer le commit sur main ; vérifier la construction Arch et celle de COPR.
4. Publier une Release GitHub pour distribuer durablement le paquet Arch.

COPR conserve son conditionnement dans `packaging/fedora/` et sa recette
`.copr/Makefile`. Le workflow Arch ne modifie pas sa configuration.
