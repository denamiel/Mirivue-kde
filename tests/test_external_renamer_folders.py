"""Folder F2 and folder-contents bulk renaming use distinct commands."""

import ast
from pathlib import Path
import os
import shlex
import shutil
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


def function_from(source, name, namespace, class_name=None):
    tree = ast.parse((ROOT / 'mirivue' / source).read_text(encoding='utf-8'))
    nodes = tree.body
    if class_name:
        nodes = next(node.body for node in nodes if isinstance(node, ast.ClassDef) and node.name == class_name)
    function = next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), source, 'exec'), namespace)
    return namespace[name]


class TestExternalRenamerFolders(unittest.TestCase):
    def test_external_command_accepts_a_selected_folder(self):
        command = function_from('renaming.py', 'external_command', {
            'shutil': shutil, 'shlex': shlex, 'os': os,
            'tr': lambda value: value,
            'trf': lambda value, *args: value.replace('\x1f0\x1f', str(args[0])),
        })
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / '64654'
            folder.mkdir()
            executable, arguments = command('true', '', [folder])
            self.assertEqual(executable, shutil.which('true'))
            self.assertEqual(arguments, [str(folder.absolute())])

    def test_folder_inventory_includes_hidden_files_and_subdirectories(self):
        folder_rename_rows = function_from('renaming.py', 'folder_rename_rows', {
            'Path': Path, 'os': os, 'SimpleNamespace': SimpleNamespace,
            'fingerprint': lambda path: path.lstat().st_ino,
            'tr': lambda value: value,
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '64654').mkdir()
            (root / '.hidden').write_text('a', encoding='utf-8')
            (root / 'visible.txt').write_text('b', encoding='utf-8')
            rows = folder_rename_rows(root)
            self.assertEqual({row.path.name for row in rows}, {'64654', '.hidden', 'visible.txt'})
            self.assertTrue(all(row.file_signature for row in rows))

    def test_launch_on_folder_routes_to_its_contents(self):
        launched = []
        configured = []
        namespace = {
            'tr': lambda value: value,
            'QProcess': SimpleNamespace(startDetached=lambda executable, arguments:
                                        (launched.append((executable, arguments)) or True, 1)),
            'external_command': lambda program, arguments, paths:
                                (program, [str(path) for path in paths]),
        }
        launch = function_from('app.py', 'launch_renamer', namespace, 'Window')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / '64654'
            folder.mkdir()
            child = folder / 'file.txt'
            child.write_text('a', encoding='utf-8')
            setting = {'renamer/program': '/usr/bin/true', 'renamer/arguments': ''}
            watcher = SimpleNamespace(directories=lambda: [], addPaths=lambda paths: None)
            window = SimpleNamespace(
                selection_locked=lambda: False, scanning=False,
                selected_indexes=lambda: [0], row=lambda index: SimpleNamespace(path=folder),
                paths_locked=lambda paths: False,
                rename_folder_contents=lambda path: self.fail('Explicit external command must launch directly'),
                settings=SimpleNamespace(value=lambda name, default='': setting.get(name, default)),
                external_watcher=watcher, external_timer=SimpleNamespace(start=lambda: None),
                show_activity_message=lambda *args: None,
                choose_renamer=lambda **kwargs: configured.append(kwargs),
            )
            namespace['folder_rename_rows'] = lambda path: [SimpleNamespace(path=child)]
            launch(window)
            self.assertEqual(launched, [('/usr/bin/true', [str(child)])])
            launched.clear()
            launch(window, paths=[child])
            self.assertEqual(launched, [('/usr/bin/true', [str(child)])])
            setting['renamer/program'] = ''
            launch(window, paths=[child])
            self.assertEqual(configured, [{'launch': True, 'paths': [child]}])

    def test_folder_contents_uses_same_tool_choice_as_selected_files(self):
        inventory = function_from('renaming.py', 'folder_rename_rows', {
            'Path': Path, 'os': os, 'SimpleNamespace': SimpleNamespace,
            'fingerprint': lambda path: path.lstat().st_ino,
            'tr': lambda value: value,
        })
        command = function_from('app.py', 'rename_folder_contents', {
            'folder_rename_rows': inventory,
        }, 'Window')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / '64654'
            folder.mkdir()
            (folder / 'a.txt').write_text('a', encoding='utf-8')
            (folder / '.hidden').write_text('b', encoding='utf-8')
            nested = folder / 'nested'
            nested.mkdir()
            (nested / 'not-listed.txt').write_text('c', encoding='utf-8')
            received = []
            chosen_tool = {'renamer/tool': 'integrated'}
            launches = []
            dispatch = function_from('app.py', 'rename_rows_with_chosen_tool', {}, 'Window')
            window = SimpleNamespace(
                scanning=False, paths_locked=lambda paths: False,
                _rename_rows=lambda rows, folder=None: received.append((rows, folder)),
                launch_renamer=lambda **kwargs: launches.append(kwargs),
                settings=SimpleNamespace(value=lambda key, default=None: chosen_tool.get(key, default)),
            )
            window.rename_rows_with_chosen_tool = lambda rows, folder=None: dispatch(window, rows, folder)
            command(window, folder)
            self.assertEqual(len(received), 1)
            rows, target = received[0]
            self.assertEqual(target, folder)
            self.assertEqual({row.path.name for row in rows}, {'a.txt', '.hidden', 'nested'})
            self.assertEqual(launches, [])
            chosen_tool['renamer/tool'] = 'external'
            command(window, folder)
            self.assertEqual(launches, [{'paths': [row.path for row in rows]}])
            self.assertEqual(len(received), 1)
            self.assertTrue(folder.is_dir())

    def test_selection_uses_the_same_tool_dispatch(self):
        rename = function_from('app.py', 'rename_names', {}, 'Window')
        row = SimpleNamespace(path=Path('/tmp/example.txt'))
        dispatched = []
        window = SimpleNamespace(
            selected_indexes=lambda: [0], row=lambda index: row,
            rename_rows_with_chosen_tool=lambda rows: dispatched.append(rows),
        )
        rename(window)
        self.assertEqual(dispatched, [[row]])


if __name__ == '__main__':
    unittest.main()
