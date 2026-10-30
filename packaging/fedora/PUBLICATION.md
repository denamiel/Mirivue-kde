# Publication Fedora / COPR de Mirivue KDE

## Références de version

Version visible : **1.0.0-beta.1**. Dans la recette actuelle de `main` :
`Version: 1.0.0` et `Release: 0.196.beta1.3%{?dist}`.
Les révisions précédentes `0.196.beta1.1` et `0.196.beta1.2` sont historiques.
La révision 3 ajoute les guides corrigés sous `/usr/share/doc/mirivue-kde/`
et permet leur distribution par une mise à jour DNF.
Lire [mirivue-kde.spec](mirivue-kde.spec) pour la valeur à construire.

Conserver un ordre RPM croissant pour les prochaines bêtas et révisions de
conditionnement. La version stable utilisera une Release adaptée à la série
stable ; vérifier son ordre avec RPM avant publication. Une correction de
documentation seule ne nécessite pas de changer la version de l'application.

## Branche de publication

Le dépôt possède une branche `main` de développement et une branche
`publication` pour le circuit COPR décrit ici. Elles peuvent pointer sur des
commits différents. La présence d'un correctif sur `main` ne prouve pas qu'il
est déjà distribué sur Fedora.

Paramètres du circuit à contrôler dans COPR :

- Source SCM : Git.
- URL : `https://github.com/denamiel/Mirivue-kde.git`.
- Committish : `publication`.
- Sous-dossier : vide.
- Recette : `packaging/fedora/mirivue-kde.spec`.
- Méthode : `make srpm`, avec `.copr/Makefile` à la racine.
- Reconstruction automatique et webhook : limités au circuit de publication
  choisi, pour ne pas publier chaque modification de développement.

Le webhook et son activation sont des réglages externes : ce document ne
constitue pas une vérification de leur état. Les contrôler dans COPR et GitHub ;
ne jamais enregistrer l'URL secrète du webhook dans Git ou dans une conversation.

## Publier après validation

1. Valider le commit candidat et vérifier la cohérence des versions, sources,
   licences et dépendances.
2. Avancer `publication` vers le commit validé selon la procédure de maintenance,
   sans écraser des changements de branche non examinés.
3. Vérifier que COPR construit ce commit ; si le webhook est actif, contrôler
   son résultat plutôt que supposer qu'un push a réussi à publier.
4. Attendre la réussite dans chaque environnement Fedora annoncé.
5. Contrôler l'installation ou la mise à jour du RPM et le lancement de Mirivue.

Une réussite des contrôles Arch ne remplace pas ces vérifications Fedora.
Les guides de la RC195 et leurs résultats restent historiques.

## Installation et mises à jour

```bash
sudo dnf copr enable pdenams/Mirivue-kde
sudo dnf install mirivue-kde
sudo dnf upgrade --refresh mirivue-kde
```

Le dépôt COPR est communautaire. Les distributions et architectures disponibles
sont celles des constructions réellement réussies sur sa page :
https://copr.fedorainfracloud.org/coprs/pdenams/Mirivue-kde/

Le [dépôt Pacman](https://github.com/denamiel/mirivue-arch) est indépendant :
il utilise les commits `main` validés, pas la branche COPR `publication`.

## Référence officielle

- https://docs.copr.fedorainfracloud.org/user_documentation.html#webhooks
