"""User-facing transfer feedback names the action, never its backend."""
import ast
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[1] / 'mirivue' / 'movement.py'
module = ast.parse(source.read_text())
functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in ('transfer_labels', 'readable_transfer_error')]
ns = {'tr': lambda x: x}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), ns)
class TestTransferWording(unittest.TestCase):
    def test_copy_and_move_are_distinct(self):
        self.assertEqual(ns['transfer_labels']('copy')[0], 'Copie')
        self.assertEqual(ns['transfer_labels']('move')[0], 'Déplacement')
    def test_internal_backend_error_is_hidden_but_real_error_remains(self):
        self.assertEqual(ns['readable_transfer_error']('KIO unavailable', 'La copie a échoué.'), 'La copie a échoué.')
        self.assertEqual(ns['readable_transfer_error']('Permission denied', 'La copie a échoué.'), 'Permission denied')
