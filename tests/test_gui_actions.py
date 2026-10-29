import os
import tempfile
import unittest


os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
_CONFIG = tempfile.TemporaryDirectory()
_STATE = tempfile.TemporaryDirectory()
os.environ['XDG_CONFIG_HOME'] = _CONFIG.name
os.environ['XDG_STATE_HOME'] = _STATE.name

try:
    from PySide6.QtWidgets import QApplication, QToolButton, QListWidget, QFrame
    from PySide6.QtGui import QPalette
    from PySide6.QtCore import Qt, QTimer
    from mirivue.app import Window
except ImportError:
    QApplication = Window = None


@unittest.skipIf(QApplication is None, 'PySide6 absent de cet environnement')
class TestGuiActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _CONFIG
        cls.state = _STATE
        cls.application = QApplication.instance() or QApplication(['Mirivue-tests'])
        cls.window = Window()

    @classmethod
    def tearDownClass(cls):
        cls.window.quit_requested = True
        cls.window.closing = True
        cls.window.close()
        cls.application.processEvents()
        cls.config.cleanup()
        cls.state.cleanup()

    def test_main_menu_contract_is_real_qt_state(self):
        self.assertEqual(
            list(self.window.main_menus),
            ['file', 'edit', 'view', 'go', 'tools', 'organize', 'operations', 'settings', 'help'],
        )
        self.assertTrue(self.window.details_view_action.isCheckable())
        self.assertTrue(self.window.icons_view_action.isCheckable())
        self.assertTrue(self.window.compact_view_action.isCheckable())
        self.assertIn(self.window.new_tab_action, self.window.main_menus['file'].actions())
        self.assertIn(self.window.close_tab_action, self.window.main_menus['file'].actions())
        self.assertIn(self.window.copy_folder_name_action, self.window.main_menus['edit'].actions())
        self.assertNotEqual(self.window.details_view_action.isChecked(), self.window.icons_view_action.isChecked())

    def test_header_groups_share_actions_and_keep_profiles(self):
        window = self.window
        menu = window.build_header_menu(window.bound_pane.table.horizontalHeader())
        groups = {action.text(): action.menu() for action in menu.actions() if action.menu()}
        for label in ('Document', 'Image', 'Audio', 'Vidéo', 'Autre', 'Informations communes', 'Configurations de colonnes'):
            self.assertIn(label, groups)
        self.assertGreater(len(groups['Configurations de colonnes'].actions()), 0)
        self.assertIn(window.column_actions[2], groups['Informations communes'].actions())
        self.assertIn(window.column_actions[2], groups['Informations communes'].actions())
        self.assertIn(window.column_actions[3], groups['Informations communes'].actions())
        self.assertIn(window.column_actions[3], groups['Informations communes'].actions())
        self.assertTrue(window.bound_pane.table.isColumnHidden(0) is False)
        self.assertTrue(any(action.text() == 'Largeurs de colonnes automatiques'
                            for action in menu.actions()))

    def test_toolbar_configuration_uses_the_native_editor_adapter(self):
        from unittest.mock import patch
        with patch('mirivue.toolbar_xml.edit') as native:
            self.window.customize_toolbar()
        native.assert_called_once_with(self.window)
        # Actual KDE reorder and Apply/Cancel are covered by
        # test_native_toolbar_editor with Valider's freshly compiled bridge.

    def test_compact_view_has_the_same_model_and_selection_as_other_views(self):
        self.window.change_view(2)
        self.assertIs(self.window.active_view(), self.window.compact)
        self.assertIs(self.window.compact.model(), self.window.icons.model())
        self.assertTrue(self.window.compact_view_action.isChecked())
        self.window.change_view(0)

    def test_compact_button_survives_toolbar_rebuild_and_legacy_order(self):
        from mirivue.desktop import TOOLBAR
        from mirivue import library

        compact = self.window.compact_button
        self.assertIn('compact_button', dict(TOOLBAR))
        old_order = [name for name, _ in TOOLBAR if name != 'compact_button']
        original = library.read(self.window.settings, 'toolbar', {})
        try:
            library.write(self.window.settings, 'toolbar', {'order': old_order, 'hidden': []})
            self.window.apply_toolbar()
            self.assertIn('compact_button', self.window.toolbar_state()[0])
            self.assertIsNotNone(self.window.right_toolbar_layout.indexOf(compact))
            self.assertGreaterEqual(self.window.right_toolbar_layout.indexOf(compact), 0)
            self.assertFalse(compact.isHidden())
            self.window.change_view(2)
            self.assertTrue(compact.isChecked())
            self.window.change_view(0)
        finally:
            library.write(self.window.settings, 'toolbar', original)
            self.window.apply_toolbar()

    def test_search_actions_open_and_close_the_unified_panel(self):
        self.window.search_action.trigger()
        self.application.processEvents()
        self.assertFalse(self.window.search_panel.isHidden())
        self.window.close_search_action.trigger()
        self.application.processEvents()
        self.assertTrue(self.window.search_panel.isHidden())

    def test_navigator_host_has_native_frame_context_without_an_extra_border(self):
        host = self.window.pane_path_container
        self.assertIsInstance(host, QFrame)
        self.assertEqual(host.frameShape(), QFrame.Shape.NoFrame)
        self.assertFalse(host.autoFillBackground())

    def test_split_views_follow_theme_active_and_inactive_palette(self):
        window = self.window
        window.show()
        window.set_split_view(True, navigate_new=False)
        self.application.processEvents()
        try:
            for active in window.panes:
                window.activate_pane(active)
                self.application.processEvents()
                colours = []
                for pane in window.panes:
                    self.assertTrue(pane.table.alternatingRowColors())
                    for view in (pane.table, pane.icons, pane.compact):
                        self.assertFalse(view.testAttribute(Qt.WidgetAttribute.WA_SetPalette))
                    graphics = pane.table._backend.widget.viewport()
                    colour = graphics.palette().color(graphics.backgroundRole())
                    self.assertEqual(colour.alpha(), 255 if pane is active else 150)
                    colours.append(colour.toRgb().rgb())
                self.assertEqual(colours[0], colours[1])
        finally:
            window.set_split_view(False, navigate_new=False)


if __name__ == '__main__':
    unittest.main()
