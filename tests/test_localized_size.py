import unittest
from unittest.mock import patch

try:
    from mirivue.metadata import quantity
except ImportError:
    quantity = None


@unittest.skipIf(quantity is None, 'PySide6 is not installed')
class TestLocalizedSize(unittest.TestCase):
    def test_file_sizes_use_the_native_kde_dialect_when_available(self):
        with patch('mirivue.metadata.services.format_bytes', return_value='1,0 kB') as native:
            self.assertEqual(quantity(1024, ['o', 'Kio'], 1024), '1,0 kB')
            native.assert_called_once_with(1024)
            self.assertEqual(quantity(1000, ['bit/s', 'kbit/s'], 1000), '1,0 kbit/s')

    def test_bytes_and_french_decimal(self):
        with patch('mirivue.metadata.configured_language', return_value='fr'), \
             patch('mirivue.metadata.services.format_bytes', return_value=None):
            self.assertEqual(quantity(8, ['o', 'Kio'], 1024), '8 o')
            self.assertEqual(quantity(115.6 * 1024, ['o', 'Kio'], 1024), '115,6 Kio')

    def test_english_decimal(self):
        with patch('mirivue.metadata.configured_language', return_value='en'), \
             patch('mirivue.metadata.services.format_bytes', return_value=None):
            self.assertEqual(quantity(115.6 * 1024, ['o', 'Kio'], 1024), '115.6 Kio')
