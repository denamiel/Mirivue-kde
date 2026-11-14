"""Word capitalization normalizes existing capitals and preserves extensions."""
import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestBatchRenameTitle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / 'mirivue/renaming.py').read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'batch_names')
        namespace = {'re': re, 'tr': lambda value: value}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'renaming.py', 'exec'), namespace)
        cls.batch_names = staticmethod(namespace['batch_names'])

    def test_capitals_are_normalized_in_a_multi_file_selection(self):
        rows = [SimpleNamespace(path=Path(name), is_dir=False) for name in (
            'ma VIDEO de paris.mp4', 'ÉTÉ  À-PARIS_AVEC  ÉLODIE.MP4',
            'Déjà Correct.txt', 'SANS EXTENSION',
        )]
        self.assertEqual(self.batch_names(rows, 'title'), [
            'Ma Video De Paris.mp4', 'Été  À-Paris_Avec  Élodie.MP4',
            'Déjà Correct.txt', 'Sans Extension',
        ])

    def test_folder_name_is_capitalized_without_treating_dot_as_extension(self):
        row = SimpleNamespace(path=Path('MES VIDÉOS.ÉTÉ'), is_dir=True)
        self.assertEqual(self.batch_names([row], 'title'), ['Mes Vidéos.été'])


if __name__ == '__main__':
    unittest.main()
