from datetime import datetime, timedelta
from pathlib import Path
import unittest

from mirivue.date_display import modification_text, normalized_date_format


ROOT = Path(__file__).resolve().parents[1]


class TestDateFormats(unittest.TestCase):
    @staticmethod
    def timestamp_ns(value):
        return int(value.timestamp() * 1_000_000_000)

    def test_iso_format_is_stable(self):
        value = datetime(2026, 9, 30, 8, 18, 45)
        self.assertEqual(
            modification_text(self.timestamp_ns(value), mode='iso'),
            '2026-09-30 08:18:45',
        )

    def test_regional_format_uses_the_process_locale(self):
        value = datetime(2026, 9, 30, 8, 18, 45)
        try:
            from PySide6.QtCore import QDateTime, QLocale
        except ImportError:
            expected = value.strftime('%c')
        else:
            expected = QLocale().toString(
                QDateTime.fromMSecsSinceEpoch(self.timestamp_ns(value) // 1_000_000),
                QLocale.FormatType.ShortFormat)
        self.assertEqual(
            modification_text(self.timestamp_ns(value), mode='locale'),
            expected,
        )

    def test_informal_format_keeps_today_yesterday_and_recent_weekday(self):
        now = datetime(2026, 9, 30, 12, 0, 0)
        today = datetime(2026, 9, 30, 8, 18, 45)
        yesterday = today - timedelta(days=1)
        recent = today - timedelta(days=3)
        self.assertEqual(
            modification_text(self.timestamp_ns(today), now=now, mode='informal'),
            'Aujourd’hui à 08:18',
        )
        self.assertEqual(
            modification_text(self.timestamp_ns(yesterday), now=now, mode='informal'),
            'Hier à 08:18',
        )
        self.assertEqual(
            modification_text(self.timestamp_ns(recent), now=now, mode='informal'),
            recent.strftime('%A').capitalize() + ' à 08:18',
        )

    def test_invalid_saved_value_returns_to_system_format(self):
        self.assertEqual(normalized_date_format('unknown'), 'locale')

    def test_configuration_applies_immediately_without_changing_sort_role(self):
        configuration = (ROOT / 'mirivue' / 'configuration.py').read_text()
        application = (ROOT / 'mirivue' / 'app.py').read_text()
        self.assertIn("w.set_date_format('informal' if self.date_relative.isChecked() else 'locale')", configuration)
        self.assertIn("pane.model.date_format = mode", application)
        self.assertIn("return row.sort_values[column]", application)


if __name__ == '__main__':
    unittest.main()
