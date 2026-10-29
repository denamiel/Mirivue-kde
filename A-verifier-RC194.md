# Vérifications restantes — RC194

Les tests hors écran ne valident pas une session Fedora KDE réelle.

- Sous Fedora 44 KDE : Valider-RC194.sh doit terminer sans échec ; les journaux
  complets sont conservés et leur chemin est affiché, même si la commande échoue.
- Installer.sh compile et installe pour le compte courant, sans sudo.
- Menu principal : ouvrir, fermer, rappeler au clavier, personnaliser la barre.
- Demandes externes : réutilisation des dossiers déjà ouverts dans deux fenêtres.
- Wayland : activation de la bonne fenêtre et conservation de l’état agrandi.
- Corbeille KIO, annulation, transferts et conflits : uniquement sur fichiers jetables.
- Glisser un onglet puis le détacher ; vérifier les deux panneaux et leur sélection.

Aucun résultat Fedora, Wayland, SELinux ni installation réelle n’est déclaré
validé par les mesures locales de cette version. Le protocole antérieur reste
applicable ; il ne faut pas contourner une validation en échec.
