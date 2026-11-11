# Agent Claude Code heberge — preparation (non active)

Cette PR introduit un **prototype opt-in** reposant sur
[Claude Code GitHub Action](https://github.com/anthropics/claude-code-action).
Son objectif est de permettre a Claude de traiter les corrections du chantier
TestLab depuis un runner GitHub **sans garder Konsole ouverte**.

## Etat initial

**NON ACTIF :** ce workflow est seulement propose sur une branche brouillon.
Un workflow planifie ne s'execute sur GitHub qu'apres integration dans la
branche par defaut. De plus, le job principal requiert
`MIRIVUE_AGENT_ENABLED=true` ; tant que cette variable n'existe pas, il
est ignore, meme en declenchement manuel.

Le workflow ne vise **que** la PR brouillon #14, si elle est toujours ouverte
sur la branche prevue et empilee sur #13. Il ne fusionne et ne publie rien.

## Activation : trois decisions du mainteneur

1. Lire et approuver la PR de configuration. Ne pas fusionner avant d'avoir
   verifie la securite et les couts avec ChatGPT.
2. Installer l'application officielle
   [Claude GitHub](https://github.com/apps/claude) uniquement sur
   `denamiel/Mirivue-kde` ; configurer dans
   `Settings > Secrets and variables > Actions > Secrets` le secret
   **`CLAUDE_CODE_OAUTH_TOKEN`**. Selon la formule Claude eligible,
   generer ce jeton **en local** avec `claude setup-token` (ou utiliser
   une cle API avec un workflow adapte apres validation du mode de facturation).
   **Ne jamais le copier dans un chat, une issue, un commit ou un journal.**
3. Apres la revue et la fusion de ce workflow sur `main`, creer
   `Settings > Secrets and variables > Actions > Variables` :
   `MIRIVUE_AGENT_ENABLED` avec valeur `true`.
   Lancer d'abord un **workflow_dispatch** de demonstration, puis
   examiner le resultat et les consommations avant de laisser agir
   l'horaire automatique (05:17 UTC, une fois par jour).

Pour couper tout developpement heberge, mettre la variable a `false`
ou desactiver le workflow depuis l'onglet Actions. Cela n'affecte ni
les installations locales de Mirivue, ni la surveillance ChatGPT.

## Garanties et limites

- Runner GitHub **heberge et jetable** ; `ubuntu-24.04` fixe pour eviter
  une modification implicite de l'image.
- Aucun declenchement par commentaire, PR externe ou push ; les instructions
  et le code de la branche sont traites comme non fiables.
- Concurrence de l'agent limitee a 1 execution, duree maximale 35 minutes,
  au plus 12 tours Claude par execution.
- Un controle de la PR #14 est effectue avant de recuperer sa branche.
- Le job est ignore si la variable d'activation n'est pas a `true`.
- L'agent peut **proposer et pousser des changements sur la PR #14** :
  il recoit donc des droits d'ecriture sur le depot. Les prompts de securite
  ne remplacent pas l'isolation, les rulesets, les protections et la revue.
- **Aucun droit d'administrateur ou de publication n'est requis.**
  La publication COPR/Pacman reste soumise aux protections existantes.
- Les runs Claude utilisent un quota/facturation Anthropic distinct du
  simple temps de runner ; le prix reel depend de la formule, du modele,
  des jetons et des limites du compte. Envisager un budget ou une limite.
- L'action officielle, ses dependances et l'authentification doivent etre
  controles sur un premier run : **aucune execution reussie n'est encore
  attestee** par cette proposition.
- Apres fusion de #14, ce workflow cesse de traiter ce chantier :
  il faudra definir et revoir un nouveau perimetre avant toute reprise.
- La surveillance automatique ChatGPT, distincte, continue a revoir GitHub.
  Elle ne remplace pas l'authentification Anthropic requise ici.

## Sources techniques

- https://github.com/anthropics/claude-code-action/blob/main/docs/setup.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/custom-automations.md
- https://github.com/anthropics/claude-code-action/blob/main/docs/security.md

## Criteres de revue avant activation

- [ ] Authentification/installation de l'App validees **sans exposer de jeton**
- [ ] Execution manuelle verifiee sur une tache volontairement simple
- [ ] Preuve d'absence de fusion/publication/edition de `main`
- [ ] Controle d'un compte rendu, des limites de cout et des droits
- [ ] Approbation explicite du mainteneur pour activer la cadence
