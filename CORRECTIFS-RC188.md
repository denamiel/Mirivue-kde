# Correctifs RC188

- Groupes de réglages cohérents et titre Configurations de colonnes.
- Indications de raccourcis dynamiques et réutilisation de l'action de configuration.
- Aide native des commandes indisponibles, sans boîte de message supplémentaire.
- Vrai dialogue KDE KEditToolBar, préférences XMLGUI propres à Mirivue, reprise
  des dispositions et conservation des séparateurs, espaces, icônes et textes.
- Annulation d'un rappel différé lorsque la catégorie de configuration est détruite.

Le nouveau fichier C++ original est sous MIT et indexé dans LICENCES-TIERS.md.
Le nombre de sources natives MIT passe de seize à dix-sept. La distribution
combinée reste GPL-3.0-or-later.

42 contrôles ciblés réussissent trois fois. Le nouveau composant est compilé
isolément et trois tests utilisent un vrai dialogue KDE, avec les versions et
limites détaillées dans VALIDATION-RC188.md. La suite complète et la compilation
de l'ensemble ne sont pas déclarées exécutées sur cet hôte.
