# Diagnostic du démarrage hébergé — 12 novembre 2026

## Preuves vérifiées directement sur GitHub

- Le [premier run Claude 43096539304](https://github.com/denamiel/Mirivue-kde/actions/runs/43096539304), au SHA `add639c76aa860b106af4c1f6a6cc1d1cbe247f4`, reste `completed/startup_failure`, tentative 1, avec zéro job. Création : 11 novembre à 20:31:15 UTC ; dernière mise à jour : 21:09:15 UTC. Claude et son authentification OAuth n'ont pas été exécutés.
- L'[incident officiel GitHub](https://www.githubstatus.com/incidents/dvy0t3mvh1lg) signale Actions dégradé à 20:48 UTC, une mitigation à 21:07 UTC et une résolution à 21:21 UTC le 11 novembre. La période recouvre l'échec du run : une cause d'infrastructure est plausible, sans preuve d'attribution définitive à ce run. L'incident ne suffit pas à expliquer le diagnostic minimal initial, créé après la résolution annoncée.
- Le [diagnostic minimal 43103588934](https://github.com/denamiel/Mirivue-kde/actions/runs/43103588934), PR #18, SHA `44a74f78e04f198a3d7f219cfde671f0449689a1`, avait un job annulé `130801047067`. Son journal renvoie encore `404 BlobNotFound` lors de cette vérification.
- Une seule relance ciblée de ce job minimal, après rétablissement annoncé, a réussi le 12 novembre à 12:29 UTC : [job 131183210859](https://github.com/denamiel/Mirivue-kde/actions/runs/43103588934/job/131183210859). Les trois étapes réussissent. Le journal atteste Ubuntu 24.04, `Contents: read`, l'événement `pull_request`, le dépôt attendu et le message « Diagnostic GitHub Actions : job demarre correctement ». Aucun checkout, aucune action tierce, aucun secret consommé par le scénario, aucune opération d'écriture.
- Une tentative de relancer les jobs échoués de l'ancien run Claude est refusée par GitHub : HTTP 403, `This workflow run cannot be retried`. Aucun nouveau run Claude n'a donc été lancé.

## Conclusion et suite

Le démarrage minimal sur PR fonctionne désormais. Cela ne valide ni `workflow_dispatch`, ni l'action Anthropic, ni OAuth. Aucun défaut du YAML Claude n'est démontré par ces observations ; aucun élargissement de permissions ni modification spéculative de son workflow n'est justifié.

Le connecteur utilisé ne propose pas de nouveau `workflow_dispatch`. Le mainteneur doit lancer une nouvelle exécution via **Actions > Mirivue - Claude heberge (diagnostic manuel) > Run workflow > main**, puis communiquer son lien. Ne pas demander le secret OAuth. Vérifier ensuite les étapes, l'authentification, les outils effectifs et l'usage Anthropic avant d'envisager une phase d'écriture ou une planification.

Si une nouvelle exécution échoue encore avant création de job, transmettre au support GitHub l'URL, les heures, `jobs=[]` et l'identifiant initial `98BB:32A6D2:475103B:604A861:6AF4D8A5`. Une relance en boucle n'apporte pas de preuve supplémentaire.

## État des chantiers

- #13 : ouverte, brouillon, HEAD `9d7ac36f64bc4445b675d268b5c70f1e7deb63fb` ; faisabilité VM documentée, stabilité prolongée non établie.
- #14 : ouverte, brouillon, empilée sur #13, HEAD `2682b09620e49549752e92c320f4cf5e69978435` ; revue demandant notamment de corriger le classement des échecs après démarrage et le calcul des observations indépendantes. Ces corrections restent à traiter.
- #15 : ouverte, brouillon, HEAD `de0a9314d14a87fdb9811131d8ab9248805007f5` ; revue demandant les six noms exacts de checks et une description actualisée du diagnostic hébergé. Corrections encore à traiter.
- #16 : fermée et fusionnée ; le workflow présent sur main est manuel et en lecture seule, sans cron. Le titre et le corps historiques de la PR décrivent une préparation plus large que le contenu final.
- #17 : ouverte ; incident de démarrage encore à valider par un nouveau run Claude.
- #18 : ouverte, brouillon ; diagnostic minimal désormais réussi, sans nécessité de fusion pour cette preuve.

Toutes les opérations de cette reprise passent par les API cloud. Aucune commande, installation, compilation, aucun test ni contrôle d'ordinateur sur les postes personnels. Aucune fusion, publication, modification de secret ou protection de main.
