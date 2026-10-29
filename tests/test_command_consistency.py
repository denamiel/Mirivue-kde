"""Focused Qt forms and actual menu blocks; no full native window or file writes."""
import textwrap
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QDialog
from mirivue.configuration import ConfigurationDialog
from mirivue.app import Window
from mirivue.action_feedback import set_action_enabled
from mirivue.locations import Location
from mirivue.keyboard import extend_bindings
from mirivue.rename_ui import show_advanced_rename
from test_date_style_configuration import Owner, ContextFixture
from test_rename_context_access import method, block, SOURCE


class TestCommandConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.owner = Owner(QSettings(str(self.root/'settings.ini'), QSettings.Format.IniFormat))
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            if hasattr(dialog, 'search_timer'): dialog.search_timer.stop()
            dialog.close()
        self.app.processEvents()
        self.owner.close()
        self.temp.cleanup()

    def config(self):
        with patch('mirivue.context_menu_settings.ContextMenuPage', ContextFixture):
            dialog = ConfigurationDialog(self.owner)
        self.dialogs.append(dialog)
        return dialog

    def test_external_settings_editable_with_both_default_tools(self):
        dialog = self.config()
        for tool in ('integrated', 'external'):
            with self.subTest(tool=tool):
                dialog.renamer_tool.setCurrentIndex(dialog.renamer_tool.findData(tool))
                self.assertTrue(dialog.renamer.isEnabled())
                self.assertTrue(dialog.renamer_args.isEnabled())
                dialog.renamer.setText('thunar')
                dialog.renamer_args.setText('-B')
                self.assertTrue(dialog.apply())
                self.assertEqual(self.owner.settings.value('renamer/program'), 'thunar')
                self.assertEqual(self.owner.settings.value('renamer/tool'), tool)
        self.assertTrue(self.config().renamer.isEnabled())

    def test_preview_help_explains_both_persistence_modes(self):
        help_text = self.config().previews.toolTip()
        self.assertIn('style commun', help_text)
        self.assertIn('par dossier', help_text)
        self.assertIn('dossier actif', help_text)

    def command_owner(self, path, locked=False, archive=False, scanning=False):
        row = SimpleNamespace(path=path, is_dir=False, is_video=True, media_type='video')
        owner = Mock()
        owner.folder = str(path.parent) if isinstance(path, Path) else 'smb://server/share'
        owner.selected_indexes.return_value = [0]
        owner.row.return_value = row
        owner.scanning = scanning
        owner.is_archive_view.return_value = archive
        owner.movement_locked.return_value = locked
        owner.current_folder_is_local.return_value = isinstance(path, Path)
        owner.selection_writable = lambda paths: bool(paths) and not scanning and not archive and not locked
        owner.can_create_archive = lambda paths: owner.selection_writable(paths) and isinstance(path, Path) and path.exists()
        owner.proxy.rowCount.return_value = 1
        # RC193 lacks the shared predicates; the fallback lets the same test
        # reproduce its menu-state mismatches. RC193 executes the real helpers.
        if hasattr(Window, 'selection_writable'):
            owner.selection_writable = Window.selection_writable.__get__(owner)
            owner.selection_block_reason = Window.selection_block_reason.__get__(owner)
            owner.can_create_archive = Window.can_create_archive.__get__(owner)
        owner.search_active = False
        owner.split_enabled = True
        owner.resume_data = []
        owner.content_stack.currentIndex.return_value = 0
        owner.external_renamer_label.return_value = 'Renommer avec thunar…'
        owner.transfer_actions = {name: Mock() for name in ('Copier','Couper','Dupliquer')}
        return owner, row

    def context(self, owner, row):
        menu = QMenu(self.owner)
        self.dialogs.append(menu)
        namespace = dict(self=owner, menu=menu, paths=[row.path], count=1, row=row,
                         selected=[row], has_videos=True, has_media=True,
                         Path=Path, Location=Location, tr=lambda text:text, set_action_enabled=set_action_enabled,
                         mark_entry=lambda *args:None, set_themed_action_icon=lambda *args:None)
        block("organize = menu.addMenu(tr('Organiser'))", '        related = self.associated_entries(paths)', namespace)
        return {action.text(): action for action in namespace['organize'].actions()}

    def test_archive_disabled_in_both_menus_for_remote_paths(self):
        owner,row = self.command_owner('smb://server/share/file.mkv')
        method('update_main_menu_states')(owner, refresh_details=False)
        owner.create_archive_action.setEnabled.assert_called_once_with(False)
        self.assertFalse(self.context(owner,row)['Créer une archive…'].isEnabled())

    def test_mutating_context_actions_match_tools_while_locked_or_in_archive(self):
        path=self.root/'film.mkv';path.write_bytes(b'test')
        for flags in ({'locked':True},{'archive':True},{'scanning':True},{}):
            with self.subTest(flags=flags):
                owner,row=self.command_owner(path,**flags)
                method('update_main_menu_states')(owner,refresh_details=False)
                actions=self.context(owner,row)
                for label,attr in [('Créer une archive…','create_archive_action'),
                                   ('Déplacer vers un nouveau dossier…','move_to_folder_action'),
                                   ('Corriger les extensions de la sélection…','extensions_action'),
                                   ('Renommer à partir des métadonnées…','metadata_rename_action'),
                                   ('Organiser en sous-dossiers…','organize_folders_action')]:
                    expected=getattr(owner,attr).setEnabled.call_args.args[0]
                    self.assertEqual(actions[label].isEnabled(),expected,(flags,label))

    def test_metadata_editor_context_matches_tools_when_locked(self):
        path=self.root/'film.mkv';path.write_bytes(b'test')
        owner,row=self.command_owner(path,locked=True)
        method('update_main_menu_states')(owner,refresh_details=False)
        namespace=dict(self=owner,media=QMenu(self.owner),tr=lambda text:text,
                       set_themed_action_icon=lambda *args:None,writable=False,reason='Occupé',set_action_enabled=set_action_enabled)
        self.dialogs.append(namespace['media'])
        start = SOURCE.index("metadata_action = media.addAction(tr('Modifier les métadonnées…'), self.edit_metadata)")
        end = SOURCE.index('            self.add_personal_label_menu(media, selected)', start)
        exec(textwrap.dedent('            '+SOURCE[start:end]), namespace)
        self.assertEqual(namespace['metadata_action'].isEnabled(),owner.metadata_action.setEnabled.call_args.args[0])

    def test_rename_title_matches_entry_and_preserves_folder_title(self):
        path=self.root/'film.mkv';path.write_bytes(b'test')
        row=SimpleNamespace(path=path)
        self.owner.selection_locked=lambda:False
        self.owner.scanning=False
        def reject(dialog):
            self.dialogs.append(dialog)
            titles.append(dialog.windowTitle())
            return QDialog.DialogCode.Rejected
        titles=[]
        with patch('mirivue.rename_ui.QTimer.singleShot'),patch.object(QDialog,'exec',reject):
            show_advanced_rename(self.owner,[row])
            show_advanced_rename(self.owner,[row],folder=self.root)
        self.assertEqual(titles[0],'Renommage avancé')
        self.assertEqual(titles[1],f'Renommer le contenu de « {self.root.name} »')

    def test_terminal_tooltips_explain_distinct_destinations(self):
        owner=self.owner
        owner.main_menus={'tools':QMenu(owner)}
        owner.open_terminal_here=Mock()
        def add(identifier,title,shortcut,callback,menu,icon):
            action=QAction(title,owner);action.triggered.connect(callback);menu.addAction(action);return action
        block('self.open_terminal_action = add_menu_action(', '    def init_shortcut_configuration(',
              dict(self=owner,add_menu_action=add,tr=lambda text:text))
        for name in ('new_tab_action','close_tab_action','reopen_tab_action','next_tab_action',
                     'previous_tab_action','guide_action','configure_action'):
            setattr(owner,name,QAction(owner))
        owner.transfer_actions={name:QAction(owner) for name in ('Couper','Copier','Coller','Dupliquer')}
        owner.copy_selected_paths=Mock()
        extend_bindings(owner,lambda *args:None)
        self.assertIn('dossier affiché',owner.open_terminal_action.toolTip())
        self.assertIn('sélectionné',owner.terminal_selection_action.toolTip())
        self.assertNotEqual(owner.open_terminal_action.toolTip(),owner.terminal_selection_action.toolTip())
