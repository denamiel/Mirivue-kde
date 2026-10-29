import unittest

from mirivue.preview_cache import PreviewCache


class Image:
    def __init__(self, size):
        self.size = size

    def sizeInBytes(self):
        return self.size


class PreviewCacheTests(unittest.TestCase):
    def test_evicts_least_recently_used_and_releases_replaced_image(self):
        cache = PreviewCache(max_bytes=10)
        cache['a'] = Image(4)
        cache['b'] = Image(4)
        self.assertIsNotNone(cache.get('a'))
        cache['c'] = Image(4)
        self.assertIsNone(cache.get('b'))
        self.assertIsNotNone(cache.get('a'))
        cache['a'] = Image(9)
        self.assertIsNone(cache.get('c'))
        self.assertEqual(cache.get('a').sizeInBytes(), 9)

    def test_pdf_tuple_and_oversize_preview(self):
        cache = PreviewCache(max_bytes=10)
        cache['page'] = (Image(8), 12)
        cache['huge'] = Image(11)
        self.assertIsNone(cache.get('huge'))
        self.assertEqual(cache.get('page')[1], 12)
        cache.clear()
        self.assertIsNone(cache.get('page'))


if __name__ == '__main__':
    unittest.main()
