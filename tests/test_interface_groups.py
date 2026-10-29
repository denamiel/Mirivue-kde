"""Real configuration controls and the menu lists actually supplied to populate."""
import ast
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication, QGroupBox
from mirivue.keyboard import _effective
import test_interface_polish as polish

class TestPreviewGroups(unittest.TestCase):
    # Reuse only the real Qt owner and cleanup, without duplicating test cases.
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    setUp=polish.TestInterfacePolish.setUp
    tearDown=polish.TestInterfacePolish.tearDown
    dialog=polish.TestInterfacePolish.dialog
    def test_preview_controls_are_grouped_without_changing_their_values(self):
        self.settings.setValue('media/seek-step-seconds', 23)
        self.settings.setValue('media/volume-step-percent', 9)
        self.settings.setValue('media/preview-first-item', True)
        before={key:self.settings.value(key) for key in self.settings.allKeys()}
        dialog=self.dialog()
        groups={group.title():group for group in dialog.findChildren(QGroupBox)}
        for name, controls in [('Miniatures', ['previews']),
                               ('Panneau d’aperçu', ['preview_panel_startup','preview_first_item']),
                               ('Lecture', ['seek_step','volume_step'])]:
            self.assertIn(name,groups)
            for control in controls:self.assertTrue(groups[name].isAncestorOf(getattr(dialog,control)),control)
        self.assertEqual(dialog.seek_step.value(),23)
        self.assertEqual(dialog.volume_step.value(),9)
        self.assertTrue(dialog.preview_first_item.isChecked())
        dialog.reject()
        self.assertEqual({key:self.settings.value(key) for key in self.settings.allKeys()},before)

class TestMenuGroups(unittest.TestCase):
    def menu_lists(self):
        import mirivue.app
        tree=ast.parse(Path(mirivue.app.__file__).read_text())
        function=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='rebuild_main_menus')
        return {node.args[0].slice.value:[ast.unparse(item) for item in node.args[1].elts]
                for node in ast.walk(function) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name) and node.func.id=='populate'}
    def test_clipboard_path_commands_share_the_clipboard_group(self):
        edit=self.menu_lists()['edit']
        start=edit.index("transfers[tr('Couper')]");end=edit.index('None',start)
        self.assertIn('self.copy_folder_name_action',edit[start:end])
        self.assertIn('self.copy_paths_action',edit[start:end])
        self.assertLess(end,edit.index('self.search_action'))
    def test_duration_is_a_direct_tools_command_not_metadata_editing(self):
        menus=self.menu_lists()
        self.assertIn('self.folder_duration_action',menus['tools'])
        self.assertNotIn('self.folder_duration_action',menus['organize'])
    def test_explicit_default_primary_does_not_reenable_secondary_keys(self):
        binding={'default':'Ctrl++','defaults':['Ctrl++','Ctrl+=']}
        self.assertEqual(_effective(binding,['Ctrl++']),['Ctrl++'])
        self.assertEqual(_effective(binding,'Ctrl++'),['Ctrl++','Ctrl+='])
