"""Regression for the shared Delete action when a second pane is selected."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

source = Path(__file__).resolve().parents[1] / 'mirivue' / 'app.py'
module = ast.parse(source.read_text())
cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and any(isinstance(n, ast.FunctionDef) and n.name == 'refresh_delete_availability' for n in node.body))
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refresh_delete_availability')
ns = {}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), ns)

class TestDeleteActionState(unittest.TestCase):
    def test_selected_entry_enables_delete_without_deferred_footer_refresh(self):
        values = []
        pane = SimpleNamespace(scanning=False,
            selected_indexes=lambda: [0], row=lambda i: SimpleNamespace(path=Path('/mnt/data/example')),
            is_archive_view=lambda: False, movement_locked=lambda paths: False,
            delete_button=SimpleNamespace(setEnabled=values.append))
        ns['refresh_delete_availability'](pane)
        self.assertEqual(values, [True])

    def test_locked_entry_stays_disabled(self):
        values = []
        pane = SimpleNamespace(scanning=False,
            selected_indexes=lambda: [0], row=lambda i: SimpleNamespace(path=Path('/mnt/data/example')),
            is_archive_view=lambda: False, movement_locked=lambda paths: True,
            delete_button=SimpleNamespace(setEnabled=values.append))
        ns['refresh_delete_availability'](pane)
        self.assertEqual(values, [False])
