from .i18n import tr, trf
tr('Small local organisation tools: collections, labels, recents and folder overview.')
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QActionGroup
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout
from . import library
from .metadata import HEADERS, duration, quantity
LABELS = {tr('À conserver'): 'positive', tr('À trier'): 'neutral',
          tr('À supprimer'): 'negative', tr('À partager'): 'link'}

def label_for_display(label):
    # Keep the stored value compatible with labels saved by earlier versions.
    return tr('À examiner pour suppression') if label in (tr('À supprimer'), 'À supprimer', 'To Delete') else label

DISPLAY_LABEL_ROLES = {label_for_display(label): role for label, role in LABELS.items()}

class OrganizationMixin:

    def init_organization(self, file_menu, organize_menu, view_menu, operations_menu):
        self.personal_labels = library.read(self.settings, tr('personal-labels-v1'), {})
        if not isinstance(self.personal_labels, dict):
            self.personal_labels = {}
        self.recent_items = library.read(self.settings, tr('recent-items-v1'), [])
        if not isinstance(self.recent_items, list):
            self.recent_items = []
        self.recent_menu = QMenu(tr('Fichiers récents'), file_menu)
        file_menu.insertMenu(self.properties_action, self.recent_menu)
        self.recent_separator = file_menu.insertSeparator(self.recent_menu.menuAction())
        self.recent_menu.aboutToShow.connect(self.populate_recent_menu)
        self.set_recent_media_enabled(self.settings.value('privacy/remember-recent-media', True, type=bool), clear_when_disabled=True)
        self.collections_menu = organize_menu.addMenu(tr('Collections'))
        self.collections_menu.aboutToShow.connect(self.populate_collections_menu)
        view_menu.addSeparator()
        sort_menu = view_menu.addMenu(tr('Trier par'))
        self.sort_menu = sort_menu
        self.sort_column_actions = {}
        column_group = QActionGroup(self)
        column_group.setExclusive(True)
        for title, column in [(tr('Nom'), 0), (tr('Taille'), 1), (tr('Date de modification'), 14), (tr('Type de média'), 17)]:
            current = sort_menu.addAction(title)
            current.setCheckable(True)
            current.triggered.connect(lambda checked=False, c=column: self.table.sortByColumn(c, self.table.horizontalHeader().sortIndicatorOrder()))
            column_group.addAction(current)
            self.sort_column_actions[column] = current
        sort_menu.addSeparator()
        for title, column in [(tr('Date de prise de vue'), 26), (tr('Artiste'), 19), (tr('Album'), 20), (tr('Résolution'), 3), (tr('Durée'), 2)]:
            current = sort_menu.addAction(title)
            current.setCheckable(True)
            current.triggered.connect(lambda checked=False, c=column: self.table.sortByColumn(c, self.table.horizontalHeader().sortIndicatorOrder()))
            column_group.addAction(current)
            self.sort_column_actions[column] = current
        sort_menu.addSeparator()
        order_group = QActionGroup(self)
        order_group.setExclusive(True)
        self.sort_ascending_action = sort_menu.addAction(tr('Ordre croissant'))
        self.sort_descending_action = sort_menu.addAction(tr('Ordre décroissant'))
        for current in (self.sort_ascending_action, self.sort_descending_action):
            current.setCheckable(True)
            order_group.addAction(current)
        self.sort_ascending_action.triggered.connect(lambda checked=False: self.table.sortByColumn(self.table.horizontalHeader().sortIndicatorSection(), Qt.SortOrder.AscendingOrder))
        self.sort_descending_action.triggered.connect(lambda checked=False: self.table.sortByColumn(self.table.horizontalHeader().sortIndicatorSection(), Qt.SortOrder.DescendingOrder))
        sort_menu.addSeparator()
        self.folders_first_action = sort_menu.addAction(tr('Trier les dossiers avant les fichiers'))
        self.folders_first_action.setCheckable(True)
        self.folders_first_action.toggled.connect(self.set_folders_first)
        sort_menu.aboutToShow.connect(self.sync_sort_menu)
        self.folder_summary_action = view_menu.addAction(tr('Résumé du dossier'), self.show_folder_summary)

    def sync_sort_menu(self):
        header = self.table.horizontalHeader()
        column = header.sortIndicatorSection()
        if column in self.sort_column_actions:
            self.sort_column_actions[column].setChecked(True)
        ascending = header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        self.sort_ascending_action.setChecked(ascending)
        self.sort_descending_action.setChecked(not ascending)
        self.folders_first_action.blockSignals(True)
        self.folders_first_action.setChecked(bool(self.proxy.folders_first))
        self.folders_first_action.blockSignals(False)

    def apply_personal_label(self, row):
        entry = self.personal_labels.get(str(row.path), {})
        signature = entry.get(tr('signature')) if isinstance(entry, dict) else None
        if signature is not None and row.file_signature is not None and (list(row.file_signature) != signature):
            return
        row.personal_label = label_for_display(str(entry.get(tr('label'), ''))) if isinstance(entry, dict) else ''
        row.personal_label_color = str(entry.get(tr('color'), '')) if isinstance(entry, dict) else ''

    def add_personal_label_menu(self, menu, rows):
        labels = menu.addMenu(tr('Étiquette personnelle'))
        rows = list(rows)
        for label, color in LABELS.items():
            display_label = label_for_display(label)
            action = labels.addAction(display_label)
            action.setIconText(display_label)
            action.triggered.connect(lambda checked=False, value=label, tint=color: self.set_personal_label(rows, value, tint))
        labels.addSeparator()
        labels.addAction(tr('Retirer l’étiquette'), lambda: self.set_personal_label(rows, '', ''))

    def set_personal_label(self, rows, label, color):
        changed = 0
        for row in rows:
            if row.is_dir:
                continue
            if label:
                self.personal_labels[str(row.path)] = dict(label=label, color=color, signature=list(row.file_signature) if row.file_signature else None)
            else:
                self.personal_labels.pop(str(row.path), None)
            row.personal_label, row.personal_label_color = (label_for_display(label), color)
            changed += 1
        library.write(self.settings, tr('personal-labels-v1'), self.personal_labels)
        self.update_summary()
        self.repaint_panes()
        if changed:
            self.show_activity_message(trf('Étiquette « \x1f0\x1f » appliquée à \x1f1\x1f élément(s).', label_for_display(label), changed) if label else trf('Étiquette retirée de \x1f0\x1f élément(s).', changed), 5000)

    def set_recent_media_enabled(self, enabled, clear_when_disabled=True):
        enabled = bool(enabled)
        self.settings.setValue('privacy/remember-recent-media', enabled)
        if not enabled and clear_when_disabled:
            self.clear_recents()
        if hasattr(self, tr('recent_menu')):
            self.recent_menu.menuAction().setVisible(enabled)
        if hasattr(self, tr('recent_separator')):
            self.recent_separator.setVisible(enabled)

    def remember_recent(self, path):
        if not self.settings.value('privacy/remember-recent-media', True, type=bool):
            return
        path = Path(path)
        if path.is_dir() or not path.exists():
            return
        values = [str(p) for p in self.recent_items if str(p) != str(path)]
        values.insert(0, str(path))
        self.recent_items = values[:25]
        library.write(self.settings, tr('recent-items-v1'), self.recent_items)

    def populate_recent_menu(self):
        self.recent_menu.clear()
        current = [Path(value) for value in self.recent_items if Path(value).exists()]
        self.recent_items = [str(path) for path in current]
        if not current:
            action = self.recent_menu.addAction(tr('Aucun fichier récent'))
            action.setEnabled(False)
        else:
            for path in current:
                action = self.recent_menu.addAction(path.name)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, p=path: self.open_url(p))
            self.recent_menu.addSeparator()
            self.recent_menu.addAction(tr('Effacer la liste des fichiers récents'), self.clear_recents)

    def clear_recents(self):
        self.recent_items = []
        library.write(self.settings, tr('recent-items-v1'), self.recent_items)

    def collections(self):
        data = library.read(self.settings, tr('collections-v1'), {})
        return data if isinstance(data, dict) else {}

    def save_collections(self, data):
        library.write(self.settings, tr('collections-v1'), data)

    def populate_collections_menu(self):
        self.collections_menu.clear()
        selected = [row for row in (self.row(index) for index in self.selected_indexes()) if not row.is_dir]
        add = self.collections_menu.addAction(tr('Ajouter la sélection à une collection…'))
        add.setEnabled(bool(selected))
        add.triggered.connect(lambda: self.add_to_collection(selected))
        self.collections_menu.addAction(tr('Gérer les collections…'), self.manage_collections)
        collections = self.collections()
        if collections:
            self.collections_menu.addSeparator()
            for name in sorted(collections, key=str.casefold):
                self.collections_menu.addAction(name, lambda checked=False, n=name: self.open_collection(n))

    def add_to_collection(self, rows):
        collections = self.collections()
        choices = sorted(collections, key=str.casefold) + [tr('Nouvelle collection…')]
        choice, ok = QInputDialog.getItem(self, tr('Ajouter à une collection'), tr('Collection :'), choices, 0, False)
        if not ok:
            return
        if choice == tr('Nouvelle collection…'):
            choice, ok = QInputDialog.getText(self, tr('Nouvelle collection'), tr('Nom :'))
            choice = choice.strip()
            if not ok or not choice:
                return
        paths = list(dict.fromkeys([*collections.get(choice, []), *(str(row.path) for row in rows)]))
        collections[choice] = paths
        self.save_collections(collections)
        self.show_activity_message(trf('\x1f0\x1f média(s) ajouté(s) à « \x1f1\x1f ».', len(rows), choice), 5000)

    def open_collection(self, name):
        files = [Path(path) for path in self.collections().get(name, []) if Path(path).exists()]
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Collection — ') + name)
        dialog.resize(700, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(trf('\x1f0\x1f média(s) enregistré(s) localement.', len(files))))
        listing = QListWidget()
        for path in files:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            listing.addItem(item)

        def open_item(item):
            if item:
                self.open_url(item.data(Qt.ItemDataRole.UserRole))
        listing.itemActivated.connect(open_item)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        open_button = buttons.addButton(tr('Ouvrir'), QDialogButtonBox.ButtonRole.AcceptRole)
        open_button.clicked.connect(lambda: open_item(listing.currentItem()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def manage_collections(self):
        collections = self.collections()
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Gérer les collections'))
        dialog.resize(650, 420)
        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels([tr('Collection / média'), tr('Emplacement')])
        for name in sorted(collections, key=str.casefold):
            parent = QTreeWidgetItem([name, ''])
            parent.setData(0, Qt.ItemDataRole.UserRole, (tr('collection'), name))
            tree.addTopLevelItem(parent)
            for text in collections[name]:
                path = Path(text)
                child = QTreeWidgetItem([path.name, str(path)])
                child.setData(0, Qt.ItemDataRole.UserRole, (tr('item'), name, text))
                parent.addChild(child)
            parent.setExpanded(True)
        layout.addWidget(tree)
        buttons = QHBoxLayout()
        remove = QPushButton(tr('Retirer l’élément sélectionné'))
        close = QPushButton(tr('Fermer'))

        def remove_selected():
            data = tree.currentItem().data(0, Qt.ItemDataRole.UserRole) if tree.currentItem() else None
            if not data:
                return
            if data[0] == tr('collection'):
                collections.pop(data[1], None)
            else:
                collections[data[1]] = [value for value in collections.get(data[1], []) if value != data[2]]
                if not collections[data[1]]:
                    collections.pop(data[1], None)
            self.save_collections(collections)
            dialog.accept()
            self.manage_collections()
        remove.clicked.connect(remove_selected)
        close.clicked.connect(dialog.accept)
        buttons.addWidget(remove)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    def show_folder_summary(self):
        rows = [self.row(self.proxy.index(i, 0)) for i in range(self.proxy.rowCount())]
        media = [row for row in rows if not row.is_dir and row.media_type in (tr('video'), tr('audio'), tr('image'))]
        counts = {kind: sum((row.media_type == kind for row in media)) for kind in (tr('video'), tr('audio'), tr('image'))}
        bytes_total = sum((max(0, row.sort_values[1]) for row in rows if not row.is_dir))
        seconds = sum((max(0, row.sort_values[2]) for row in media if row.media_type in (tr('video'), tr('audio'))))
        text = trf('<b>\x1f0\x1f</b><br><br>Vidéos : \x1f1\x1f<br>Sons : \x1f2\x1f<br>Images : \x1f3\x1f<br>Fichiers affichés : \x1f4\x1f<br>Taille affichée : \x1f5\x1f<br>Durée audio et vidéo : \x1f6\x1f', Path(self.folder or '').name or 'Dossier', counts['video'], counts['audio'], counts['image'], sum((not row.is_dir for row in rows)), quantity(bytes_total, ['o', 'Kio', 'Mio', 'Gio', 'Tio'], 1024), duration(seconds))
        QMessageBox.information(self, tr('Résumé du dossier'), text)

    def compare_selected(self):
        rows = [self.row(index) for index in self.selected_indexes() if not self.row(index).is_dir]
        if len(rows) != 2:
            QMessageBox.information(self, tr('Comparer deux médias'), tr('Sélectionnez exactement deux fichiers, images, sons ou vidéos.'))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Comparer deux médias'))
        dialog.resize(860, 560)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels([tr('Information'), rows[0].path.name, rows[1].path.name])
        columns = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 14, 17, 18, 19, 20, 22, 23, 26, 27, 28, 29]
        for column in columns:
            left, right = (rows[0].values[column], rows[1].values[column])
            if not left and (not right):
                continue
            index = table.rowCount()
            table.insertRow(index)
            for current, value in enumerate((HEADERS[column], left, right)):
                table.setItem(index, current, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
