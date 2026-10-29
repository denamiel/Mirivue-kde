"""Verify that the name sort cache follows the displayed name after rename."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


source = Path(__file__).resolve().parents[1] / 'mirivue' / 'natural_sort.py'
spec = importlib.util.spec_from_file_location('mirivue_natural_sort', source)
natural_sort = importlib.util.module_from_spec(spec)
spec.loader.exec_module(natural_sort)


class TestNaturalSortCache(unittest.TestCase):
    def test_key_is_reused_and_recomputed_after_rename(self):
        cached_key = natural_sort.cached_natural_name_key
        row = SimpleNamespace(values=['Épisode 2.mkv'])
        first = cached_key(row)
        self.assertIs(cached_key(row), first)
        row.values[0] = 'Épisode 10.mkv'
        self.assertLess(first, cached_key(row))
        self.assertIsNot(cached_key(row), first)


if __name__ == '__main__':
    unittest.main()
