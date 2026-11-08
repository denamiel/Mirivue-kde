# Publication contrôlée de Mirivue KDE

**Principe :** valider le code et publier des paquets sont deux décisions
distinctes. Une fusion dans `main`, une CI verte, un tag ou un push ne publient
jamais rien. Chaque publication exige trois conditions réunies :

1. un lancement **manuel** du workflow sur `main` ;
2. la confirmation tapée `PUBLIER` ;
3. l’**approbation** du mainteneur dans un environnement GitHub protégé.

Un garde-fou refuse en outre de publier dans COPR une révision RPM inchangée,
pour ne jamais distribuer deux contenus différents sous le même numéro.

## Pourquoi

Le 8 novembre 2026, la fusion de la PR n° 5 dans `main` (commit `d4d5b95`) a
déclenché le job `publish` du workflow Fedora. Celui-ci a avancé la branche
`publication`, et COPR a construit puis publié la build `11285421`
(Fedora 44 et 45, 00:00–00:03 UTC). Ce paquet contient le code de la PR n° 5 mais
porte le **même numéro** que la build précédente (`1.0.0-0.200.beta5.3`) :
`dnf` ne le propose pas aux installations existantes. Le dépôt Pacman
(`denamiel/mirivue-arch`) publie lui aussi automatiquement, chaque heure, les
commits validés de `main` lorsque sa variable `PUBLISH_ENABLED` vaut `true`.

## Réglages GitHub à créer avant la première publication

Sans protection, GitHub crée un environnement inconnu **sans approbation** au
premier usage. Créer donc d’abord, dans *Settings → Environments* de chaque
dépôt, avec *Required reviewers* = le mainteneur et *Deployment branches* =
`main` seulement :

| Dépôt | Environnement | Protège |
|---|---|---|
| `denamiel/Mirivue-kde` | `publication-copr` | avance de la branche `publication` (COPR) |
| `denamiel/Mirivue-kde` | `publication-arch` | ajout des paquets Arch à une release |
| `denamiel/mirivue-arch` | `publication-pacman` | publication du dépôt Pacman signé |

En ligne de commande, pour un environnement :

```bash
id=$(gh api user --jq .id)
gh api -X PUT repos/denamiel/Mirivue-kde/environments/publication-copr --input - <<EOF
{"reviewers":[{"type":"User","id":$id}],
 "deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
EOF
gh api -X POST repos/denamiel/Mirivue-kde/environments/publication-copr/deployment-branch-policies -f name=main
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
   `publication` et que la révision RPM a changé, puis avance `publication`.
5. Contrôler ensuite la build COPR et son numéro, sans le supposer.

## Paquets Arch dans une release

La création d’une release reste un acte manuel. L’ajout des paquets Arch à la
release attend en plus l’approbation de `publication-arch`.

## Dépôt Pacman (`denamiel/mirivue-arch`) — proposition, non appliquée

Ce dépôt de distribution n’est pas modifié par ce travail.

**Mesure immédiate possible**, réversible, à décider par le mainteneur :

```bash
gh variable set PUBLISH_ENABLED --body false --repo denamiel/mirivue-arch
```

Les exécutions planifiées continuent alors de construire et valider, sans
publier.

**Modification proposée** de `.github/workflows/repository.yml`. Les exécutions
planifiées et les push ne font plus que construire ; la publication exige un
lancement manuel, la saisie `PUBLIER`, `PUBLISH_ENABLED=true` et l’approbation
de `publication-pacman` :

```diff
       force_rebuild:
         description: Reconstruire même sans nouvelle version (incrémente pkgrel)
         type: boolean
         default: false
+      publier:
+        description: Pour publier le dépôt signé, taper exactement PUBLIER
+        required: false
+        default: ''
@@
   publish:
     name: Publier le dépôt avec la clé du propriétaire
     needs: [plan, build, installation]
-    if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request' && vars.PUBLISH_ENABLED == 'true'
+    # Les exécutions planifiées et les push valident et construisent seulement.
+    # Publication : lancement manuel, confirmation tapée, environnement approuvé.
+    if: >-
+      github.ref == 'refs/heads/main'
+      && github.event_name == 'workflow_dispatch'
+      && inputs.publier == 'PUBLIER'
+      && vars.PUBLISH_ENABLED == 'true'
     runs-on: ubuntu-latest
+    environment: publication-pacman
     container: archlinux:base-devel
```

Publication ensuite :

```bash
gh workflow run repository.yml --repo denamiel/mirivue-arch --ref main -f publier=PUBLIER
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
