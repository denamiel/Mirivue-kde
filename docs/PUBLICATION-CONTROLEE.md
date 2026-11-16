# Publication automatique des versions validées

La fusion d’une PR qui augmente explicitement une version constitue la décision
de publication. Les PR, les tags seuls et les modifications sans hausse de
version ne publient aucun paquet. Aucun jeton personnel supplémentaire n’est
nécessaire : les workflows utilisent leur `GITHUB_TOKEN` limité au dépôt.

## KDE : du code fusionné aux paquets

1. `main` reste protégée : PR obligatoire, contrôles requis, interdiction de
   suppression et de réécriture, aucun contournement.
2. Le workflow Fedora vérifie les RPM stables, Python, X11, Wayland, Plasma,
   les médias, les systèmes de fichiers et la suite intégrale. Tous ces jobs
   bloquent la publication. Rawhide reste expérimental, sans paquet annoncé.
3. Une révision RPM égale ne publie rien ; une révision inférieure est refusée.
   Une révision supérieure peut avancer `publication`, uniquement si le commit
   testé est toujours la tête de `main` et descend de la publication précédente.
4. COPR construit automatiquement cette branche. Le job conserve son verrou
   jusqu’à la réussite Fedora 44/45 et vérifie le commit et le contenu de
   l’archive Git effectivement livrée dans le SRPM public.
5. `release-automatique.yml` attend la réussite des workflows Fedora et Arch
   du même commit de `main`. Il réutilise l’artefact Arch de cette exécution,
   contrôle SHA256, crée le tag exact puis la release. Une release publique,
   un tag différent et un fichier existant de contenu différent sont refusés.

Les lancements manuels servent à reprendre une exécution ; ils n’autorisent
jamais à contourner le contrôle des sources, des versions ou des tests.

## Dépôt Pacman signé

Le dépôt `denamiel/mirivue-arch` examine chaque heure les nouvelles versions
validées. Il peut aussi être lancé manuellement en sélectionnant `edition=kde`
ou `edition=gnome`. KDE exige les workflows Fedora **et** Arch réussis du commit
sélectionné ; GNOME exige son workflow de qualification.

Seules les éditions dont la version augmente sont reconstruites. Une édition
inchangée ou dont les tests échouent conserve son paquet déjà publié : ses
signatures et ses empreintes sont vérifiées, et ses tests graphiques ne bloquent
pas une mise à jour de l’autre édition. La base Pacman reste complète et signée.
Les tests d’installation et de corruption portent sur le catalogue préparé et
sur les éditions modifiées.

La publication refuse une branche de publication non protégée, une source ou
un manifeste devenus obsolètes, une rotation implicite de clé et tout retour à
une version inférieure. `PUBLISH_ENABLED=false` reste l’arrêt d’urgence. Les PR
et modifications du dépôt de publication sans nouvelle version amont utilisent
un candidat de test jetable, qui ne peut jamais être publié.

## Protections GitHub attendues

| Dépôt | Environnement | Restriction |
|---|---|---|
| Mirivue-kde | publication-copr | uniquement la branche main |
| Mirivue-kde | publication-arch | uniquement la branche main |
| mirivue-arch | publication-pacman | uniquement la branche main |

Ces environnements conservent leur restriction de branche et n’exigent plus
l’approbation manuelle supplémentaire du mainteneur. Les permissions d’écriture
et la clé privée de signature sont réservées aux jobs de publication. Stocker
les clés de signature dans l’environnement `publication-pacman` est recommandé.

`mirivue-arch/main` doit exiger une PR et le contrôle **Validation du dépôt signé**,
sans réécriture, suppression ou contournement. Le modèle de ruleset est dans
`packaging/protection-mirivue-arch.json`. Les protections existantes de
`Mirivue-kde/main` restent inchangées.

```bash
python3 packaging/environnements-publication.py --verifier
# Application uniquement dans le cadre de la mise en place autorisée :
python3 packaging/environnements-publication.py --appliquer
```

L’administration des environnements et rulesets peut nécessiter une intervention
sur GitHub si l’intégration ne possède pas les droits Administration. Cela se
fait une fois lors de la configuration, sans secret personnel pour les sorties
suivantes. La suppression des trois approbations finales est une modification
délibérée : la fusion d’une nouvelle version est désormais le feu vert.

## Origine du changement

Le 8 novembre 2026, une publication automatique avait réutilisé le numéro
`1.0.0-0.200.beta5.3` : DNF ne proposait pas le correctif. Le circuit manuel
avait alors ajouté trois approbations distinctes. Le circuit actuel prévient
ce défaut par l’ordre strict des versions et la validation du commit, tout en
retrouvant la publication automatique demandée par le mainteneur.
