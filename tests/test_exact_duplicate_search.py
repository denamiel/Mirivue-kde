import ast
from collections import defaultdict
import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def translated(template, *values):
    for index, value in enumerate(values):
        template = template.replace(f'\x1f{index}\x1f', str(value))
    return template


def fingerprint(path):
    info = Path(path).lstat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def load_duplicate_functions():
    tree = ast.parse((ROOT / 'mirivue' / 'duplicates.py').read_text(encoding='utf-8'))
    wanted = {'file_hash', 'find_duplicates'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {
        'Path': Path,
        'defaultdict': defaultdict,
        'hashlib': hashlib,
        'os': os,
        'stat': stat,
        'fingerprint': fingerprint,
        'tr': lambda value: value,
        'trf': translated,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'duplicates.py', 'exec'), namespace)
    return namespace['find_duplicates']


class TestExactDuplicateSearch(unittest.TestCase):
    def test_only_complete_byte_identical_files_are_grouped(self):
        find_duplicates = load_duplicate_functions()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / 'premier.bin'
            second = root / 'sous-dossier' / 'second.bin'
            different = root / 'meme-taille.bin'
            second.parent.mkdir()
            first.write_bytes(b'contenu identique')
            second.write_bytes(b'contenu identique')
            different.write_bytes(b'contenu different')

            groups = find_duplicates([first, second, different])

            self.assertEqual(len(groups), 1)
            self.assertEqual({path for path, _signature in groups[0]['files']}, {first, second})
            self.assertEqual(groups[0]['digest'], hashlib.sha256(b'contenu identique').hexdigest())

    def test_symlinks_and_repeated_paths_are_not_false_duplicates(self):
        find_duplicates = load_duplicate_functions()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / 'original.bin'
            link = root / 'lien.bin'
            original.write_bytes(b'donnees')
            link.symlink_to(original)

            self.assertEqual(find_duplicates([original, original, link]), [])


if __name__ == '__main__':
    unittest.main()
