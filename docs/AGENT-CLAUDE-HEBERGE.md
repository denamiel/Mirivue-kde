# Claude Code heberge — premiere phase : essai manuel en lecture seule

Suivi : [PR #16](https://github.com/denamiel/Mirivue-kde/pull/16).

## Etat

Le workflow `.github/workflows/claude-heberge.yml` a ete **restreint** :
- seulement `workflow_dispatch`, aucun `schedule` et aucun evenement PR ;
- seulement sur la branche `main`, via condition `github.ref` ;
- `contents: read`, `pull-requests: read`, `issues: read`, `actions: read` ;
- transmission explicite du `github.token` limite, a la place du jeton
  d'installation de l'application Claude si celui-ci dispose de plus de droits ;
- pas de commande shell autorisee a Claude ; uniquement `Read`, `Glob` et `Grep` ;
- au plus cinq tours, duree d'execution maximale 15 minutes ;
- diagnostic limite a la lecture de `README.md` et de
  `docs/PUBLICATION-CONTROLEE.md` lorsqu'il existe ;
- pas de push, pas de modification de fichier, aucun acces aux secrets dans
  les sorties et aucun declenchement de publication.

**Ce workflow ne developpe PAS Mirivue de maniere autonome.** Il sert
uniquement a verifier que l'action Claude Code peut s'authentifier et
s'executer de facon controlee sur un runner GitHub.

## Activation de la premiere phase

L'application Claude sur GitHub et le secret `CLAUDE_CODE_OAUTH_TOKEN`
doivent etre configures exclusivement dans les parametres du depot.
Ne jamais copier un secret dans une issue, une PR, un log ou un chat.

1. La PR #16 passe une revue independante des changements, des droits
   effectifs et du cout/usage Anthropic. Verifier aussi la version de l'action
   et, si possible, l'epingler par SHA apres verification de la release.
2. Le proprietaire donne explicitement son accord pour integrer ce workflow
   non destructif dans `main`. Sans accord, la PR reste en brouillon.
3. Sur la branche par defaut, le proprietaire peut executer manuellement
   `Mirivue - Claude heberge (diagnostic manuel)` par
   **Actions > workflow > Run workflow**, branche `main`.
4. Examiner le premier run : authentification, logs sans secret, outils
   disponibles, temps de calcul, cout, erreurs et absence de changements.
   Un job rouge signifie **non valide**, pas une permission de supprimer
   des protections.

L'installation de l'application GitHub n'implique pas que le jeton OAuth
sera accepte ou que son abonnement couvre l'execution hebergee.

## Deuxieme phase (NON IMPLEMENTEE)

Un agent qui modifie des fichiers et fonctionne a horaire defini implique
des risques plus eleves : cout et usage Anthropic, droits GitHub, injection
de prompts dans le code ou les commentaires, branches cibles, collisions
avec les PR en cours. Son implementation devra etre proposee dans une
**nouvelle PR separee**, apres succes et revue de l'essai manuel.

Avant toute mise en service, il faudra verifier :
- un declenchement explicitement accepte et sa periodicite ;
- un perimetre de fichiers et branches limite avec controles techniques ;
- aucun secret de publication ni autorisation d'editer les protections ;
- les interactions avec les PR #13/#14 et `CLAUDE.md` (#15) ;
- une politique d'echec, de supervision, de cout, de desactivation ;
- des premieres operations d'ecriture et de CI sur branche non protegee
  et jetable, avec revue independante ;
- aucune fusion, publication ou changement de `main` autonome.

## Limites connues

Une fois le workflow manuel valide, Claude fonctionne sur l'infrastructure
GitHub **uniquement lorsqu'un workflow est declenche**. Il n'ecoute pas en
continu les commentaires. L'agent a cadence reguliere n'existe pas encore.

La surveillance ChatGPT est distincte et n'exige ni Claude Code local ni
la fusion de cette PR. Elle peut suivre les changements, mais ne remplace
pas un agent de developpement heberge.

Sources :
- https://github.com/anthropics/claude-code-action
- https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/security.md
