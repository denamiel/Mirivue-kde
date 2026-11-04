# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Standard KDE diagnostic dialogs, separate from file operations."""
from PySide6.QtWidgets import QApplication, QMessageBox
from . import __version__, RELEASE_DATE, AUTHOR, BUILD_REVISION
from .i18n import tr, trf
from .diagnostics import diagnostic_report, state_directory
from .platform_services import services


class DiagnosticDialogsMixin:
    def show_about(self):
        QMessageBox.about(self, tr('À propos de Mirivue'), trf('<h2>Mirivue</h2><p>Version : <b>\x1f0\x1f</b><br>Révision du paquet : <b>\x1f3\x1f</b><br>Date de publication : \x1f1\x1f<br>Nom : <b>\x1f2\x1f</b></p><p>Your Media, Clearly Organised</p><p>Gestion de fichiers et lecture locale des informations de vos vidéos, sons et images sous Linux.</p><p>Python · Qt/PySide6 · MediaInfo · FFmpeg<br>Distribution combinée : GNU GPL v3 ou ultérieure.<br>Parties originales sous MIT ; composants tiers sous leurs licences propres.<br>Voir LICENSE et LICENCES-TIERS.md dans les sources.</p>', __version__, RELEASE_DATE, AUTHOR, BUILD_REVISION))

    def show_diagnostics(self):
        report = diagnostic_report(__version__)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(tr('Diagnostic de Mirivue'))
        box.setText(tr('Informations sur l’installation de Mirivue.'))
        box.setInformativeText(tr('Ce rapport décrit les composants disponibles ; il ne détermine pas la cause d’un incident. Les erreurs sont consignées dans le journal local.'))
        box.setDetailedText(report)
        copy_button = box.addButton(tr('Copier le diagnostic'), QMessageBox.ButtonRole.ActionRole)
        folder_button = box.addButton(tr('Ouvrir le dossier des journaux'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is copy_button:
            QApplication.clipboard().setText(report)
            self.show_activity_message(tr('Diagnostic copié.'), 4000)
        elif box.clickedButton() is folder_button:
            state_directory().mkdir(parents=True, exist_ok=True)
            services.open_default_file(state_directory())

    def show_previous_unclean_shutdown(self):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr('Arrêt précédent incomplet'))
        box.setText(tr('Une session précédente n’a pas enregistré de fermeture normale.'))
        box.setInformativeText(tr('Cela peut suivre un arrêt forcé ou un plantage. Cette détection ne prouve pas une perte de fichiers. Si un transfert était en cours, vérifiez la source et la destination. Consultez le journal pour rechercher la cause.'))
        diagnostic_button = box.addButton(tr('Afficher le diagnostic'), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is diagnostic_button:
            self.show_diagnostics()

