# Mirivue KDE

Gestionnaire de fichiers multimédia à deux panneaux pour KDE Plasma.
Version de développement : **1.0.0-beta.1** (préversion).

## Installer sur Fedora 44 x86_64

Les RPM sont disponibles sur [COPR pdenams/Mirivue-kde](https://copr.fedorainfracloud.org/coprs/pdenams/Mirivue-kde/).

```bash
sudo dnf copr enable pdenams/Mirivue-kde
sudo dnf install mirivue-kde
```

Lancez **Mirivue KDE** depuis le menu des applications ou avec `mirivue-kde`.
Pour mettre à jour, utilisez votre gestionnaire de mises à jour ou :

```bash
sudo dnf upgrade --refresh mirivue-kde
```

COPR est un dépôt communautaire distinct des dépôts officiels Fedora.
Les versions de Fedora et architectures réellement disponibles sont celles
des constructions réussies du projet COPR.

## Installer sur CachyOS / Arch Linux x86_64

Le [dépôt Pacman signé Mirivue](https://github.com/denamiel/mirivue-arch)
distribue les éditions KDE et GNOME dans deux paquets indépendants.

Suivez une seule fois son [guide d'installation](https://github.com/denamiel/mirivue-arch#installation-sur-arch--cachyos-x86_64)
pour vérifier la clé publique et ajouter le dépôt à `/etc/pacman.conf`.
Puis :

```bash
sudo pacman -Syu mirivue-kde
```

Les mises à jour suivantes sont incluses dans `sudo pacman -Syu`.
Aucune connexion GitHub ni clé privée n'est nécessaire sur l'ordinateur client.
L'installation depuis un artefact Actions avec `pacman -U` reste possible,
mais ne configure pas à elle seule les mises à jour.
Voir [le guide de conditionnement](packaging/README.md).

## Fonctions

- Navigation à deux panneaux et opérations natives KDE/KIO.
- Aperçus d'images, audio, vidéo et PDF.
- Informations et analyse multimédia.
- Recherche récursive et gestion d'archives.

La lecture des médias dépend aussi des codecs installés.

## Retours et problèmes

Ouvrez une [Issue](https://github.com/denamiel/Mirivue-kde/issues) en indiquant
la version de Mirivue, le système, le bureau, les étapes de reproduction et le
résultat attendu. Retirez les données personnelles des captures et journaux.

## Sources, validation et publication

Le dépôt contient les sources Python et C++, les tests et le conditionnement.
L'import initial provenait de la RC195 ; ce repère est historique et ne désigne
pas la version actuelle. Les anciens rapports par RC conservent leurs résultats
et leurs limites ; ils ne constituent pas les instructions d'installation actuelles.

Les [outils Fedora](packaging/fedora/README.md) et le
[circuit de publication COPR](packaging/fedora/PUBLICATION.md) décrivent le rôle
de la branche `publication`. Le suivi Pacman utilise, lui, les commits de `main`
ayant réussi le workflow Arch requis ; il ne dépend pas de cette branche COPR.
Un tag ou une modification locale ne met pas directement à jour les ordinateurs.

Les constructions Arch et les essais hors écran ne remplacent pas une validation
dans une session Plasma réelle. Les résultats d'une ancienne RC ne sont pas
présentés comme les résultats de la bêta actuelle.

## Licences

La distribution combinée est sous **GPL-3.0-or-later**. Les parties originales
identifiées sous MIT conservent cette permission. Les composants Dolphin
conservent leurs auteurs et licences, notamment GPL-2.0-or-later et BSD-2-Clause.
Les métadonnées AppStream sont sous CC0-1.0.

Voir [LICENSE](LICENSE), [LICENCES-TIERS.md](LICENCES-TIERS.md), les dossiers
`LICENSES/` et les notices adjacentes. Les preuves KDE sont dans
`packaging/preuves-kde/`.

Projet porté par Pascal Denamiel. Les auteurs tiers sont crédités dans leurs
fichiers et notices.
