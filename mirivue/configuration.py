from .i18n import tr
tr('A single, Plasma-style configuration window for persistent Mirivue choices.')
from pathlib import Path
from .platform_services import services
from PySide6.QtCore import QEvent, QPointF, Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QPalette, QTextLayout, QTextOption
from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QCheckBox, QRadioButton, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QListWidgetItem, QPushButton, QSpinBox, QStackedWidget, QVBoxLayout, QWidget, QFileDialog, QStyle, QStyledItemDelegate, QStyleOptionFocusRect, QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QKeySequenceEdit, QHeaderView, QSizePolicy, QGroupBox, QScrollArea
from .metadata import HEADERS, modification_text
from .iconography import context_help_button
import time
PAGE_ICONS = {
    # Semantic Breeze category/application icons; prefer these over action
    # and *-symbolic icons that render monochrome at this size.
    tr('Général'): ('folder', 'system-file-manager'),
    tr('Menu contextuel'): ('preferences-desktop-context-menu', 'preferences-desktop'),
    tr('Configurations de colonnes'): ('x-office-spreadsheet', 'preferences-desktop-icons', 'view-list-details'),
    tr('Aperçus et lecture'): ('applications-multimedia', 'preferences-desktop-multimedia'),
    tr('Applications externes'): ('preferences-desktop-filetype-association', 'preferences-desktop-default-applications', 'applications-utilities'),
}

# Qt's standard icons are provided by the active KDE widget style as a last
# resort.  Not every Breeze installation supplies every semantic icon name,
# and KIconTheme's fallback theme may differ between Plasma and GNOME.
PAGE_ICON_FALLBACKS = {
    tr('Général'): QStyle.StandardPixmap.SP_DirHomeIcon,
    tr('Configurations de colonnes'): QStyle.StandardPixmap.SP_FileDialogDetailedView,
    tr('Menu contextuel'): QStyle.StandardPixmap.SP_FileDialogContentsView,
    tr('Aperçus et lecture'): QStyle.StandardPixmap.SP_MediaPlay,
    tr('Applications externes'): QStyle.StandardPixmap.SP_ComputerIcon,
}


class KPageStyleCategoryDelegate(QStyledItemDelegate):
    """The KPageListViewDelegate layout used by Dolphin's KPageDialog."""

    @staticmethod
    def text_layout(text, font, max_width):
        layout = QTextLayout(text, font)
        layout.setTextOption(QTextOption(Qt.AlignmentFlag.AlignHCenter))
        layout.beginLayout()
        height = 0.0
        natural_width = 0.0
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max_width)
            line.setPosition(QPointF(0, height))
            height += line.height()
            natural_width = max(natural_width, line.naturalTextWidth())
        layout.endLayout()
        return layout, natural_width

    def sizeHint(self, option, index):
        icon_width = option.widget.style().pixelMetric(QStyle.PixelMetric.PM_IconViewIconSize, option, option.widget)
        metrics = option.fontMetrics
        layout, width = self.text_layout(str(index.data(Qt.ItemDataRole.DisplayRole) or ''),
                                         option.font, max(3 * icon_width, 8 * metrics.height()))
        return QSize(max(int(width + 0.5), icon_width) + metrics.height(),
                     icon_width + int(layout.boundingRect().height()) + 10)

    def paint(self, painter, option, index):
        if not index.isValid():
            return
        widget = option.widget
        style = widget.style()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        active = bool(option.state & QStyle.StateFlag.State_Active)
        icon_mode = QIcon.Mode.Selected if selected and active else QIcon.Mode.Normal
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_IconViewIconSize, option, widget)
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        pixmap = icon.pixmap(icon_size, icon_size, icon_mode) if isinstance(icon, QIcon) else None
        icon_width = pixmap.width() / pixmap.devicePixelRatio() if pixmap and not pixmap.isNull() else icon_size
        icon_height = pixmap.height() / pixmap.devicePixelRatio() if pixmap and not pixmap.isNull() else icon_size
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or '')
        max_width = max(3 * int(icon_width), 8 * option.fontMetrics.height())
        layout, _ = self.text_layout(text, option.font, max_width)
        group = (QPalette.ColorGroup.Disabled if not option.state & QStyle.StateFlag.State_Enabled
                 else QPalette.ColorGroup.Active if active else QPalette.ColorGroup.Inactive)
        foreground = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        painter.save()
        try:
            background = QStyleOptionViewItem(option)
            background.showDecorationSelected = True
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, background, painter, widget)
            painter.setPen(option.palette.color(group, foreground))
            if pixmap and not pixmap.isNull():
                painter.drawPixmap(round(option.rect.center().x() - icon_width / 2),
                                   option.rect.y() + 5, pixmap)
            if text:
                layout.draw(painter, QPointF(option.rect.x() + (option.rect.width() - max_width) / 2,
                                             option.rect.y() + icon_height + 7))
            if option.state & QStyle.StateFlag.State_HasFocus:
                focus = QStyleOptionFocusRect()
                focus.initFrom(widget)
                focus.rect = option.rect
                focus.state = option.state | QStyle.StateFlag.State_KeyboardFocusChange
                focus.backgroundColor = option.palette.color(
                    group, QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.Window)
                style.drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, focus, painter, widget)
        finally:
            painter.restore()


