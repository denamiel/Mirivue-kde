import ast
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[1]


def translated(template, *values):
    for index, value in enumerate(values):
        template = template.replace(f'\x1f{index}\x1f', str(value))
    return template


def load_functions(source_name, names, namespace):
    tree = ast.parse((ROOT / 'mirivue' / source_name).read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), source_name, 'exec'), namespace)
    return namespace


class FileServices:
    @staticmethod
    def validate_portable_name(name):
        return '' if name and '/' not in name else 'Nom invalide.'

    @staticmethod
    def rename_no_replace(source, destination):
        if os.path.lexists(destination):
            raise FileExistsError(destination)
        os.rename(source, destination)


class TestBatchRenameExistingNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        extensions = load_functions('extensions.py', {'Rename', 'fingerprint', 'rename_no_replace', '_temporary_rename_path', 'apply_renames'}, {
            '__name__': 'rename_test_pkg.extensions',
            '__package__': 'rename_test_pkg',
            'dataclass': dataclass,
            'Path': Path,
            'os': os,
            'stat': stat,
            'uuid': uuid,
            'services': FileServices(),
            'tr': lambda value: value,
            'trf': translated,
        })
        cls.extensions = extensions
        cls.renaming = load_functions('renaming.py', {'prepare_names'}, {
            'os': os,
            'services': FileServices(),
            'tr': lambda value: value,
            'Rename': extensions['Rename'],
            'fingerprint': extensions['fingerprint'],
        })
        package = ModuleType('rename_test_pkg')
        package.__path__ = []
        media = ModuleType('rename_test_pkg.media')
        media.companion = lambda path: Path(str(path) + '.xmp')
        media.AUDIO_EXT = set()
        media.IMAGE_EXT = set()
        metadata = ModuleType('rename_test_pkg.metadata')
        metadata.EXTENSIONS = set()
        cls.previous_modules = {name: sys.modules.get(name) for name in ('rename_test_pkg', 'rename_test_pkg.media', 'rename_test_pkg.metadata')}
        sys.modules['rename_test_pkg'] = package
        sys.modules['rename_test_pkg.media'] = media
        sys.modules['rename_test_pkg.metadata'] = metadata

    @classmethod
    def tearDownClass(cls):
        for name, module in cls.previous_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def row(self, path):
        return SimpleNamespace(path=path, file_signature=self.extensions['fingerprint'](path))

    def test_a_file_already_correct_is_ignored_while_others_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            correct = root / '001.txt'
            other = root / 'photo.txt'
            correct.write_text('correct', encoding='utf-8')
            other.write_text('other', encoding='utf-8')
            plans = self.renaming['prepare_names']([self.row(correct), self.row(other)], ['001.txt', '002.txt'])
            self.assertEqual([(plan.source.name, plan.destination.name, plan.issue) for plan in plans], [('photo.txt', '002.txt', '')])
            renamed, errors = self.extensions['apply_renames'](plans)
            self.assertFalse(errors)
            self.assertEqual(renamed, {other: root / '002.txt'})
            self.assertEqual(correct.read_text(encoding='utf-8'), 'correct')
            self.assertEqual((root / '002.txt').read_text(encoding='utf-8'), 'other')

    def test_numbering_chain_is_staged_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / name for name in ('002.txt', '003.txt', 'photo.txt')]
            for path, content in zip(paths, ('two', 'three', 'photo')):
                path.write_text(content, encoding='utf-8')
            plans = self.renaming['prepare_names']([self.row(path) for path in paths], ['001.txt', '002.txt', '003.txt'])
            self.assertTrue(all(not plan.issue for plan in plans))
            renamed, errors = self.extensions['apply_renames'](plans)
            self.assertFalse(errors)
            self.assertEqual(len(renamed), 3)
            self.assertEqual([(root / name).read_text(encoding='utf-8') for name in ('001.txt', '002.txt', '003.txt')], ['two', 'three', 'photo'])

    def test_unselected_existing_destination_remains_a_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            occupied = root / '001.txt'
            source = root / 'photo.txt'
            occupied.write_text('keep', encoding='utf-8')
            source.write_text('source', encoding='utf-8')
            plans = self.renaming['prepare_names']([self.row(source)], ['001.txt'])
            self.assertEqual(len(plans), 1)
            self.assertEqual(plans[0].issue, 'Ce nom existe déjà.')
            renamed, errors = self.extensions['apply_renames'](plans)
            self.assertFalse(renamed)
            self.assertEqual(len(errors), 1)
            self.assertEqual(occupied.read_text(encoding='utf-8'), 'keep')
            self.assertEqual(source.read_text(encoding='utf-8'), 'source')

    def test_dialog_accepts_valid_rows_even_when_others_conflict(self):
        method = (ROOT / 'mirivue' / 'rename_ui.py').read_text(encoding='utf-8')
        self.assertIn('accept.setEnabled(ready > 0)', method)
        self.assertNotIn("tr('Renommage annulé')", method)
        self.assertIn('déjà correctement nommé(s) ignoré(s)', method)


if __name__ == '__main__':
    unittest.main()
