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
