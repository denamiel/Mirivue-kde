"""Folder inventory reports visible progress before a file operation starts."""
import ast
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import time
import unittest

source = Path(__file__).resolve().parents[1] / 'mirivue' / 'file_moves.py'
module = ast.parse(source.read_text())
function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'tree_snapshot')
namespace = {'Path': Path, 'os': os, 'stat': stat, 'time': time, 'tr': lambda text: text}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
tree_snapshot = namespace['tree_snapshot']


class TestTransferInventoryProgress(unittest.TestCase):
    def test_nested_folder_reports_count_and_final_total(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / 'folder'
            (root / 'inside').mkdir(parents=True)
            (root / 'a.txt').write_text('a')
            (root / 'inside' / 'b.txt').write_text('b')
            updates = []

            snapshot = tree_snapshot(root, progress=lambda count, current: updates.append((count, current)))

            self.assertEqual(len(snapshot), 4)
            self.assertTrue(updates)
            self.assertEqual(updates[-1][0], 4)
            self.assertEqual(updates[-1][1], root)


if __name__ == '__main__':
    unittest.main()
