"""User-facing command scope, settings, previews and shared rename workflow."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, QTimer, Qt, QItemSelectionModel
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QTableWidget, QPushButton, QGroupBox, QMessageBox
from mirivue.app import Window
from mirivue.configuration import ConfigurationDialog
from mirivue.metadata import basic_entry
from mirivue.renaming import batch_names
from mirivue import library


class TestErgonomicsGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        settings = QSettings(str(self.root/'settings.ini'), QSettings.Format.IniFormat)
        settings.setValue('media/start-preview-panel', False)
        with patch('mirivue.app.mirivue_settings', return_value=settings):
            self.window = Window()
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        self.window.quit_requested = True
        self.window.closing = True
        self.window.close()
        self.application.processEvents()
        self.temporary.cleanup()

    def choose(self, name='film.mkv', media='video'):
        path = self.root/name
        path.write_bytes(b'file for UI test')
        row = basic_entry(path)
        row.media_type = media
        row.media_tags = {'artist': 'Artiste', 'title': 'Titre'}
        self.window.model.add(row)
        index = self.window.proxy.index(0, 0)
        self.window.active_view().selectionModel().select(index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
        self.window.update_main_menu_states()
        return row

    def test_actions_with_no_selection_and_no_jobs_are_disabled(self):
        self.window.update_main_menu_states()
        for name in ('Couper', 'Copier', 'Dupliquer'):
            self.assertFalse(self.window.transfer_actions[name].isEnabled())
        for action in (self.window.metadata_action, self.window.properties_action,
                       self.window.clear_pending_action, self.window.stop_all_analyses_action):
            self.assertFalse(action.isEnabled())
        self.choose('document.txt', 'other')
        self.assertTrue(self.window.transfer_actions['Copier'].isEnabled())
        self.assertTrue(self.window.properties_action.isEnabled())
        self.assertFalse(self.window.metadata_action.isEnabled())
        self.assertFalse(self.window.metadata_rename_action.isEnabled())

    def test_menu_hierarchy_has_direct_task_groups(self):
        tools = [a.menu() for a in self.window.main_menus['tools'].actions() if a.menu()]
        self.assertEqual([m.title() for m in tools],
            ['Renommer et organiser', 'Métadonnées', 'Collections', 'Opérations'])
        self.assertIn(self.window.batch_rename_action, tools[0].actions())
        self.assertIn(self.window.metadata_action, tools[1].actions())

    def test_view_controls_describe_only_the_active_layout(self):
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            self.window.update_main_menu_states()
            self.assertEqual(self.window.columns_menu.menuAction().isVisible(), mode == 0)
            self.assertEqual(self.window.extra_info_menu.menuAction().isVisible(), mode != 0)
            self.assertEqual(self.window.media_profile_menu.menuAction().isVisible(), mode == 0)

    def test_new_window_command_uses_current_location(self):
        self.window.folder = self.root
        with patch.object(self.window, 'open_place_in_new_window') as launch:
            self.window.new_window_action.trigger()
            launch.assert_called_once_with(self.root)
        self.assertEqual(self.window.new_window_action.shortcut(), QKeySequence('Ctrl+N'))

    def test_default_toolbar_is_grouped_but_custom_toolbar_is_preserved(self):
        order, hidden, before = self.window.toolbar_state()
        self.assertEqual(order[:3], ['back', 'forward', 'up'])
        self.assertNotIn('view_mode_button', hidden)
        self.assertTrue({'details_button', 'icons_button', 'compact_button'} <= set(hidden))
        self.assertEqual(len(self.window.view_mode_button.menu().actions()), 3)
        old_order = [n for n in order if n != 'view_mode_button']
        library.write(self.window.settings, 'toolbar', {'order': old_order, 'hidden': ['up'], 'before_paths': ['back']})
        order, hidden, before = self.window.toolbar_state()
        self.assertEqual([n for n in order if n != 'view_mode_button'], old_order)
        self.assertEqual(set(hidden), {'up', 'view_mode_button'})
        self.assertEqual(before, {'back'})

    def test_preference_search_shows_no_results_and_recovers(self):
        dialog = ConfigurationDialog(self.window)
        dialog.show()
        self.addCleanup(dialog.close)
        dialog.category_search.setText('mot absent 98234')
        dialog.search_timer.stop()
        dialog.filter_categories()
        self.assertFalse(dialog.no_results.isHidden())
        self.assertTrue(dialog.pages.isHidden())
        dialog.category_search.setText('volume')
        dialog.search_timer.stop()
        dialog.filter_categories()
        self.assertFalse(dialog.pages.isHidden())
        self.assertIn('volume', dialog.search_results.text())
        dialog.category_search.clear()
        dialog.search_timer.stop()
        dialog.filter_categories()
        self.assertTrue(all(not dialog.categories.isRowHidden(i) for i in range(dialog.categories.count())))

    def test_configuration_groups_and_startup_only_preview_choice(self):
        dialog = ConfigurationDialog(self.window)
        self.addCleanup(dialog.close)
        groups = {g.title() for g in dialog.pages.widget(0).findChildren(QGroupBox)}
        self.assertEqual(groups, {'Démarrage', 'Affichage', 'Fermeture', 'Navigation', 'Onglets', 'Confidentialité'})
        self.assertFalse(hasattr(dialog, 'keep_play_history'))
        before = self.window.preview_dock.isHidden()
        dialog.preview_panel_startup.setChecked(before)
        self.assertTrue(dialog.apply())
        self.assertEqual(self.window.preview_dock.isHidden(), before)
        self.assertEqual(self.window.settings.value('media/start-preview-panel', type=bool), before)

    def test_external_renamer_name_and_advanced_renamer_are_distinct(self):
        self.choose()
        self.window.settings.setValue('renamer/tool', 'external')
        self.window.settings.setValue('renamer/program', '/usr/bin/krename')
        self.window.update_main_menu_states()
        self.assertEqual(self.window.external_renamer_action.text(), 'Renommer avec krename…')
        with patch.object(self.window, '_rename_rows') as integrated, patch.object(self.window, 'launch_renamer') as external:
            self.window.batch_rename_action.trigger()
            integrated.assert_called_once()
            external.assert_not_called()
            self.window.rename_names()
            external.assert_called_once()

    def test_metadata_rename_uses_live_preview_and_blocks_missing_fields(self):
        row = self.choose('musique.flac', 'audio')
        observed = []
        def exercise():
            dialog = self.application.activeModalWidget()
            try:
                rules = dialog.findChild(QComboBox, 'batch-rename-method')
                template = dialog.findChild(QLineEdit, 'batch-rename-primary')
                table = dialog.findChild(QTableWidget)
                rename = next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Renommer')
                self.assertEqual(rules.currentData(), 'metadata')
                self.assertEqual(table.item(0, 1).text(), 'Artiste - Titre.flac')
                self.assertTrue(rename.isEnabled())
                template.setText('{album}')
                self.assertFalse(rename.isEnabled())
                template.setText('{title}')
                self.assertTrue(rename.isEnabled())
                self.assertEqual(table.item(0, 1).text(), 'Titre.flac')
                observed.append(True)
            except Exception as error:
                observed.append(error)
            finally:
                dialog.reject()
        QTimer.singleShot(0, exercise)
        self.window.rename_from_metadata()
        self.assertEqual(observed, [True])
        self.assertTrue(row.path.exists())

    def test_advanced_metadata_proposals_keep_extension_and_reject_unknown_fields(self):
        row = self.choose('musique.flac', 'audio')
        self.assertEqual(batch_names([row], 'metadata', '{artist} / {title}'), ['Artiste _ Titre.flac'])
        with self.assertRaises(ValueError):
            batch_names([row], 'metadata', '{unknown}')
        with self.assertRaises(ValueError):
            batch_names([row], 'metadata', '{album}')

    def test_operations_reuse_one_window_with_two_independent_pages(self):
        self.window.show_jobs()
        dialog = self.window._operations_dialog
        self.assertEqual([dialog.tabs.tabText(i) for i in range(dialog.tabs.count())], ['Transferts', 'Analyses'])
        self.window.show_transfers()
        self.assertIs(self.window._operations_dialog, dialog)
        self.assertEqual(dialog.tabs.currentIndex(), 0)
        self.window.show_jobs(tab='analyses')
        self.assertEqual(dialog.tabs.currentIndex(), 1)
        dialog.close()

    def test_folder_summary_uses_visible_rows(self):
        self.choose('visible.txt', 'other')
        self.choose('masque.txt', 'other')
        self.window.proxy.name_filter = 'visible'
        self.window.proxy.invalidateFilter()
        with patch.object(QMessageBox, 'information') as info:
            self.window.show_folder_summary()
        self.assertIn('Fichiers affichés : 1', info.call_args.args[2])

    def test_legacy_toolbar_without_hidden_list_keeps_existing_buttons(self):
        from mirivue.desktop import TOOLBAR
        old_order = [name for name, _ in TOOLBAR if name != 'view_mode_button']
        library.write(self.window.settings, 'toolbar', {'order': old_order})
        _order, hidden, _before = self.window.toolbar_state()
        self.assertEqual(hidden, ['view_mode_button'])
        library.write(self.window.settings, 'toolbar', ['invalid'])
        _order, hidden, _before = self.window.toolbar_state()
        self.assertNotIn('view_mode_button', hidden)

    def test_integrated_rename_commits_valid_rows_without_overwriting_conflicts(self):
        first = self.choose('premier.txt', 'other')
        second = self.choose('second.txt', 'other')
        occupied = self.root/'occupe.txt'
        occupied.write_text('à conserver')
        observed = []
        def exercise():
            dialog = self.application.activeModalWidget()
            try:
                table = dialog.findChild(QTableWidget)
                table.item(0, 1).setText('nouveau.txt')
                table.item(1, 1).setText('occupe.txt')
                rename = next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Renommer')
                self.assertTrue(rename.isEnabled())
                observed.append(True)
                dialog.accept()
            except Exception as error:
                observed.append(error)
                dialog.reject()
        QTimer.singleShot(0, exercise)
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Ok):
            self.window._rename_rows([first, second])
        self.assertEqual(observed, [True])
        self.assertTrue((self.root/'nouveau.txt').exists())
        self.assertFalse((self.root/'premier.txt').exists())
        self.assertTrue((self.root/'second.txt').exists())
        self.assertEqual(occupied.read_text(), 'à conserver')

    def test_retired_playback_history_is_neither_collected_nor_deleted(self):
        self.window.settings.setValue('media/keep-play-history', True)
        self.window.settings.setValue('media/play-history', ['ancien.flac'])
        self.window.remember_played_media('nouveau.flac')
        self.assertEqual(self.window.playback_history(), ['ancien.flac'])


if __name__ == '__main__':
    unittest.main()
