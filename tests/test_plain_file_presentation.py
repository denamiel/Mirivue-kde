"""Plain KDE file text, retired status column and media-specific diagnostics."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from mirivue.app import Window, VideoModel, media_missing_fields
from mirivue.configuration import ConfigurationDialog
from mirivue.metadata import Video, HEADERS
from mirivue.column_groups import PRIMARY_COLUMNS, MEDIA_COLUMNS
from mirivue import library


class TestPlainFilePresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def media(self, kind='audio'):
        row = Video(Path('/tmp/media.flac'), media_type=kind, is_video=(kind == 'video'), metadata_loaded=True)
        row.values[0] = row.path.name
        row.sort_values[2] = 100
        row.sort_values[8] = 'flac'
        row.media_technical = {'bitrate': 800000}
        return row

    def test_audio_checks_audio_codec_and_bitrate_without_visual_properties(self):
        row = self.media()
        self.assertEqual(media_missing_fields(row), [])
        row.sort_values[8] = ''
        self.assertEqual(media_missing_fields(row), ['codec'])
        row.sort_values[8] = 'flac'
        row.media_technical.clear()
        self.assertEqual(media_missing_fields(row), ['débit'])
        row.sort_values[25] = 800000
        self.assertEqual(media_missing_fields(row), [])

    def test_video_and_image_keep_their_relevant_checks(self):
        row = self.media('video')
        self.assertEqual(set(media_missing_fields(row)), {'résolution', 'codec', 'FPS', 'débit'})
        row.media_technical.update(width=1920, height=1080)
        row.sort_values[4], row.sort_values[5], row.sort_values[6] = 'h264', 25, 1000000
        self.assertEqual(media_missing_fields(row), [])
        row.media_type, row.is_video = 'image', False
        row.sort_values[2] = -1
        row.sort_values[4] = ''
        self.assertEqual(media_missing_fields(row), [])
        row.metadata_loaded = False
        self.assertEqual(media_missing_fields(row), [])

    def test_name_text_always_uses_the_theme_and_details_remain_in_tooltip(self):
        row = self.media()
        row.error = 'Erreur précise de lecture'
        row.personal_label = 'À trier'
        row.duplicate_group = 3
        row.values[10] = 'OK • Doublon groupe 3 • À trier'
        model = VideoModel()
        model.add(row)
        model.operation_state = lambda path, column: 'En attente'
        for column in (0, 2, 10):
            self.assertIsNone(model.data(model.index(0, column), Qt.ItemDataRole.ForegroundRole))
        tooltip = model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole)
        self.assertIn('Erreur précise de lecture', tooltip)
        self.assertIn('Étiquette : À trier', tooltip)
        self.assertEqual(tooltip.count('Doublon groupe 3'), 1)
        self.assertNotIn('résolution', tooltip)

    def test_status_cannot_return_through_profiles_or_legacy_header_state(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(directory+'/settings.ini', QSettings.Format.IniFormat)
            settings.setValue('media/start-preview-panel', False)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
            window.show()
            self.application.processEvents()
            try:
                self.assertIsNone(window.column_actions[10])
                self.assertEqual(HEADERS[10], '')
                offered = set(PRIMARY_COLUMNS)
                for _label, columns in MEDIA_COLUMNS:
                    offered.update(columns)
                self.assertNotIn(10, offered)
                # Simulate a header saved by RC170, where State was visible.
                header = window.table.horizontalHeader()
                header.setSectionHidden(10, False)
                header.setSortIndicator(10, Qt.SortOrder.DescendingOrder)
                old_state = header.saveState()
                header.restoreState(old_state)
                self.assertTrue(window.table.isColumnHidden(10))
                self.assertEqual(header.sortIndicatorSection(), 0)
                window.table.sortByColumn(10, Qt.SortOrder.DescendingOrder)
                self.assertEqual(header.sortIndicatorSection(), 0)
                for profile in window.profile_names():
                    window.apply_media_profile(profile, save=False)
                    window.table.setColumnHidden(10, False)
                    self.assertTrue(window.table.isColumnHidden(10))
                library.write(settings, 'media/profile-definitions', {'Personnel': [0, 10, 14]})
                self.assertNotIn(10, window.profile_definitions()['Personnel'])
                dialog = ConfigurationDialog(window)
                try:
                    self.assertNotIn(10, [dialog.profile_columns.item(i).data(Qt.ItemDataRole.UserRole)
                        for i in range(dialog.profile_columns.count())])
                finally:
                    dialog.close()
                window.set_split_view(True, navigate_new=False)
                self.application.processEvents()
                for pane in window.panes:
                    self.assertTrue(pane.table.isColumnHidden(10))
            finally:
                window.quit_requested = True
                window.closing = True
                window.close()
                self.application.processEvents()


if __name__ == '__main__':
    unittest.main()
