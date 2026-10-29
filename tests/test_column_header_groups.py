import unittest

from mirivue.column_groups import PRIMARY_COLUMNS, MEDIA_COLUMNS


class TestColumnHeaderGroups(unittest.TestCase):
    def test_every_available_column_remains_reachable(self):
        groups = dict(MEDIA_COLUMNS)
        self.assertEqual(tuple(groups), ('Informations communes', 'Document', 'Image', 'Audio', 'Vidéo', 'Autre'))
        offered = set(PRIMARY_COLUMNS)
        for columns in groups.values():
            offered.update(columns)
        self.assertEqual(offered, set(range(1, 40)) - {10, 12, 13, 15, 16, 36})
        self.assertEqual(set(PRIMARY_COLUMNS) & set().union(*groups.values()), set())
        offered_list = list(PRIMARY_COLUMNS) + [c for cols in groups.values() for c in cols]
        self.assertEqual(len(offered_list), len(set(offered_list)))
        self.assertEqual(groups['Informations communes'], (2, 3, 8))


if __name__ == '__main__':
    unittest.main()
