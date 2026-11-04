# Construction Fedora 44/45

Depuis un clone Git, sous Fedora 44/45 classique :

```bash
cd packaging/fedora
bash Preparer-Sources.sh
bash Construire-RPM.sh --source-only
```

Le SRPM est produit dans `SRPM/`. Pour vérifier la reconstruction propre :

```bash
bash Verifier-Reconstruction-Propre.sh
```

Après fermeture de Mirivue, `bash Installer-RPM.sh` installe le résultat.
Ne pas lancer ces scripts avec sudo ; ils demandent les droits nécessaires.

La préparation utilise uniquement le commit courant, sans modifications locales non commitées. L'archive Git contient une organisation documentaire différente de l'archive de la publication COPR initiale. Incrémenter Release dans la recette avant une nouvelle publication. Les scripts interrogent la recette pour connaître le nom du paquet et utilisent la version de Fedora installée.

Source1 contient le validateur AppStream, Source2 la licence des outils. Les scripts de ce dossier sont sous MIT (LICENSE-KIT.txt) ; les composants tiers conservent leurs licences.
