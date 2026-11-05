"""Check that the integrated renamer can safely reverse a name exchange."""

import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from test_batch_rename_existing_names import TestBatchRenameExistingNames, load_functions


ROOT = Path(__file__).resolve().parents[1]


class TestLocalRenameUndo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TestBatchRenameExistingNames.setUpClass()
        cls.extensions = TestBatchRenameExistingNames.extensions
        warnings = []
        cls.warnings = warnings
        tree = ast.parse((ROOT / 'mirivue' / 'movement.py').read_text())
        klass = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MovementMixin')
        namespace = {
            '__name__': 'rename_test_pkg.movement',
            '__package__': 'rename_test_pkg',
            'BackgroundTransfers': object,
            'Rename': cls.extensions['Rename'],
            'apply_renames': cls.extensions['apply_renames'],
            'fingerprint': cls.extensions['fingerprint'],
            'tr': lambda value: value,
            'services': SimpleNamespace(_kio_undo_available=False, _kio_undo_text='',
                                        _kio_redo_available=False, _kio_redo_text=''),
            'QMessageBox': SimpleNamespace(warning=lambda _window, _title, message: warnings.append(message)),
        }
        exec(compile(ast.Module(body=[klass], type_ignores=[]), '<movement>', 'exec'), namespace)
        cls.mixin = namespace['MovementMixin']

    @classmethod
    def tearDownClass(cls):
        TestBatchRenameExistingNames.tearDownClass()

    def test_media_and_companions_undo_and_redo_once(self):
        import sys
        media = sys.modules['rename_test_pkg.media']
        media.IMAGE_EXT.add('.png')
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                sources = [root/'a.png', root/'b.png']
                for path in sources:
                    path.write_bytes(path.name.encode())
                    media.companion(path).write_bytes(b'original XMP')
                plans = [self.extensions['Rename'](path, root/f'Lot {i}.png',
                         self.extensions['fingerprint'](path)) for i, path in enumerate(sources)]
                changed, errors = self.extensions['apply_renames'](plans)
                self.assertFalse(errors)
                self.assertEqual(len(changed), 4)
                window = self.mixin()
                window.refresh_kio_panes = lambda: None
                window.record_local_renames(changed)
                self.assertTrue(window.apply_local_rename_history(True))
                for path in sources:
                    self.assertEqual(path.read_bytes(), path.name.encode())
                    self.assertEqual(media.companion(path).read_bytes(), b'original XMP')
                self.assertTrue(window.apply_local_rename_history(False))
                for plan in plans:
                    self.assertFalse(plan.source.exists())
                    self.assertEqual(plan.destination.read_bytes(), plan.source.name.encode())
                    self.assertEqual(media.companion(plan.destination).read_bytes(), b'original XMP')
        finally:
            media.IMAGE_EXT.discard('.png')

    def test_exchange_undo_and_redo_preserve_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'a.txt', root / 'b.txt'
            first.write_text('premier', encoding='utf-8')
            second.write_text('second', encoding='utf-8')
            signature = self.extensions['fingerprint']
            Rename = self.extensions['Rename']
            changed, errors = self.extensions['apply_renames']([
                Rename(first, second, signature(first)),
                Rename(second, first, signature(second)),
            ])
            self.assertFalse(errors)
            window = self.mixin()
            window.refresh_kio_panes = lambda: None
            window.record_local_renames(changed)
            window.apply_local_rename_history(True)
            self.assertEqual(first.read_text(encoding='utf-8'), 'premier')
            self.assertEqual(second.read_text(encoding='utf-8'), 'second')
            window.apply_local_rename_history(False)
            self.assertEqual(first.read_text(encoding='utf-8'), 'second')
            self.assertEqual(second.read_text(encoding='utf-8'), 'premier')

    def test_changed_file_is_not_reversed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new = root / 'ancien.txt', root / 'nouveau.txt'
            old.write_text('origine', encoding='utf-8')
            signature = self.extensions['fingerprint']
            changed, errors = self.extensions['apply_renames']([
                self.extensions['Rename'](old, new, signature(old))
            ])
            self.assertFalse(errors)
            window = self.mixin()
            window.refresh_kio_panes = lambda: None
            window.record_local_renames(changed)
            new.write_text('modification depuis le renommage', encoding='utf-8')
            window.apply_local_rename_history(True)
            self.assertFalse(old.exists())
            self.assertEqual(new.read_text(encoding='utf-8'), 'modification depuis le renommage')
            self.assertTrue(self.warnings)

    def test_two_renames_undo_and_redo_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second, third = (root / name for name in ('a.txt', 'b.txt', 'c.txt'))
            first.write_text('original', encoding='utf-8')
            signature = self.extensions['fingerprint']
            rename = self.extensions['Rename']
            window = self.mixin()
            window.refresh_kio_panes = lambda: None
            for source, target in ((first, second), (second, third)):
                changed, errors = self.extensions['apply_renames']([rename(source, target, signature(source))])
                self.assertFalse(errors)
                window.record_local_renames(changed)
            self.assertEqual(len(window.file_undo_history()), 2)
            window.apply_local_rename_history(True)
            self.assertTrue(second.exists())
            window.apply_local_rename_history(True)
            self.assertTrue(first.exists())
            window.apply_local_rename_history(False)
            window.apply_local_rename_history(False)
            self.assertEqual(third.read_text(encoding='utf-8'), 'original')

    def test_kio_entry_keeps_rename_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / 'a.txt', root / 'b.txt'
            first.write_text('original', encoding='utf-8')
            changed, errors = self.extensions['apply_renames']([
                self.extensions['Rename'](first, second, self.extensions['fingerprint'](first))
            ])
            self.assertFalse(errors)
            window = self.mixin()
            window.refresh_kio_panes = lambda: None
            window.record_local_renames(changed)
            window.record_kio_history()
            self.assertEqual([kind for kind, _entry in window.file_undo_history()], ['rename', 'kio'])
            self.assertFalse(window.apply_local_rename_history(True))
            self.assertTrue(second.exists())


if __name__ == '__main__':
    unittest.main()
