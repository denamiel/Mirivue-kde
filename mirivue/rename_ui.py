"""Integrated rename editor and shared metadata proposal preview."""
from PySide6.QtCore import QTimer, QSignalBlocker
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QLineEdit, QSpinBox, QLabel, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QMessageBox)
from PySide6.QtCore import Qt
from .i18n import tr, trf
from .iconography import context_help_button
from .renaming import batch_names, prepare_names
from .extensions import apply_renames

def show_advanced_rename(self, rows, folder=None, initial_method='manual'):
    if self.selection_locked():
        QMessageBox.information(self, tr('Opérations en cours'), tr('Un fichier sélectionné, ou un fichier de ce dossier, est utilisé par une opération. Attendez sa fin ou annulez-la.'))
        return False
    if self.scanning:
        return
    if not rows:
        return
    dialog = QDialog(self)
    dialog.setWindowTitle(trf('Renommer le contenu de « \x1f0\x1f »', folder.name) if folder else tr('Renommage avancé'))
    dialog.resize(820, 520)
    dialog.setMinimumSize(580, 400)
    dialog.setSizeGripEnabled(True)
    layout = QVBoxLayout(dialog)
    rename_help = QHBoxLayout()
    rename_help.addStretch(1)
    rename_help.addWidget(context_help_button(dialog, tr('Les nouveaux noms s’affichent immédiatement et peuvent être ajustés dans le tableau. Les extensions sont conservées. Les noms déjà corrects sont ignorés et aucun fichier existant n’est écrasé.')))
    layout.addLayout(rename_help)
    rules = QComboBox()
    rules.setObjectName(tr('batch-rename-method'))
    rules.addItem(tr('À partir des métadonnées'), 'metadata')
    rules.addItem(tr('Modifier les noms manuellement'), tr('manual'))
    rules.addItem(tr('Ajouter du texte au début'), tr('prefix'))
    rules.addItem(tr('Ajouter du texte à la fin'), tr('suffix'))
    rules.addItem(tr('Rechercher et remplacer'), tr('replace'))
    rules.addItem(tr('Numéroter'), tr('number'))
    rules.addItem(tr('Mettre une majuscule au début de chaque mot'), tr('title'))
    rule_form = QFormLayout()
    rule_form.addRow(tr('Méthode :'), rules)
    rules.setCurrentIndex(max(0, rules.findData(initial_method)))
    first = QLineEdit('{artist} - {title}' if initial_method == 'metadata' else '')
    first.setObjectName(tr('batch-rename-primary'))
    second = QLineEdit()
    second.setObjectName(tr('batch-rename-secondary'))
    start_number = QSpinBox()
    start_number.setObjectName(tr('batch-rename-start'))
    start_number.setRange(0, 999999999)
    start_number.setValue(1)
    digits = QSpinBox()
    digits.setObjectName(tr('batch-rename-digits'))
    digits.setRange(1, 9)
    digits.setValue(3)
    first_label = QLabel(tr('Texte :'))
    second_label = QLabel(tr('Remplacer par :'))
    start_label = QLabel(tr('Début :'))
    digits_label = QLabel(tr('Chiffres :'))
    rule_form.addRow(first_label, first)
    rule_form.addRow(second_label, second)
    rule_form.addRow(start_label, start_number)
    rule_form.addRow(digits_label, digits)
    layout.addLayout(rule_form)
    table = QTableWidget(len(rows), 2)
    table.setObjectName('renamePreview')
    table.setHorizontalHeaderLabels([tr('Nom actuel'), tr('Nouveau nom')])
    for index, row in enumerate(rows):
        old_item = QTableWidgetItem(row.path.name)
        old_item.setFlags(old_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        old_item.setToolTip(str(row.path))
        table.setItem(index, 0, old_item)
        table.setItem(index, 1, QTableWidgetItem(row.path.name))
    table.setColumnWidth(0, 300)
    table.setMinimumWidth(0)
    table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(table)
    status = QLabel(tr('Aucun fichier existant ne sera écrasé.'))
    status.setWordWrap(True)
    status.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(status)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
    accept = buttons.addButton(tr('Renommer'), QDialogButtonBox.ButtonRole.AcceptRole)
    accept.setAutoDefault(False)
    layout.addWidget(buttons)
    plans = []

    def update_rule_form():
        mode = rules.currentData()
        first_label.setVisible(mode != tr('manual'))
        first.setVisible(mode != tr('manual'))
        second_label.setVisible(mode == tr('replace'))
        second.setVisible(mode == tr('replace'))
        start_label.setVisible(mode == tr('number'))
        start_number.setVisible(mode == tr('number'))
        digits_label.setVisible(mode == tr('number'))
        digits.setVisible(mode == tr('number'))
        if mode == 'metadata':
            first_label.setText(tr('Modèle de nom :'))
            first.setPlaceholderText('{artist} - {title}')
            first.setToolTip(tr('Champs : {title}, {artist}, {album}, {tracknumber}, {date_taken}. Les extensions sont conservées.'))
        if mode == tr('prefix'):
            first_label.setText(tr('Texte :'))
        elif mode == tr('suffix'):
            first_label.setText(tr('Texte :'))
        elif mode == tr('replace'):
            first_label.setText(tr('Rechercher :'))
        elif mode == tr('number'):
            first_label.setText(tr('Nom de base :'))
        elif mode != 'metadata':
            first_label.setText(tr('Texte :'))
        update_proposed_names()

    def validate():
        nonlocal plans
        plans = prepare_names(rows, [table.item(i, 1).text() for i in range(len(rows))])
        ready_sources = {plan.source for plan in plans if not plan.issue}
        issues = {plan.source: plan.issue for plan in plans if plan.issue}
        # Qt's FontRole changes only the weight. Clearing it restores the
        # inherited theme font; no family, size, foreground or background is set.
        with QSignalBlocker(table):
            for index, row in enumerate(rows):
                item = table.item(index, 1)
                font = QFont()
                font.setBold(True)
                item.setData(Qt.ItemDataRole.FontRole, font if row.path in ready_sources else None)
                item.setToolTip(issues.get(row.path) or (tr('Ce nom sera modifié.') if row.path in ready_sources else tr('Nom inchangé.')))
        errors = [trf('\x1f0\x1f : \x1f1\x1f', p.source.name, p.issue) for p in plans if p.issue]
        ready = sum((not p.issue for p in plans))
        unchanged = len(rows) - len(plans)
        summary = trf('\x1f0\x1f à renommer · \x1f1\x1f déjà correctement nommé(s) ignoré(s) · \x1f2\x1f conflit(s) ignoré(s).', ready, unchanged, len(errors))
        status.setText(tr('\n').join([summary, tr('En gras : noms qui seront modifiés.'), *errors]))
        accept.setEnabled(ready > 0)

    def update_proposed_names(*_):
        mode = rules.currentData()
        if mode == tr('manual'):
            return
        try:
            names = batch_names(rows, mode, first.text(), second.text(), start_number.value(), digits.value())
        except (ValueError, KeyError, AttributeError, IndexError) as error:
            with QSignalBlocker(table):
                for index in range(len(rows)):
                    table.item(index, 1).setData(Qt.ItemDataRole.FontRole, None)
                    table.item(index, 1).setToolTip(str(error))
            status.setText(str(error))
            accept.setEnabled(False)
            return
        table.blockSignals(True)
        for index, name in enumerate(names):
            table.item(index, 1).setText(name)
        table.blockSignals(False)
        validate()
    rules.currentIndexChanged.connect(update_rule_form)
    first.textChanged.connect(update_proposed_names)
    second.textChanged.connect(update_proposed_names)
    start_number.valueChanged.connect(update_proposed_names)
    digits.valueChanged.connect(update_proposed_names)
    table.itemChanged.connect(validate)
    update_rule_form()
    validate()
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    table.setCurrentCell(0, 1)
    QTimer.singleShot(0, lambda: table.editItem(table.item(0, 1)))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    plans = prepare_names(rows, [table.item(i, 1).text() for i in range(len(rows))])
    renamed, errors = apply_renames(plans)
    self.record_local_renames(renamed)
    renamed_count = sum((plan.source in renamed for plan in plans))
    # Keep the selected rows selected after a batch rename.  The model
    # order is unchanged, so a reset would unnecessarily clear the
    # selection in both the Details and Icons views.
    if folder is None:
        self.update_renamed_rows(renamed, reset=False)
    elif renamed:
        self.refresh_other_panes([folder, *renamed, *renamed.values()])
    if errors:
        box = QMessageBox(self)
        box.setWindowTitle(tr('Rapport de renommage'))
        box.setText(trf('\x1f0\x1f fichier(s) renommé(s), \x1f1\x1f ignoré(s) ou en échec.', renamed_count, len(errors)))
        box.setDetailedText(tr('\n').join(errors))
        box.exec()
    self.show_activity_message(trf('\x1f0\x1f élément(s) renommé(s).', renamed_count), 6000)

