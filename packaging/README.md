# Paquets CachyOS / Arch Linux et Fedora

Version de référence : `mirivue/__init__.py`, actuellement **1.0.0-beta.1**.
La version Python est `1.0.0b1`, la version Arch `1.0.0beta1`.
Pour Fedora, lire les champs Version/Release dans
[fedora/mirivue-kde.spec](fedora/mirivue-kde.spec) ; ils ne se déduisent pas
directement du nom visible de la bêta.

## Dépôt Pacman signé — installation recommandée

Le [dépôt mirivue-arch](https://github.com/denamiel/mirivue-arch) est publié.
Suivre son [guide d'installation](https://github.com/denamiel/mirivue-arch#installation-sur-arch--cachyos-x86_64)
pour vérifier l'empreinte de la clé publique et ajouter sa section à Pacman.

```bash
sudo pacman -Syu mirivue-kde
```

Après cette configuration unique, `sudo pacman -Syu` met aussi à jour Mirivue.
Le dépôt fournit des préversions pour Arch/CachyOS x86_64, pas des RPM Fedora.
Il ne nécessite pas de compte AUR, de compte GitHub ou de clé privée côté client.

Le workflow central examine les deux projets chaque heure. Il ne sélectionne
que le commit courant de `main` ayant réussi son workflow requis, puis reconstruit
les paquets avec les recettes amont. Il vérifie leur installation simultanée et
leur lancement hors écran avant signature et publication. Un échec bloque cette
publication. La clé de production est réservée au job de publication.
Les archives sources correspondant aux paquets sont conservées.

Une nouvelle version repart à `pkgrel=1` ; une reconstruction d'une même version
augmente `pkgrel`. Une correction documentaire peut donc produire une nouvelle
révision de paquet sans changer le numéro de version de l'application.
Les mises à jour déjà installées ne s'appliquent pas sans lancer le gestionnaire
de mises à jour du système.

## Artefacts GitHub et installation manuelle

Le workflow [Paquet CachyOS et Arch Linux](../.github/workflows/arch-package.yml)
construit sur les modifications de `main`, les pull requests, les lancements
manuels et les publications GitHub. Il vérifie notamment la syntaxe Python,
le lanceur desktop et les dépendances liées des assistants KIO principaux.

L'artefact `mirivue-kde-arch-x86_64` contient les paquets et `SHA256SUMS`.
Sa durée de conservation est limitée. Sur l'événement de publication d'une
Release, le workflow joint aussi ces fichiers à cette Release.

Après extraction, fermer Mirivue, vérifier `sha256sum -c SHA256SUMS`, puis
installer le paquet principal voulu avec `sudo pacman -U ./NOM_EXACT_DU_PAQUET`.
Une construction peut fournir aussi un paquet de symboles de débogage ; ce n'est
pas une seconde édition de Mirivue. Le contrôle SHA-256 vérifie l'intégrité des
fichiers téléchargés, sans remplacer la confiance apportée par une signature.

Cette méthode manuelle ne configure pas le dépôt Pacman. L'AUR est un circuit
distinct : aucune soumission à l'AUR n'est effectuée par ces workflows.

## Construction locale

Sur un système CachyOS/Arch à jour :

```bash
sudo pacman -Syu --needed base-devel git python
git clone https://github.com/denamiel/Mirivue-kde.git
cd Mirivue-kde
bash Construire-paquet-CachyOS.sh
```

Exécuter le script sans sudo. Il emploie `makepkg` et peut demander les droits
pour installer les dépendances. Fermer Mirivue avant l'installation du paquet.
Le dossier source peut porter n'importe quel nom. Si un ancien lanceur personnel
masque celui du paquet, vérifier sa provenance avant toute suppression.
Ne pas supprimer les réglages pour résoudre un conflit de lanceurs.

## Publier une correction

1. Corriger et tester le code sur une branche de travail.
2. Pour une version applicative, mettre à jour les versions et le conditionnement
   de manière cohérente ; compléter `CHANGELOG.md`. Pour une correction de
   documentation seule, conserver la version de l'application.
3. Intégrer à `main` et attendre le workflow Arch requis. Le dépôt Pacman central
   prend ensuite en charge les nouveaux commits validés ; une Release GitHub
   propre à l'application n'est pas nécessaire à ce circuit.
4. Pour Fedora, appliquer séparément le
   [circuit COPR](fedora/PUBLICATION.md) et vérifier la construction concernée.

Une réussite Arch ne déclenche ni ne valide, à elle seule, une construction COPR.
La configuration et les droits des webhooks sont extérieurs aux fichiers Git.
