"""Ark-style automatic extraction folder names."""
import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'mirivue' / 'locations.py'
MODULE = ast.parse(SOURCE.read_text(encoding='utf-8'))
NODES = [
    node for node in MODULE.body
    if (isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == 'ARCHIVE_SUFFIXES'
        for target in node.targets))
    or (isinstance(node, ast.FunctionDef) and node.name == 'archive_subfolder_name')
]
namespace = {'Path': Path}
exec(compile(ast.Module(body=NODES, type_ignores=[]), str(SOURCE), 'exec'), namespace)


class TestArchiveSubfolder(unittest.TestCase):
    def test_compound_and_simple_suffixes_are_removed(self):
        folder = namespace['archive_subfolder_name']
        self.assertEqual(folder('/tmp/photos.tar.gz'), 'photos')
        self.assertEqual(folder('/tmp/sauvegarde.tar.zst'), 'sauvegarde')
        self.assertEqual(folder('/tmp/documents.zip'), 'documents')
        self.assertEqual(folder('/tmp/documents.rar'), 'documents')
        self.assertEqual(folder('/tmp/paquet.deb'), 'paquet')


if __name__ == '__main__':
    unittest.main()
