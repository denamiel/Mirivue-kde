"""Mirivue KDE keeps KDE association handling when opened in GNOME."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtGui import QIcon
    from mirivue.platform_services import services
    from mirivue.media_ui import default_application_icon
except ImportError:
    QIcon = None


@unittest.skipIf(QIcon is None, 'PySide6 is unavailable on this machine')
class TestKdeAssociationsCrossSession(unittest.TestCase):
    def test_default_open_uses_kio_in_gnome(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME',
                                     'XDG_SESSION_DESKTOP': 'GNOME',
                                     'KDE_FULL_SESSION': ''}), \
             patch.object(services, 'tool_path', return_value='/tmp/mirivue-kio-open'), \
             patch('mirivue.platform_services.QProcess.startDetached', return_value=True) as launch:
            self.assertFalse(services.is_plasma)
            self.assertTrue(services.open_default_file(Path('/tmp/example.mkv')))
            launch.assert_called_once_with('/tmp/mirivue-kio-open', ['/tmp/example.mkv'])

    def test_document_icon_queries_kde_preferred_service_each_time(self):
        class Result:
            stdout = json.dumps({'identifier': 'org.example.Viewer.desktop',
                                 'icon': 'example-viewer'})

        with patch.object(services, 'tool_path', return_value='/tmp/mirivue-kio-applications'), \
             patch('subprocess.run', return_value=Result()) as query, \
             patch.object(QIcon, 'fromTheme', return_value=QIcon()) as themed:
            default_application_icon(Path('/tmp/example.txt'))
            default_application_icon(Path('/tmp/example.txt'))
            self.assertEqual(query.call_count, 2)
            self.assertEqual(query.call_args.args[0][:2],
                             ['/tmp/mirivue-kio-applications', '--default'])
            self.assertIn('example-viewer', [call.args[0] for call in themed.call_args_list])


if __name__ == '__main__':
    unittest.main()
