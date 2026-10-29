"""Execute the actual menu blocks and rename methods with isolated Qt owners.

No native Window or file operation is created by these focused tests.
"""
import ast
import os
from pathlib import Path
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QWidget


ROOT = Path(os.environ.get('MIRIVUE_TEST_SOURCE_ROOT', Path(__file__).resolve().parents[1]))
SOURCE = (ROOT / 'mirivue/app.py').read_text(encoding='utf-8')
WINDOW = next(node for node in ast.parse(SOURCE).body if isinstance(node, ast.ClassDef) and node.name == 'Window')


def method(name):
    node = next(node for node in WINDOW.body if isinstance(node, ast.FunctionDef) and node.name == name)
    from mirivue.action_feedback import set_action_enabled
    namespace = {'tr': lambda text: text, 'QTimer': None, 'set_action_enabled': set_action_enabled}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(ROOT / 'mirivue/app.py'), 'exec'), namespace)
    return namespace[name]


def block(start, end, namespace):
    section = SOURCE[SOURCE.index(start):SOURCE.index(end, SOURCE.index(start))]
    exec(compile(textwrap.dedent('        ' + section), str(ROOT / 'mirivue/app.py'), 'exec'), namespace)


class TestRenameContextAccess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_context_group_has_no_advanced_duplicate(self):
        owner = QWidget()
        try:
            owner.batch_rename_action = QAction('Renommage avancé…', owner)
            owner.scanning = False
            owner.folder = '/tmp'
            owner.group_selected = Mock()
            owner.create_archive = Mock()
            owner.movement_locked = lambda paths: False
            owner.is_archive_view = lambda: False
            owner.selection_writable = lambda paths: bool(paths)
            owner.selection_block_reason = lambda paths: ''
            owner.can_create_archive = lambda paths: False
            owner.external_renamer_label = lambda: 'Renommer avec thunar…'
            owner.launch_renamer = Mock()
            menu = QMenu(owner)
            namespace = dict(self=owner, menu=menu, paths=['file1', 'file2'], count=2,
                             row=SimpleNamespace(is_dir=False), Path=Path,
                             tr=lambda text: text, mark_entry=lambda *args: None,
                             set_themed_action_icon=lambda *args: None,
                             set_action_enabled=__import__('mirivue.action_feedback', fromlist=['set_action_enabled']).set_action_enabled,
                             Location=SimpleNamespace(from_value=lambda value: SimpleNamespace(is_uri=False)))
            block("organize = menu.addMenu(tr('Organiser'))", '        if has_videos:', namespace)
            actions = namespace['organize'].actions()
            self.assertNotIn(owner.batch_rename_action, actions)
            self.assertIn('Déplacer vers un nouveau dossier…', [a.text() for a in actions])
            self.assertIn('Renommer avec thunar…', [a.text() for a in actions])
        finally:
            owner.close()

    def test_tools_keeps_advanced_action_and_its_callback(self):
        owner = QWidget()
        try:
            selected = [object()]
            owner.selected_indexes = lambda: [0]
            owner.row = lambda index: selected[index]
            owner._rename_rows = Mock()
            owner.batch_rename_action = QAction('Renommage avancé…', owner)
            owner.batch_rename_action.triggered.connect(lambda: method('rename_advanced')(owner))
            for name in ('metadata_rename_action', 'extensions_action', 'organize_folders_action',
                         'external_renamer_action', 'move_to_folder_action', 'create_archive_action'):
                setattr(owner, name, QAction(name, owner))
            block("self.rename_menu = QMenu(tr('Renommer et organiser'), self)", '        def reset(menu):',
                  dict(self=owner, QMenu=QMenu, tr=lambda text: text))
            self.assertIn(owner.batch_rename_action, owner.rename_menu.actions())
            owner.batch_rename_action.trigger()
            owner._rename_rows.assert_called_once_with(selected)
        finally:
            owner.close()

    def test_multiple_f2_still_uses_configured_tool(self):
        rows = [object(), object()]
        for external in (False, True):
            with self.subTest(external=external):
                owner = SimpleNamespace(is_archive_view=lambda: False, selection_locked=lambda: False,
                                        scanning=False, selected_indexes=lambda: [0, 1], row=lambda i: rows[i],
                                        settings=SimpleNamespace(value=lambda *args: 'external' if external else 'integrated'),
                                        launch_renamer=Mock(), _rename_rows=Mock())
                if external:
                    rows = [SimpleNamespace(path='one'), SimpleNamespace(path='two')]
                owner.rename_rows_with_chosen_tool = lambda selected: method('rename_rows_with_chosen_tool')(owner, selected)
                owner.rename_names = lambda: method('rename_names')(owner)
                method('rename_f2')(owner)
                if external:
                    owner.launch_renamer.assert_called_once_with(paths=['one', 'two'])
                    owner._rename_rows.assert_not_called()
                else:
                    owner._rename_rows.assert_called_once_with(rows, folder=None)
                    owner.launch_renamer.assert_not_called()

    def test_single_f2_still_edits_inline(self):
        index = Mock()
        index.siblingAtColumn.return_value = index
        view = Mock()
        view.currentIndex.return_value = index
        owner = SimpleNamespace(is_archive_view=lambda: False, selection_locked=lambda: False,
                                scanning=False, selected_indexes=lambda: [index], active_view=lambda: view,
                                table=Mock(), rename_names=Mock())
        method('rename_f2')(owner)
        view.edit.assert_called_once_with(index)
        owner.rename_names.assert_not_called()


if __name__ == '__main__':
    unittest.main()
