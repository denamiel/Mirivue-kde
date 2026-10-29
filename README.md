# Mirivue KDE

Gestionnaire de fichiers multimédia à deux panneaux pour KDE Plasma.
Version de développement : **1.0.0-rc195**.

## Installer sur Fedora 44 x86_64

Les RPM sont disponibles sur [COPR pdenams/Mirivue-kde](https://copr.fedorainfracloud.org/coprs/pdenams/Mirivue-kde/).

```bash
sudo dnf copr enable pdenams/Mirivue-kde
sudo dnf install mirivue-kde
```

Lancez **Mirivue KDE** depuis le menu des applications ou avec `mirivue-kde`.
Pour mettre à jour, utilisez Discover ou :

```bash
sudo dnf upgrade --refresh mirivue-kde
```

COPR est un dépôt communautaire distinct des dépôts officiels Fedora.

## Fonctions

- Navigation à deux panneaux et opérations natives KDE/KIO.
- Aperçus d'images, audio, vidéo et PDF.
- Informations et analyse multimédia.
- Recherche récursive et gestion d'archives.

La lecture des médias dépend aussi des codecs installés.

## Retours et problèmes

Ouvrez une [Issue](https://github.com/denamiel/Mirivue-kde/issues) en indiquant la version de Mirivue, Fedora/KDE, les étapes de reproduction et le résultat attendu. Retirez les données personnelles des captures et journaux.

## Sources et construction

Sources Python et C++ de la RC195 avec les notices de la révision RPM `0.195.rc195.3.fc44`. L'import initial ne contient pas l'historique des versions précédentes. Les tests sources sont conservés ; les résultats temporaires et captures de validation ne sont pas inclus. Les comptes rendus anciens restent des documents historiques.

Les outils Fedora sont décrits dans [packaging/fedora/README.md](packaging/fedora/README.md). GitHub conserve les sources et les signalements ; COPR construit et distribue les RPM. Aucun déclenchement automatique GitHub → COPR n'est configuré.

## Licences

La distribution combinée est sous **GPL-3.0-or-later**. Les parties originales identifiées sous MIT conservent cette permission. Les composants Dolphin conservent leurs auteurs et licences, notamment GPL-2.0-or-later et BSD-2-Clause. Les métadonnées AppStream sont sous CC0-1.0.

Voir [LICENSE](LICENSE), [LICENCES-TIERS.md](LICENCES-TIERS.md), les dossiers `LICENSES/` et les notices adjacentes. Les preuves KDE sont dans `packaging/preuves-kde/`.

Projet porté par Pascal Denamiel. Les auteurs tiers sont crédités dans leurs fichiers et notices.
