# Vérification des trois fichiers KDE — révision 4

Les trois points laissés en attente dans la révision 3 sont résolus.
Source officielle : miroir KDE/dolphin, tag v26.08.2, REUSE.toml.
https://github.com/KDE/dolphin/blob/v26.08.2/REUSE.toml

Les motifs **/*.kcfg et **/*.kcfgc couvrent les deux fichiers de paramètres.
Le motif src/**/*.knsrc couvre src/settings/contextmenu/servicemenu.knsrc.
Tous déclarent SPDX-FileCopyrightText = KDE Contributors et
SPDX-License-Identifier = GPL-2.0-or-later.

Les copies Mirivue sont identiques octet par octet aux fichiers lus via l'API
GitHub au même tag. Aucun code ni contenu de configuration n'a été changé.
Des fichiers .license adjacents conservent explicitement l'attribution et la
licence. Les réponses d'origine (contenu, SHA Git et URL), REUSE.toml et les
empreintes SHA-256 comparées figurent dans packaging/preuves-kde/ et sont
installés dans le dossier des licences du RPM.

Réponses Git des fichiers :
- REUSE.toml : 28658ff266740c258d94c6b0d11f6bea9d8d9442
- .kcfg : 6e8f8e9d54b67816650de5110da1e3f106f46816
- .kcfgc : ba7077c45e59ad1f4e62c4c13cd39cbe7942a9ca
- .knsrc : f0e6ddbf146c25c0ea7ef5c2b8508424bd57ebc5

Ce constat remplace les réserves sur ces trois fichiers dans MENTIONS-RC195-r3.md,
conservé comme historique. Les réserves générales sur une preuve exhaustive de
provenance et de titularité ne deviennent pas une certification juridique.

Version applicative : RC195 inchangée. RPM : 0.195.rc195.3.fc44.
Contrôles locaux : comparaisons exactes, analyse TOML/XML, notices adjacentes,
syntaxe Bash/Python, politique AppStream et intégrité des entrées.
La construction de cette révision sous Fedora n'est pas exécutée ici ; COPR
pourra la faire à partir du SRPM. Aucun paquet n'a été envoyé à COPR.
