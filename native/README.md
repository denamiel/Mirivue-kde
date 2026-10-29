# Assistants natifs Qt 6 et KIO/KF6 (RC181)

Les sources C++ du dossier `native` construisent les assistants KIO de liste,
d'ouverture, d'associations, de transferts, de corbeille, de miniatures et
d'emplacements, ainsi que le suivi des tâches et la bibliothèque des widgets
KDE, ainsi que `libmirivue-item-presentation.so` (cache de dessin et en-tête).
`CMakeLists.txt` décrit les cibles et les bibliothèques Qt/KF6 requises.

Aucun exécutable précompilé n'est livré dans les sources de la RC181. Le paquet
CachyOS/Arch et l'installateur utilisateur recompilent les assistants pour la
machine d'installation, puis les placent dans le dossier `tools` installé. Une
compilation manuelle doit se faire dans un dossier de construction distinct ;
`Valider-RC181.sh` compile le module de présentation puis vérifie les tests
Python et Qt sur ce chemin natif, et
`Construire-paquet-CachyOS.sh` compile les cibles natives pour le paquet.

Pour les environnements de validation sans KF6, l’option CMake
`MIRIVUE_PRESENTATION_ONLY=ON` ne construit que le module de présentation.

Licences : voir `../LICENCES-TIERS.md` ; le code de Mirivue est sous MIT, le moteur de Dolphin conserve ses licences GPL-2.0-or-later et BSD-2-Clause.

Le tri naturel des noms utilise `natural-sort.cpp`, extrait du comparateur de
Dolphin 26.08.2 et compilé dans la bibliothèque de présentation Qt. La provenance
est décrite dans NATURAL-SORT-UPSTREAM.json. Les comparaisons des noms, accents,
décimaux et versions s’exécutent en C++, avec un QCollator propre à chaque
thread. Le chemin UTF-8 est mis en cache par ligne côté Python et renouvelé
après un renommage. Le repli Python concerne uniquement les sources non compilées ;
la validation d’une version exige le comparateur natif.
