"""Exercise a real Qt window using isolated preferences and no user files."""

from .desktop import TOOLBAR


def _wait_native_contract(application, predicate, message, timeout_ms=2000):
    """Wait for the platform's reply; a persistent failure still fails the test."""
    import time
    from PySide6.QtTest import QTest
    deadline = time.monotonic() + timeout_ms / 1000
    while True:
        application.processEvents()
        if predicate():
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(message() if callable(message) else message)
        QTest.qWait(10)


def check_native_places(window, application):
    """Exercise the installed KF6 widgets on the active graphical desktop."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit, QStyle

    def check_path_positions():
        window.sync_path_toolbar_alignment()
        application.processEvents()
        tolerance = window.navigation_bar.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarItemSpacing) + 8
        for pane in window.panes:
            if pane.path_bar.isHidden():
                continue
            path_x = pane.path_bar.mapToGlobal(QPoint(0, 0)).x()
            view_x = pane.container.mapToGlobal(QPoint(0, 0)).x()
            if abs(path_x - view_x) > tolerance:
                raise RuntimeError(f'barre de chemin décalée du panneau : {path_x - view_x} px')

    import tempfile
    temporary = tempfile.TemporaryDirectory(prefix='mirivue-native-contract-')
    try:
        # Window() alone has no location. Enter must validate a real, disposable
        # path, not send an empty URL to KIO.
        window.prepare_startup_browsing(temporary.name)
        window.showNormal()
        _wait_native_contract(application,
                              lambda: window.windowHandle() is not None and window.windowHandle().isExposed(),
                              'la fenêtre de contrôle ne devient pas visible')
        if any(widget.styleSheet() for widget in (
                window, window.menuBar(), window.navigation_bar)):
            raise RuntimeError('le thème natif des menus ou de la barre est remplacé par une feuille de style')
        if window.native_places is None:
            raise RuntimeError('le panneau KFilePlacesView est absent dans cette session : '
                               + str(window.native_places_error or 'cause inconnue'))
        if window.native_places.widget.isHidden():
            raise RuntimeError('le panneau Emplacements natif est masqué')
        if window.navigation_bar.metaObject().className() != 'KToolBar':
            raise RuntimeError('la barre d’outils KToolBar native est absente')
        if any(action not in window.navigation_bar.actions() for action in (
                window.toolbar_left_action, window.toolbar_path_action,
                window.toolbar_right_action)):
            raise RuntimeError('les chemins et commandes ne sont pas intégrés à KToolBar')
        if any(p.native_navigator is None for p in window.panes):
            raise RuntimeError('une barre de chemin KUrlNavigator est absente')
        if any(p.native_navigator.is_places_selector_visible() for p in window.panes):
            raise RuntimeError('le sélecteur Emplacements est dupliqué lorsque le panneau est visible')
        if any(p.native_navigator.shows_hidden_folders() != p.hidden_state for p in window.panes):
            raise RuntimeError('les dossiers cachés du fil d’Ariane ne suivent pas la vue')
        if any(not p.native_navigator.has_background() for p in window.panes):
            raise RuntimeError('le cadre KDE du fil d’Ariane est désactivé')
        navigator = window.panes[0].native_navigator
        navigator.set_editable(True)
        application.processEvents()
        if not navigator.is_editable():
            raise RuntimeError('la saisie du chemin ne s’ouvre pas')
        # Wayland may deny window activation during an automated launch, so
        # QApplication.focusWidget() can be null even though the editor works.
        editor = next((line for line in navigator.widget.findChildren(QLineEdit)
                       if line.isVisible()), None)
        if editor is None:
            raise RuntimeError('l’éditeur du fil d’Ariane est absent')
        QTest.keyClick(editor, Qt.Key.Key_Return)
        application.processEvents()
        if navigator.is_editable():
            raise RuntimeError('Entrée ne revient pas aux boutons du fil d’Ariane')
        check_path_positions()
        starting_width = window.width()
        # Configure events from a window manager may arrive after processEvents.
        # There is no arbitrary 700 px floor: it prevented a small window from
        # shrinking even when its actual layout allowed it.
        window.resize(max(1, starting_width - 250), window.height())
        _wait_native_contract(application, lambda: window.width() < starting_width,
                              lambda: 'la fenêtre refuse de rétrécir avec sa barre de chemin visible '
                              f'(départ={starting_width}, actuelle={window.width()}, '
                              f'minimum={window.minimumWidth()}, '
                              f'minimum conseillé={window.minimumSizeHint().width()}, '
                              f'état={window.windowState()})')
        check_path_positions()
        window.resize(starting_width, window.height())
        _wait_native_contract(application, lambda: window.width() == starting_width,
                              'la fenêtre ne retrouve pas sa largeur initiale')
        check_path_positions()
        window.set_split_view(True, navigate_new=False)
        application.processEvents()
        check_path_positions()
        first, second = window.panes
        window.activate_pane(first)
        window.hidden.setChecked(not first.hidden_state)
        application.processEvents()
        if first.native_navigator.shows_hidden_folders() != first.hidden_state:
            raise RuntimeError('Ctrl+H ne met pas à jour le fil d’Ariane actif')
        if second.native_navigator.shows_hidden_folders() != second.hidden_state:
            raise RuntimeError('Ctrl+H a modifié le fil d’Ariane du panneau inactif')
        window.activate_pane(second)
        application.processEvents()
        if second.native_navigator.shows_hidden_folders() != second.hidden_state:
            raise RuntimeError('l’activation du second panneau perd son réglage des dossiers cachés')
        window.set_split_view(False, navigate_new=False)
        application.processEvents()
        check_path_positions()
        window.set_places_panel_visible(False)
        application.processEvents()
        if not all(p.native_navigator.is_places_selector_visible() for p in window.panes):
            raise RuntimeError('le sélecteur Emplacements manque lorsque le panneau est masqué')
        window.sync_path_toolbar_alignment()
        application.processEvents()
        def check_hidden_places_toolbar():
            group = window.left_toolbar_group
            if group.width() <= 0 or window.back.isHidden() or window.back.width() <= 0:
                raise RuntimeError('le bouton Précédent disparaît quand Emplacements est masqué')
            if group.width() > group.sizeHint().width() + 2:
                raise RuntimeError('un espace vide sépare les boutons du chemin quand Emplacements est masqué')
            path_x = window.panes[0].path_bar.mapToGlobal(QPoint(0, 0)).x()
            group_end = group.mapToGlobal(QPoint(group.width(), 0)).x()
            if abs(path_x - group_end) > 16:
                raise RuntimeError('le chemin ne commence pas après les boutons quand Emplacements est masqué')

        check_hidden_places_toolbar()
        window.set_split_view(True, navigate_new=False)
        application.processEvents()
        window.sync_path_toolbar_alignment()
        application.processEvents()
        check_hidden_places_toolbar()
        window.set_split_view(False, navigate_new=False)
        application.processEvents()
        window.set_places_panel_visible(True)
        application.processEvents()
        if any(p.native_navigator.is_places_selector_visible() for p in window.panes):
            raise RuntimeError('le sélecteur Emplacements reste visible après F9')
        window.sync_path_toolbar_alignment()
        application.processEvents()
        check_path_positions()
    finally:
        window.quit_requested = True
        window.closing = True
        window.close()
        application.processEvents()
        temporary.cleanup()


def check_window(window, application):
    import os
    import sys
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette
    from . import __version__
    from . import library

    def require(condition, message):
        if not condition:
            raise RuntimeError(message)

    def phase(label):
        print('Contrôle graphique : ' + label, file=sys.stderr, flush=True)

    phase('ouverture de la fenêtre')
    window.show()
    application.processEvents()
    validated = False
    try:
        phase('barre d’outils et modes de vue')
        require(window.toolbar_path_action in window.navigation_bar.actions(),
                'les barres de chemin ne sont pas une action de la barre d’outils')
        modes = (
            (1, 'icons_button', 'icons_view_action', window.icons),
            (2, 'compact_button', 'compact_view_action', window.compact),
            (0, 'details_button', 'details_view_action', window.table),
        )
        for mode, name, action_name, view in modes:
            button = getattr(window, name)
            require(window.left_toolbar_layout.indexOf(button) >= 0 or
                    window.right_toolbar_layout.indexOf(button) >= 0,
                    f'{name} absent de la barre d’outils')
            require(not button.icon().isNull(), f'{name} sans icône')
            require(not button.isHidden() or not window.view_mode_button.isHidden(),
                    f'{name} et son sélecteur groupé sont masqués')
            if button.isHidden():
                require(getattr(window, action_name) in window.view_mode_button.menu().actions(),
                        f'{name} absent du sélecteur groupé')
                getattr(window, action_name).trigger()
            else:
                button.click()
            application.processEvents()
            require(window.active_view() is view, f'{name} n’active pas sa vue')
            require(getattr(window, action_name).isChecked(),
                    f'{name} ne synchronise pas son menu')
        require(window.table._backend.query().get('engine') == 'KStandardItemListView',
                'le moteur de vues de Dolphin est absent')
        require(all(not pane.container.styleSheet() for pane in window.panes),
                'un panneau de fichiers impose encore une feuille de style')

        # An older toolbar layout must inherit newly added commands.
        previous = library.read(window.settings, 'toolbar', {})
        try:
            legacy_order = [name for name, _ in TOOLBAR if name != 'compact_button']
            library.write(window.settings, 'toolbar', {'order': legacy_order, 'hidden': []})
            window.apply_toolbar()
            require('compact_button' in window.toolbar_state()[0],
                    'la disposition ancienne perd la vue compacte')
            require(window.right_toolbar_layout.indexOf(window.compact_button) >= 0,
                    'la disposition ancienne ne place pas le bouton compact')
        finally:
            library.write(window.settings, 'toolbar', previous)
            window.apply_toolbar()

        phase('vue scindée')
        window.set_split_view(True, navigate_new=False)
        application.processEvents()
        require(window.split_enabled and len(window.panes) == 2,
                'la vue scindée ne crée pas deux panneaux')
        require(all(not pane.container.styleSheet() for pane in window.panes),
                'un panneau de la vue scindée impose encore une feuille de style')
        require(all(p.path_bar is not None for p in window.panes),
                'une barre de chemin manque en vue scindée')
        for active_pane in window.panes:
            window.activate_pane(active_pane)
            for pane in window.panes:
                require(pane.table.alternatingRowColors(),
                        'les lignes alternées sont désactivées dans un panneau')
                for view in (pane.table, pane.icons, pane.compact):
                    require(not view.testAttribute(Qt.WidgetAttribute.WA_SetPalette),
                            'une vue impose sa palette au moteur KDE')
                viewport = pane.table._backend.widget.viewport()
                background = viewport.palette().color(viewport.backgroundRole())
                require(background.alpha() == (255 if pane is active_pane else 150),
                        'le fond du panneau inactif ne suit pas Dolphin')
        window.set_split_view(False, navigate_new=False)
        application.processEvents()
        require(not window.split_enabled, 'la vue scindée ne se ferme pas')
        phase('recherche')
        window.search_action.trigger()
        application.processEvents()
        require(not window.search_panel.isHidden(), 'la recherche ne s’ouvre pas')
        window.close_search_action.trigger()
        application.processEvents()
        require(window.search_panel.isHidden(), 'la recherche ne se ferme pas')
        phase('configuration et icônes')
        from .configuration import ConfigurationDialog
        dialog = ConfigurationDialog(window)
        dialog.show()
        application.processEvents()
        try:
            navigation = dialog.categories
            expected_width = (navigation.sizeHintForColumn(0) +
                              navigation.verticalScrollBar().sizeHint().width() + 5)
            require(navigation.width() == expected_width,
                    'la largeur de navigation ne suit pas KPageListView')
            require(navigation.font().bold(),
                    'les libellés des catégories ne reprennent pas la graisse de KPageListView')
            category_text, _ = navigation.itemDelegate().text_layout(
                navigation.item(0).text(), navigation.font(), 180)
            require(bool(category_text.textOption().alignment() & Qt.AlignmentFlag.AlignHCenter),
                    'les libellés des catégories ne sont pas centrés sous les icônes')
            missing = [navigation.item(i).text() for i in range(navigation.count())
                       if navigation.item(i).icon().isNull()]
            require(not missing, 'icônes de rubriques absentes : ' + ', '.join(missing))
            require(navigation.count() == 5 and navigation.item(4).text() == 'Menu contextuel' and all(navigation.item(i).text() not in ('Fiabilité', 'Apparence et langue')
                                                     for i in range(navigation.count())),
                    'les rubriques de configuration ne correspondent pas à la version actuelle')
            require(not hasattr(dialog, 'monitor_external_changes'),
                    'le réglage d’actualisation ne doit plus apparaître')
            require(not hasattr(dialog, 'language'),
                    'le choix de langue inachevé ne doit plus apparaître dans la configuration')
            require(window.read_unloaded_metadata_action in window.main_menus['organize'].actions(),
                    'la lecture détaillée manque dans Métadonnées')
            dialog.category_search.setText('Colonnes')
            dialog.search_timer.stop()
            dialog.filter_categories()
            require(sum(not navigation.isRowHidden(i) for i in range(navigation.count())) == 1,
                    'la recherche ne filtre pas les rubriques')
            require(dialog.page_title.text() == 'Configurations de colonnes',
                    'la recherche ne sélectionne pas la rubrique trouvée')
            dialog.category_search.clear()
            dialog.search_timer.stop()
            dialog.filter_categories()
            require(all(not navigation.isRowHidden(i) for i in range(navigation.count())),
                    'les rubriques ne reviennent pas après la recherche')
            navigation.setCurrentRow(1)
            require(dialog.pages.currentIndex() == 1, 'la rubrique ne change pas de page')
        finally:
            dialog.reject()
        phase('fermeture avec configuration ouverte')
        window.show_configuration()
        application.processEvents()
        configuration = window._configuration_dialog
        require(configuration is not None and configuration.isVisible() and not configuration.isModal(),
                'la configuration bloque encore la fermeture de la fenêtre principale')
        window.show_configuration()
        require(window._configuration_dialog is configuration,
                'une seconde fenêtre de configuration a été ouverte')
        validated = True
    finally:
        phase('fermeture')
        window.quit_requested = True
        window.closing = True
        closed = window.close()
        phase(f'closeEvent terminé ; fermeture acceptée : {closed}')
        if not closed:
            raise RuntimeError('la fenêtre a refusé de fermer pendant le contrôle graphique')
        if not window.settings.value('window/geometry'):
            raise RuntimeError('la géométrie de la fenêtre n’a pas été enregistrée à la fermeture')
        if validated:
            # The offscreen contract has no QApplication event loop. After a
            # successful close, Qt/KF6 process teardown can remain stuck in
            # native workers or Python wrapper finalizers. This child process
            # has isolated settings and has completed every assertion. Avoid
            # confusing teardown of its fixture with an application failure.
            print(f'Mirivue {__version__}: interactions de l’interface vérifiées', flush=True)
            sys.stderr.flush()
            os._exit(0)
