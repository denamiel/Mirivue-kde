"""Disposable-file and lifecycle regressions, independent of the desktop."""
import ast
import errno
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def functions(filename, names):
    tree = ast.parse((ROOT / 'mirivue' / filename).read_text())
    nodes = [node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name in names]
    scope = dict(Path=Path, os=os, stat=stat, time=time, hashlib=hashlib,
                 tempfile=tempfile, shutil=shutil, errno=errno, tr=lambda text: text,
                 trf=lambda text, *args: text)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), scope)
    return scope

class TestSourceCleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'a').write_bytes(b'original')
        self.scope = functions('file_moves.py', {'tree_snapshot', 'remove_verified_source',
                                               'validate_target', 'exists', '_move_one'})
        self.before = self.scope['tree_snapshot'](self.source)

    def test_new_child_survives_cleanup(self):
        (self.source / 'new').write_bytes(b'new data')
        with self.assertRaises(OSError):
            self.scope['remove_verified_source'](self.source, self.before)
        self.assertEqual((self.source / 'new').read_bytes(), b'new data')

    def test_changed_file_is_retained(self):
        (self.source / 'a').write_bytes(b'changed content')
        with self.assertRaises(OSError):
            self.scope['remove_verified_source'](self.source, self.before)
        self.assertEqual((self.source / 'a').read_bytes(), b'changed content')

    def test_replaced_directory_is_retained(self):
        saved = self.root / 'saved'
        self.source.rename(saved)
        self.source.mkdir()
        with self.assertRaises(OSError):
            self.scope['remove_verified_source'](self.source, self.before)
        self.assertTrue(self.source.exists())
        self.assertTrue((saved / 'a').exists())

    def test_unchanged_tree_is_removed(self):
        self.scope['remove_verified_source'](self.source, self.before)
        self.assertFalse(self.source.exists())

    def test_change_after_publication_preserves_source_and_copy(self):
        target = self.root / 'target'
        def rename(source, destination):
            if source == self.source:
                raise OSError(errno.EXDEV, 'simulate another device')
            source.rename(destination)
            (self.source / 'new').write_bytes(b'arrived during publication')
        self.scope['rename_noreplace'] = rename
        warning = self.scope['_move_one'](self.source, target)
        self.assertTrue(warning)
        self.assertEqual((target / 'a').read_bytes(), b'original')
        self.assertEqual((self.source / 'new').read_bytes(), b'arrived during publication')

    def test_failed_copy_preserves_source(self):
        self.scope['rename_noreplace'] = lambda *_: (_ for _ in ()).throw(OSError(errno.EXDEV, 'other device'))
        with patch('os.fsync', side_effect=OSError(errno.ENOSPC, 'disk full')):
            with self.assertRaises(OSError):
                self.scope['_move_one'](self.source, self.root / 'target')
        self.assertEqual((self.source / 'a').read_bytes(), b'original')
        self.assertFalse((self.root / 'target').exists())
        self.assertFalse(list(self.root.glob('.mirivue-deplacement-*')))

class TestWorkerFailure(unittest.TestCase):
    def test_unexpected_exception_is_recorded_as_failure(self):
        tree = ast.parse((ROOT / 'mirivue/file_moves.py').read_text())
        worker = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MoveWorker')
        run = next(n for n in worker.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        scope = {'__package__': 'mirivue', 'time': time, 'tr': lambda text:text,
                 'trf': lambda text,*args:text, 'errno':errno,
                 'tree_snapshot':lambda *args:{},
                 'move_one':lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('unexpected backend failure'))}
        exec(compile(ast.Module(body=[run], type_ignores=[]), 'file_moves.py', 'exec'), scope)
        fake = SimpleNamespace(plans=[(Path('/source'),Path('/target'))],
                               checked_interruption=lambda:False, source_signatures={},
                               progress=SimpleNamespace(emit=lambda *args:None),
                               errors=[], moved={}, copy_only=True, isInterruptionRequested=lambda:False)
        scope['run'](fake)
        self.assertEqual(fake.errors, ['unexpected backend failure'])
        self.assertEqual(fake.moved, {})

class TestBackgroundClose(unittest.TestCase):
    def test_waits_then_closes_without_cancelling_jobs(self):
        scope = functions('background_transfers.py', {'finish_background_transfer_close'})
        events = []
        pending = [object()]
        window = SimpleNamespace(_background_transfer_close_timer=SimpleNamespace(stop=lambda:events.append('stop')),
                                 isVisible=lambda:False, closing=False, pending_transfers=lambda:pending,
                                 close=lambda:events.append('close'), quit_requested=False)
        scope['finish_background_transfer_close'](window)
        self.assertEqual(events, [])
        pending.clear()
        scope['finish_background_transfer_close'](window)
        self.assertEqual(events, ['stop', 'close'])
        self.assertTrue(window.quit_requested)

    def test_reopening_window_cancels_deferred_close(self):
        scope = functions('background_transfers.py', {'finish_background_transfer_close'})
        events = []
        window = SimpleNamespace(_background_transfer_close_timer=SimpleNamespace(stop=lambda:events.append('stop')),
                                 isVisible=lambda:True, closing=False, pending_transfers=lambda:[],
                                 close=lambda:events.append('close'))
        scope['finish_background_transfer_close'](window)
        self.assertEqual(events, ['stop'])

if __name__ == '__main__':
    unittest.main()