class KPageStyleCategories(QListWidget):
    """Keep the KF6 KPageListView width rule, independent of dialog resizing."""

    def adjustNavigationWidth(self):
        self.setFixedWidth(self.sizeHintForColumn(0) + self.verticalScrollBar().sizeHint().width() + 5)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            QTimer.singleShot(0, self, self.adjustNavigationWidth)

class ConfigurationDialog(QDialog):

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(tr('Configurer Mirivue'))
        self.resize(900, 670)
        self.setMinimumSize(650, 500)
        self.setSizeGripEnabled(True)
        outer = QVBoxLayout(self)
        body = QGridLayout()
        outer.addLayout(body, 1)
        self.categories = KPageStyleCategories()
        self.categories.setObjectName('configurationCategories')
        # KF6 KPageListView uses a bold font for every category, regardless of
        # whether it is selected. The selection changes the palette only.
        navigation_font = self.categories.font()
        navigation_font.setBold(True)
        self.categories.setFont(navigation_font)
        self.categories.setItemDelegate(KPageStyleCategoryDelegate(self.categories))
        self.categories.setMovement(QListWidget.Movement.Static)
        self.categories.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.categories.setWordWrap(True)
        native_icon_size = self.style().pixelMetric(QStyle.PixelMetric.PM_IconViewIconSize, None, self.categories)
        self.categories.setIconSize(QSize(native_icon_size, native_icon_size))
        self.categories.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.categories.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pages = QStackedWidget()
        self.category_search = QLineEdit()
        self.category_search.setObjectName('configurationSearch')
        self.category_search.setPlaceholderText(tr('Rechercher…'))
        self.category_search.setClearButtonEnabled(True)
        self.category_search.addAction(QIcon.fromTheme('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400)
        self.category_search.textChanged.connect(self.search_timer.start)
        self.categories.currentRowChanged.connect(lambda _row: self.search_timer.start() if self.category_search.text() else None)
        self.search_timer.timeout.connect(self.filter_categories)
        body.addWidget(self.category_search, 0, 0)
        self.page_title = QLabel()
        body.addWidget(self.page_title, 0, 1)
        self.search_results = QLabel()
        self.search_results.setWordWrap(True)
        self.search_results.hide()
        self.no_results = QLabel(tr('Aucun réglage trouvé. Essayez un autre mot.'))
        self.no_results.setWordWrap(True)
        self.no_results.hide()
        body.addWidget(self.categories, 1, 0, 2, 1)
        body.addWidget(self.search_results, 1, 1)
        body.addWidget(self.pages, 2, 1)
        body.addWidget(self.no_results, 2, 1)
        body.setColumnStretch(1, 1)
        self._general_page()
        self._columns_page()
        self._previews_page()
        self._applications_page()
        self._context_menu_page()
        self.categories.adjustNavigationWidth()
        self.categories.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.categories.currentRowChanged.connect(self.update_page_title)
        self.categories.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Apply)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr('OK'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText(tr('Appliquer'))
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.accepted.connect(self.accept_if_applied)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def update_page_title(self, row):
        item = self.categories.item(row) if row >= 0 else None
        self.page_title.setText(item.text() if item else '')

    def filter_categories(self):
        needle = self.category_search.text().strip().casefold()
        first = None
        for row in range(self.categories.count()):
            item = self.categories.item(row)
            page = self.pages.widget(row)
            words = [item.text()]
            words.extend(label.text() for label in page.findChildren(QLabel))
            words.extend(group.title() for group in page.findChildren(QGroupBox))
            words.extend(button.text() for button in page.findChildren(QAbstractButton))
            for combo in page.findChildren(QComboBox):
                words.extend(combo.itemText(i) for i in range(combo.count()))
            if page.isAncestorOf(self.context_menu_page):
                from .context_menu_settings import ENTRIES
                words.extend(tr(entry[1]) for entry in ENTRIES)
                words.extend(self.context_menu_page.searchable_labels())
            match = not needle or any(needle in word.casefold() for word in words)
            self.categories.setRowHidden(row, not match)
            if match and first is None:
                first = row
        current = self.categories.currentRow()
        self.pages.setVisible(first is not None)
        self.no_results.setVisible(first is None)
        self.search_results.setVisible(bool(needle) and first is not None)
        if first is not None and (current < 0 or self.categories.isRowHidden(current)):
            self.categories.setCurrentRow(first)
        if first is None:
            self.page_title.setText(tr('Résultats de recherche'))
        else:
            self.update_page_title(self.categories.currentRow())
            page = self.pages.currentWidget()
            matches = [widget for widget in page.findChildren(QWidget)
                       if needle and ((isinstance(widget, (QLabel, QAbstractButton)) and needle in widget.text().casefold())
                                      or (isinstance(widget, QGroupBox) and needle in widget.title().casefold()))]
            self.search_results.setText(tr('Correspondances : ') + ' · '.join(dict.fromkeys(w.title() if isinstance(w, QGroupBox) else w.text() for w in matches)))
            scroll = page.findChild(QScrollArea)
            if scroll and matches:
                scroll.ensureWidgetVisible(matches[0])

    def add_page(self, title):
        item = QListWidgetItem(title)
        for icon_name in PAGE_ICONS.get(title, ()):
            icon = QIcon.fromTheme(icon_name)
            if not icon.isNull():
                item.setIcon(icon)
                break
        if item.icon().isNull():
            item.setIcon(self.style().standardIcon(
                PAGE_ICON_FALLBACKS.get(title, QStyle.StandardPixmap.SP_FileIcon)))
        self.categories.addItem(item)
        page = QWidget()
        page.setLayout(QVBoxLayout())
        page.layout().setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        contents = QWidget()
        contents.setLayout(QVBoxLayout())
        scroll.setWidget(contents)
        page.layout().addWidget(scroll)
        self.pages.addWidget(page)
        return contents.layout()

    @staticmethod
    def group(parent_layout, title):
        group = QGroupBox(title)
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(group)
        parent_layout.addWidget(group)
        return layout

    @staticmethod
    def note(text):
        tr('An explanatory label that never dictates the dialog width.')
        label = QLabel(text)
        label.setWordWrap(True)
        label.setSizePolicy(label.sizePolicy().horizontalPolicy(), label.sizePolicy().verticalPolicy())
        return label

    def _context_menu_page(self):
        from .context_menu_settings import ContextMenuPage
        layout = self.add_page(tr('Menu contextuel'))
        self.context_menu_page = ContextMenuPage(self.window, self)
        layout.addWidget(self.context_menu_page, 1)

    def _general_page(self):
        page_layout = self.add_page(tr('Général'))
        layout = startup_layout = self.group(page_layout, tr('Démarrage'))
        form = QFormLayout()
        layout.addLayout(form)
        self.startup = QComboBox()
        self.startup.addItem(tr('Dossiers et onglets de la session précédente'), 'session')
        self.startup.addItem(tr('Dernier dossier ouvert'), tr('last'))
        self.startup.addItem(tr('Dossier choisi'), tr('path'))
        saved_location = self.window.settings.value('startup/location', tr('home'))
        self.startup.setCurrentIndex(max(0, self.startup.findData(saved_location if saved_location in ('last', 'session') else tr('path'))))
        form.addRow(tr('Au démarrage :'), self.startup)
        self.startup_path = QComboBox()
        self.startup_path.addItem(tr('Dossier personnel'), str(Path.home()))
        for place in getattr(self.window, tr('current_place_entries'), lambda: [])():
            url = str(place.get('url', ''))
            if url.startswith('file:'):
                from PySide6.QtCore import QUrl
                path = QUrl(url).toLocalFile()
                # These entries have already been supplied by the KDE Places
                # model (or validated by the local fallback). Avoid blocking
                # the dialog on a synchronous stat of a removable or remote
                # volume each time configuration is opened.
                if path and self.startup_path.findData(path) < 0:
                    self.startup_path.addItem(str(place.get('name') or Path(path).name), path)
        saved = str(self.window.settings.value('startup/path', ''))
        if saved and (self.startup_path.findData(saved) < 0):
            self.startup_path.addItem(Path(saved).name or saved, saved)
        if self.startup_path.findData(saved) >= 0:
            self.startup_path.setCurrentIndex(self.startup_path.findData(saved))
        choose_startup = QPushButton(tr('Choisir un autre dossier…'))

        def choose_folder():
            initial = self.startup_path.currentData() or str(Path.home())
            folder = QFileDialog.getExistingDirectory(self, tr('Choisir le dossier de démarrage'), initial)
            if not folder:
                return
            index = self.startup_path.findData(folder)
            if index < 0:
                self.startup_path.addItem(Path(folder).name or folder, folder)
                index = self.startup_path.count() - 1
            self.startup_path.setCurrentIndex(index)
            self.startup.setCurrentIndex(self.startup.findData(tr('path')))
        choose_startup.clicked.connect(choose_folder)
        form.addRow(tr('Dossier de démarrage :'), self.startup_path)
        choose_row = QHBoxLayout()
        choose_row.addStretch()
        choose_row.addWidget(choose_startup)
        form.addRow('', choose_row)

        def update_startup_path():
            enabled = self.startup.currentData() == tr('path')
            self.startup_path.setEnabled(enabled)
            choose_startup.setEnabled(enabled)
        self.startup.currentIndexChanged.connect(update_startup_path)
        update_startup_path()
        self.start_split = QCheckBox(tr('Toujours démarrer en mode scindé'))
        self.start_split.setChecked(self.window.settings.value('startup/split', False, type=bool))
        layout.addWidget(self.start_split)
        self.single_instance = QCheckBox(tr('Ouvrir les nouveaux dossiers en onglets'))
        self.single_instance.setChecked(not self.window.settings.value('startup/allow_multiple_instances', False, type=bool))
        self.single_instance.setToolTip(tr('Les dossiers demandés par une autre application s’ouvrent dans un nouvel onglet. Une nouvelle fenêtre reste possible sur demande.'))
        layout.addWidget(self.single_instance)
        layout = display_layout = self.group(page_layout, tr('Affichage'))
        date_form = QFormLayout()
        example_ns = time.time_ns() - 30 * 60 * 1_000_000_000
        self.date_relative = QRadioButton(tr('Relative (Par exemple « %s »)') % modification_text(example_ns, mode='informal'))
        self.date_absolute = QRadioButton(tr('Absolue (Par exemple « %s »)') % modification_text(example_ns, mode='locale'))
        self.date_style_group = QButtonGroup(self)
        self.date_style_group.addButton(self.date_relative)
        self.date_style_group.addButton(self.date_absolute)
        self.date_relative.setChecked(str(self.window.settings.value('view/date-format', 'locale')) == 'informal')
        self.date_absolute.setChecked(not self.date_relative.isChecked())
        date_form.addRow(tr('Style de date :'), self.date_relative)
        date_form.addRow('', self.date_absolute)
        layout.addLayout(date_form)
        layout = closing_layout = self.group(page_layout, tr('Fermeture'))
        self.close_to_tray = QCheckBox(tr('Réduire dans la zone de notification à la fermeture'))
        self.close_to_tray.setChecked(self.window.settings.value('window/close-to-tray', False, type=bool))
        self.close_to_tray.setToolTip(tr('Si cette option est désactivée, la croix ferme Mirivue. Ctrl+Q et Fichier → Quitter ferment toujours Mirivue.'))
        layout.addWidget(self.close_to_tray)
        layout = self.group(page_layout, tr('Navigation'))
        self.empty_double_click_up = QCheckBox(tr('Double-cliquer dans un espace vide pour remonter au dossier parent'))
        self.empty_double_click_up.setChecked(self.window.settings.value('navigation/empty-double-click-up', False, type=bool))
        layout.addWidget(self.empty_double_click_up)
        self.confirm_close_tabs = QCheckBox(tr('Confirmer la fermeture de plusieurs onglets'))
        self.confirm_close_tabs.setChecked(self.window.settings.value('window/confirm-close-multiple-tabs', True, type=bool))
        self.confirm_close_tabs.setToolTip(tr('La confirmation propose de fermer la fenêtre ou seulement l’onglet courant. Elle n’est pas affichée si la restauration de session est activée.'))
        closing_layout.addWidget(self.confirm_close_tabs)
        self.hide_hidden_on_startup = QCheckBox(tr('Toujours masquer les éléments cachés au démarrage'))
        self.hide_hidden_on_startup.setChecked(self.window.settings.value('view/hide-hidden-on-startup', False, type=bool))
        self.hide_hidden_on_startup.setToolTip(tr('Au lancement, les éléments cachés sont masqués, même s’ils étaient visibles lorsque Mirivue a été fermé.'))
        startup_layout.addWidget(self.hide_hidden_on_startup)
        layout = display_layout
        self.remember_folder_sort = QCheckBox(tr('Mémoriser le style d’affichage de chaque dossier'))
        self.remember_folder_sort.setChecked(self.window.settings.value('view/remember-per-folder', self.window.settings.value('sorting/remember-per-folder', False, type=bool), type=bool))
        self.remember_folder_sort.setToolTip(tr('Désactivé : partager le mode d’affichage, le tri, les miniatures et les éléments cachés entre les dossiers. Activé : mémoriser les choix de chaque dossier. Les profils médias restent disponibles.'))
        layout.addWidget(self.remember_folder_sort)
        self.sort_mode = QComboBox()
        for label, mode in (('Naturel', 0), ('Alphabétique, sensible à la casse', 1), ('Alphabétique, insensible à la casse', 2)):
            self.sort_mode.addItem(tr(label), mode)
        self.sort_mode.setCurrentIndex(max(0, self.sort_mode.findData(self.window.settings.value('sorting/mode', 0, type=int))))
        sorting_form = QFormLayout()
        sorting_form.addRow(tr('Ordre de tri :'), self.sort_mode)
        layout.addLayout(sorting_form)
        self.hidden_last = QCheckBox(tr('Placer les fichiers et dossiers cachés en dernier'))
        self.hidden_last.setChecked(self.window.settings.value('sorting/hidden-last', False, type=bool))
        layout.addWidget(self.hidden_last)
        layout = self.group(page_layout, tr('Onglets'))
        self.tabs_after_last = QCheckBox(tr('Ouvrir les nouveaux onglets à la fin'))
        self.tabs_after_last.setChecked(self.window.settings.value('tabs/open-after-last', False, type=bool))
        self.tabs_after_last.setToolTip(tr('Sinon, les dossiers s’ouvrent après l’onglet courant. Ctrl+T ajoute toujours un onglet à la fin.'))
        layout.addWidget(self.tabs_after_last)
        self.always_show_tabs = QCheckBox(tr('Toujours afficher la barre d’onglets'))
        self.always_show_tabs.setChecked(self.window.settings.value('tabs/always-show-bar', False, type=bool))
        layout.addWidget(self.always_show_tabs)
        self.close_buttons_on_tabs = QCheckBox(tr('Afficher les boutons de fermeture sur les onglets'))
        self.close_buttons_on_tabs.setChecked(self.window.settings.value('tabs/show-close-buttons', True, type=bool))
        layout.addWidget(self.close_buttons_on_tabs)
        layout = display_layout
        self.folders_first = QCheckBox(tr('Trier les dossiers avant les fichiers'))
        self.folders_first.setChecked(self.window.settings.value('sorting/folders-first', True, type=bool))
        self.folders_first.setToolTip(tr('Les dossiers restent en tête, même lorsque le tri de la colonne est décroissant.'))
        layout.addWidget(self.folders_first)
        folder_size_form = QFormLayout()
        self.folder_size_display = QComboBox()
        self.folder_size_display.addItem(tr('Nombre d’éléments'), 'count')
        self.folder_size_display.addItem(tr('Taille totale'), 'size')
        saved_folder_size_display = str(self.window.settings.value('view/folder-size-display', 'count'))
        self.folder_size_display.setCurrentIndex(max(0, self.folder_size_display.findData(saved_folder_size_display)))
        self.folder_size_display.setToolTip(tr('Le nombre concerne les éléments directement contenus dans le dossier. La taille totale inclut les sous-dossiers et demande un calcul récursif.'))
        folder_size_form.addRow(tr('Colonne Taille pour les dossiers :'), self.folder_size_display)
        layout.addLayout(folder_size_form)
        layout = self.group(page_layout, tr('Confidentialité'))
        self.keep_recent_media = QCheckBox(tr('Mémoriser les fichiers récemment ouverts'))
        self.keep_recent_media.setChecked(self.window.settings.value('privacy/remember-recent-media', True, type=bool))
        self.keep_recent_media.setToolTip(tr('Lorsque cette option est désactivée, la liste Fichiers récents est effacée et retirée du menu Fichier.'))
        self.clear_recent_media = QPushButton(tr('Effacer la liste des fichiers récents'))
        self.clear_recent_media.setToolTip(tr('Supprime uniquement la liste locale des fichiers récemment ouverts. Les fichiers ne sont pas modifiés.'))
        self.clear_recent_media.clicked.connect(self.clear_recent_media_list)
        self.keep_recent_media.toggled.connect(self.update_recent_media_button)
        self.update_recent_media_button()
        layout.addWidget(self.keep_recent_media)
        layout.addWidget(self.clear_recent_media)
        page_layout.addStretch()

    def update_recent_media_button(self, *_):
        self.clear_recent_media.setEnabled(self.keep_recent_media.isChecked() and bool(self.window.recent_items))

    def clear_recent_media_list(self):
        self.window.clear_recents()
        self.update_recent_media_button()

    def _columns_page(self):
        layout = self.add_page(tr('Configurations de colonnes'))
        row = QHBoxLayout()
        row.addWidget(QLabel(tr('Configuration prédéfinie :')))
        row.addWidget(context_help_button(self, tr('Modifiez les configurations prédéfinies de colonnes. Appliquer ou OK les enregistre sans changer la vue actuelle. Choisissez ensuite une configuration dans Affichage → Configurations de colonnes pour l’appliquer au dossier actif.')))
        layout.addWidget(self.note(tr('Ces réglages définissent les configurations proposées dans Affichage → Configurations de colonnes. Ils ne changent pas la vue actuelle.')))
        self.profile = QComboBox()
        self.profile.addItems(self.window.profile_names())
        row.addWidget(self.profile, 1)
        self.reset_profile = QPushButton(tr('Rétablir cette configuration'))
        row.addWidget(self.reset_profile)
        layout.addLayout(row)
        self.profile_columns = QListWidget()
        layout.addWidget(self.profile_columns, 1)
        self._edited_profiles = {name: set(cols) for name, cols in self.window.profile_definitions().items()}
        self._loading_profile = False
        self.profile.currentTextChanged.connect(self.load_profile)
        self.profile_columns.itemChanged.connect(self.remember_profile)
        self.reset_profile.clicked.connect(self.reset_current_profile)
        self.load_profile(self.profile.currentText())

    def load_profile(self, name):
        self._loading_profile = True
        self.profile_columns.clear()
        selected = self._edited_profiles.get(name, {0})
        for column, title in enumerate(HEADERS):
            if column in (10, 12, 13, 15, 16, 36):
                continue
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, column)
            if column == 0:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            else:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if column == 0 or column in selected else Qt.CheckState.Unchecked)
            self.profile_columns.addItem(item)
        self._loading_profile = False

    def remember_profile(self, *_):
        if self._loading_profile:
            return
        checked = {self.profile_columns.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.profile_columns.count()) if self.profile_columns.item(i).checkState() == Qt.CheckState.Checked}
        self._edited_profiles[self.profile.currentText()] = checked | {0}

    def reset_current_profile(self):
        name = self.profile.currentText()
        self._edited_profiles[name] = set(self.window.default_profile(name))
        self.load_profile(name)

    def _previews_page(self):
        page_layout = self.add_page(tr('Aperçus et lecture'))
        layout = self.group(page_layout, tr('Miniatures'))
        self.previews = QCheckBox(tr('Afficher les miniatures'))
        self.previews.setChecked(self.window.preview_action.isChecked())
        self.previews.setToolTip(tr('Affiche les miniatures dans les vues Icônes, Compacte et Détaillée du panneau actif. Avec un style commun, ce choix s’applique aux dossiers ordinaires. Si la mémorisation par dossier est activée, il est enregistré pour le dossier actif. Les emplacements spéciaux peuvent conserver leur propre réglage. Cette option ne concerne pas le panneau d’aperçu.'))
        self.preview_panel_startup = QCheckBox(tr('Afficher automatiquement le panneau d’aperçu au démarrage'))
        self.preview_panel_startup.setChecked(self.window.settings.value('media/start-preview-panel', self.window.preview_dock.isVisible(), type=bool))
        self.preview_panel_startup.setToolTip(tr('Le panneau restera utilisable à la demande pendant une session, même si cette option est désactivée.'))
        self.preview_first_item = QCheckBox(tr('Afficher le premier fichier du dossier lorsqu’aucun élément n’est sélectionné'))
        self.preview_first_item.setChecked(self.window.settings.value('media/preview-first-item', False, type=bool))
        self.preview_first_item.setToolTip(tr('Le fichier est seulement affiché dans le panneau d’aperçu : il n’est pas sélectionné dans la liste.'))
        layout.addWidget(self.previews)
        layout = self.group(page_layout, tr('Panneau d’aperçu'))
        layout.addWidget(self.preview_panel_startup)
        layout.addWidget(self.preview_first_item)
        layout = self.group(page_layout, tr('Lecture'))
        self.seek_step = QSpinBox()
        self.seek_step.setRange(1, 120)
        self.seek_step.setSuffix(tr(' secondes'))
        self.seek_step.setValue(self.window.settings.value('media/seek-step-seconds', 10, type=int))
        self.volume_step = QSpinBox()
        self.volume_step.setRange(1, 25)
        self.volume_step.setSuffix(tr(' %'))
        self.volume_step.setValue(self.window.settings.value('media/volume-step-percent', 5, type=int))
        form = QFormLayout()
        form.addRow(tr('Avancer ou reculer de :'), self.seek_step)
        form.addRow(tr('Variation du volume par cran :'), self.volume_step)
        layout.addLayout(form)
        preview_help = QHBoxLayout()
        preview_help.addStretch(1)
        preview_help.addWidget(context_help_button(self, tr('Les aperçus sont calculés en arrière-plan et réutilisés depuis le cache local.')))
        page_layout.addLayout(preview_help)
        page_layout.addStretch()

    def accept_if_applied(self):
        if self.apply():
            self.accept()

    def _applications_page(self):
        layout = self.add_page(tr('Applications externes'))
        form = QFormLayout()
        layout.addLayout(form)
        self.renamer_tool = QComboBox()
        self.renamer_tool.addItem(tr('Outil intégré'), 'integrated')
        self.renamer_tool.addItem(tr('Outil externe'), 'external')
        chosen_tool = str(self.window.settings.value('renamer/tool', 'integrated'))
        self.renamer_tool.setCurrentIndex(max(0, self.renamer_tool.findData(chosen_tool)))
        form.addRow(tr('Outil utilisé par F2 pour plusieurs fichiers :'), self.renamer_tool)
        self.renamer = QLineEdit(self.window.settings.value('renamer/program', ''))
        self.renamer_args = QLineEdit(self.window.settings.value('renamer/arguments', tr('-B')))
        self.renamer_args.setToolTip(tr('La sélection est ajoutée automatiquement à la commande.'))
        form.addRow(tr('Outil de renommage externe :'), self.renamer)
        form.addRow(tr('Arguments du logiciel :'), self.renamer_args)
        verify = QPushButton(tr('Vérifier les composants nécessaires…'))
        verify.clicked.connect(lambda: self.window.ensure_components([tr('mediainfo'), tr('ffmpeg'), tr('ffprobe'), tr('mkvpropedit'), tr('mkvextract')], report=True))
        layout.addWidget(verify)
        layout.addStretch()

    def apply(self):
        if not self.context_menu_page.apply():
            return False
        w = self.window
        s = w.settings
        s.setValue(tr('startup/location'), self.startup.currentData())
        if self.startup.currentData() == tr('path') and self.startup_path.currentData():
            s.setValue(tr('startup/path'), self.startup_path.currentData())
        w.startup_split_action.setChecked(self.start_split.isChecked())
        s.setValue(tr('startup/allow_multiple_instances'), not self.single_instance.isChecked())
        s.setValue(tr('window/close-to-tray'), self.close_to_tray.isChecked())
        s.setValue('navigation/empty-double-click-up', self.empty_double_click_up.isChecked())
        s.setValue('window/confirm-close-multiple-tabs', self.confirm_close_tabs.isChecked())
        s.setValue(tr('view/hide-hidden-on-startup'), self.hide_hidden_on_startup.isChecked())
        remember_sort = self.remember_folder_sort.isChecked()
        if remember_sort != s.value('view/remember-per-folder', s.value('sorting/remember-per-folder', False, type=bool), type=bool):
            header = w.table.horizontalHeader()
            s.setValue('sorting/common-sort', [header.sortIndicatorSection(), header.sortIndicatorOrder().value])
            s.setValue('sorting/remember-per-folder', remember_sort)
            s.setValue('view/remember-per-folder', remember_sort)
            if w.folder:
                w.restore_folder_view(w.folder)
        w.set_sorting_options(self.sort_mode.currentData(), self.hidden_last.isChecked())
        s.setValue('tabs/open-after-last', self.tabs_after_last.isChecked())
        s.setValue('tabs/always-show-bar', self.always_show_tabs.isChecked())
        s.setValue('tabs/show-close-buttons', self.close_buttons_on_tabs.isChecked())
        w.apply_tab_bar_settings()
        w.set_folders_first(self.folders_first.isChecked(), all_panes=True)
        w.set_folder_size_display(self.folder_size_display.currentData())
        w.set_date_format('informal' if self.date_relative.isChecked() else 'locale')
        w.set_recent_media_enabled(self.keep_recent_media.isChecked())
        self.update_recent_media_button()
        # The translated interface is rebuilt on the next application launch.
        s.sync()
        w.set_theme(tr('auto'))
        w.save_profile_definitions(self._edited_profiles)
        w.preview_action.setChecked(self.previews.isChecked())
        s.setValue(tr('media/start-preview-panel'), self.preview_panel_startup.isChecked())
        s.setValue(tr('media/preview-first-item'), self.preview_first_item.isChecked())
        w.schedule_media_preview()
        s.setValue(tr('media/seek-step-seconds'), self.seek_step.value())
        s.setValue(tr('media/volume-step-percent'), self.volume_step.value())
        s.remove(tr('media/hide-preview-text-playing'))
        s.setValue(tr('renamer/program'), self.renamer.text().strip())
        s.setValue(tr('renamer/arguments'), self.renamer_args.text())
        s.setValue(tr('renamer/tool'), self.renamer_tool.currentData())
        s.sync()
        return True


def ShortcutConfigurationDialog(window):
    """Return the real KDE dialog; kept as the existing Python entry point."""
    from .native_shortcuts import create_dialog
    return create_dialog(window)

def show_configuration(window):
    dialog = getattr(window, '_configuration_dialog', None)
    if dialog is None:
        dialog = ConfigurationDialog(window)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window._configuration_dialog = dialog
        dialog.destroyed.connect(lambda: setattr(window, '_configuration_dialog', None))
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def show_shortcut_configuration(window):
    dialog = getattr(window, '_shortcut_configuration_dialog', None)
    if dialog is None:
        try:
            dialog = ShortcutConfigurationDialog(window)
        except (OSError, AttributeError, RuntimeError) as error:
            QMessageBox.warning(window, tr('Composants KDE indisponibles'), str(error))
            return
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window._shortcut_configuration_dialog = dialog
        dialog.destroyed.connect(lambda: setattr(window, '_shortcut_configuration_dialog', None))
    dialog.show_native()
    dialog.raise_()
    dialog.activateWindow()
