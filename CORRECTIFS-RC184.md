# Correctifs RC184

- configuration.py : style de date déplacé dans Général → Affichage ; deux
  boutons exclusifs Relative / Absolue, comme Dolphin 26.08.2. Exemples à trente
  minutes ; Colonnes est réservé aux configurations de colonnes.
- native/kio-places-widget.cpp : petit pont original vers KFormat::formatRelativeDateTime.
- platform_services.py et date_display.py : emploi du formateur natif quand il
  est disponible. L'absolu régional et la lecture des anciennes valeurs ISO restent.
- Les préférences informal/locale ne changent pas. Un ancien choix iso devient
  locale seulement sur Appliquer/OK ; Annuler le conserve. Le défaut antérieur
  absolu régional reste inchangé.
- Tests : test_date_style_configuration.py (cinq nouveaux cas), adaptation du
  contrôle textuel de test_date_formats.py. Formulaires, contrôleur et modèles réels ;
  fenêtre d'application environnante contrôlée par une fixture.
- Version, scripts et documents mis à jour. Aucun remaniement des vues ni des
  opérations. Le partage volontaire de kservicemenurc reste inchangé.

Preuves avant/après et portée exacte : VALIDATION-RC184.md et validation/RC184.
La suite complète et le pont KIO complet n'ont pas été compilés/exécutés ici.
