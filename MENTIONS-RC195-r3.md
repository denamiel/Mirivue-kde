# Corrections des mentions — RC195, révision RPM 3

## Corrections appliquées

- Scripts et recette externes : mentions MIT et attribution collective déjà employée par le projet ; LICENSE-KIT.txt inclus comme Source2 dans le SRPM.
- Métadonnées : en-têtes CC0-1.0, texte CC0 dans LICENSES racine et licence CC0 ajoutée à la déclaration du RPM.
- Icônes : fichiers .license explicites sous MIT, attribution collective Mirivue contributors, notice installée aussi dans le dossier central des licences.
- Adaptateurs locaux dolphin_export.h et dolphindebug.* : déclaration GPL-3.0-or-later de la distribution du projet. Ils ne figurent pas dans la liste des sources amont UPSTREAM.json ; les en-têtes KDE existants restent intacts.
- Trois images de diagnostic exclues de la nouvelle archive source. Les originaux restent dans le kit r2 et l'archive d'audit ; aucun fichier original n'a été effacé. Les tests sources sont conservés.
- Version applicative inchangée ; révision RPM 0.195.rc195.2.fc44.

## Points non résolus — ne pas présenter cette révision comme auditée intégralement

Les fichiers settings/dolphin_contentdisplaysettings.kcfg et .kcfgc proviennent de Dolphin 26.08.2 selon UPSTREAM.json ; mirivue/servicemenu.knsrc est documenté comme repris du même projet. Leurs licences fichier par fichier n'ont pas pu être confirmées à distance dans cette session. Aucune licence MIT ne leur a été attribuée par défaut.

L'originalité de l'icône reste une déclaration du projet, déjà présente dans sa notice ; une annotation SPDX ne démontre pas sa provenance. Aucun auteur individuel n'a été inventé.

La licence générale couvre les créations du projet sans en-tête individuel ; les annotations ajoutées ne remplacent aucune licence tierce et ne constituent pas une preuve de titularité. CMakeLists.txt, README.md et les manifestes de provenance du moteur restent couverts par la déclaration générale, à l'exception des licences amont explicitement documentées.

La recette installe la présente notice, les mentions d'icônes, LICENSES racine et les textes KDE. Le RPM et SRPM finaux doivent encore être construits/extraits sous Fedora, puis leur contenu contrôlé. Aucun RPM Fedora n'est construit ici.

## Validation locale

Syntaxe Bash et Python, analyse XML, présence des notices et des Source1/Source2, politique de validation AppStream et conservation des en-têtes KDE vérifiées. Reconstruction Mock et affichage Discover non exécutés dans cette session.
