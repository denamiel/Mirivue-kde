# Publication contrôlée de Mirivue KDE

**Principe :** valider le code et publier des paquets sont deux décisions
distinctes. Une fusion dans `main`, une CI verte, un tag, une release GitHub ou
un push ne publient jamais rien. **Chaque** publication (COPR, paquets Arch
joints à une release, dépôt Pacman) exige trois conditions réunies :

1. un lancement **manuel** du workflow sur `main` ;
2. la confirmation tapée `PUBLIER` ;
3. l’**approbation** du mainteneur dans un environnement GitHub protégé.

COPR refuse en outre toute révision RPM **égale ou inférieure** à celle déjà
publiée (comparaison `Epoch:Version-Release` identique à `rpmvercmp`).
Les paquets Arch ne sont joints qu’à une release dont le tag désigne exactement
le commit construit, sans jamais remplacer un fichier déjà joint.
`tests/test_publication_controlee.py` vérifie ces règles à chaque CI.

## Pourquoi

Le 8 novembre 2026, la fusion de la PR n° 5 dans `main` (commit `d4d5b95`) a
déclenché le job `publish` du workflow Fedora. Celui-ci a avancé la branche
`publication`, et COPR a construit puis publié la build `11285421`
(Fedora 44 et 45, 00:00–00:03 UTC). Ce paquet contient le code de la PR n° 5 mais
porte le **même numéro** que la build précédente (`1.0.0-0.200.beta5.3`) :
`dnf` ne le propose pas aux installations existantes. Le dépôt Pacman
(`denamiel/mirivue-arch`) publie lui aussi automatiquement, chaque heure, les
commits validés de `main` lorsque sa variable `PUBLISH_ENABLED` vaut `true`.

## Environnements GitHub : à créer avant la fusion

Un environnement absent ne protège rien : GitHub le crée sans aucune règle au
premier usage. Les trois environnements doivent donc exister **avant** la
fusion des workflows qui les utilisent :

| Dépôt | Environnement | Protège |
|---|---|---|
| `denamiel/Mirivue-kde` | `publication-copr` | avance de la branche `publication` (COPR) |
| `denamiel/Mirivue-kde` | `publication-arch` | paquets Arch joints à une release |
| `denamiel/mirivue-arch` | `publication-pacman` | publication du dépôt Pacman signé |

Règles : approbation obligatoire du mainteneur, déploiement limité à `main`,
aucun délai. Tous les jobs de publication s’exécutent sur `main`
(`workflow_dispatch`), y compris les paquets Arch : la règle « `main` seulement »
convient donc aux trois.

**`Prevent self-review`** reste désactivé : avec un seul mainteneur, celui qui
lance la publication doit pouvoir l’approuver, sinon aucune publication n’est
possible. L’approbation reste une seconde action explicite, distincte du
lancement et de la saisie `PUBLIER`.

**Limite.** Ces protections empêchent toute publication automatique ou
accidentelle. Elles ne protègent pas contre une personne ou un outil disposant
du jeton GitHub du mainteneur, qui pourrait lancer et approuver lui-même.

```bash
packaging/environnements-publication.sh --verifier    # lecture seule
packaging/environnements-publication.sh --appliquer   # crée ou corrige les trois environnements
```

## Publier dans COPR

1. Vérifier que la révision RPM du commit de `main` a augmenté.
2. Lancer le workflow :

   ```bash
   gh workflow run fedora-package.yml --repo denamiel/Mirivue-kde --ref main -f publier_copr=PUBLIER
   ```

3. Après les contrôles RPM et Python, approuver le déploiement
   `publication-copr` sur la page de l’exécution.
4. Le job vérifie que le commit est toujours la tête de `main`, qu’il descend de
   `publication` et que sa révision RPM est strictement supérieure
   (`packaging/fedora/verifier-revision-publication.py`), puis avance `publication`.
5. Contrôler ensuite la build COPR et son numéro, sans le supposer.

## Paquets Arch joints à une release

Une release ou un tag ne déclenchent plus rien. Après avoir créé la release sur
le commit de `main` à distribuer :

```bash
gh workflow run arch-package.yml --repo denamiel/Mirivue-kde --ref main \
  -f publier_arch=PUBLIER -f tag=v1.0.0-beta.6
```

Le paquet est reconstruit sur ce commit ; après approbation de
`publication-arch`, le job vérifie que le tag désigne ce commit, puis joint les
fichiers sans remplacer ceux qui existent déjà.

## Dépôt Pacman (`denamiel/mirivue-arch`)

La modification correspondante est préparée sur la branche
`controle/publication-explicite` de ce dépôt (pull request distincte, non
fusionnée) : les exécutions planifiées et les push ne font plus que construire ;
la publication exige un lancement manuel, la saisie `PUBLIER`,
`PUBLISH_ENABLED=true` et l’approbation de `publication-pacman`.

Tant qu’elle n’est pas fusionnée, le dépôt publie encore chaque heure les commits
validés de `main` (`PUBLISH_ENABLED=true` constaté le 8 novembre 2026). Mesure
immédiate et réversible, à décider par le mainteneur :

```bash
gh variable set PUBLISH_ENABLED --body false --repo denamiel/mirivue-arch
```

## Vérifier ce qui est réellement publié

```bash
# COPR : dernière build réussie et son numéro
curl -s "https://copr.fedorainfracloud.org/api_3/package/?ownername=pdenams&projectname=Mirivue-kde&packagename=mirivue-kde&with_latest_succeeded_build=true" \
  | python3 -c "import json,sys; b=json.load(sys.stdin)['builds']['latest_succeeded']; print(b['id'], b['source_package']['version'])"
# Pacman : manifeste signé du dépôt
gh release download repository --repo denamiel/mirivue-arch --pattern manifest.json --output - \
  | python3 -c "import json,sys; [print(k, v['pkgver'], v['pkgrel'], v.get('source_sha','')[:12]) for k, v in json.load(sys.stdin)['packages'].items()]"
```
