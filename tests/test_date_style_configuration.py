"""Date controls, persistence and native KFormat delegation with real Qt forms."""
import ctypes
import os
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QSignalSpy
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWidget, QGroupBox, QRadioButton
from mirivue.configuration import ConfigurationDialog
from mirivue.app import Window, VideoModel
from mirivue.date_display import modification_text
from mirivue.platform_services import services


class ContextFixture(QWidget):
    """Keep this date test from writing the shared KDE service settings."""
    def __init__(self, owner, parent=None): super().__init__(parent)
    def apply(self): return True
    def searchable_labels(self): return []


class Owner(QWidget):
    """Controlled application API; all configuration widgets/actions are real."""
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.recent_items = []
        self.startup_split_action = QAction(self)
        self.startup_split_action.setCheckable(True)
        self.preview_action = QAction(self)
        self.preview_action.setCheckable(True)
        self.preview_dock = QWidget(self)
        self.panes = []
        for _ in range(2):
            model = VideoModel()
            stamp = time.time_ns() - 1800 * 1_000_000_000
            values = [0] * model.columnCount()
            values[14] = stamp
            model.rows = [SimpleNamespace(modified_ns=stamp, accessed_ns=stamp, deleted_ns=None,
                                          sort_values=values, is_dir=False)]
            self.panes.append(SimpleNamespace(model=model))
    def profile_names(self): return ['Test']
    def profile_definitions(self): return {'Test': {0, 1}}
    def default_profile(self, name): return {0, 1}
    def clear_recents(self): self.recent_items.clear()
    def set_date_format(self, mode): Window.set_date_format(self, mode)
    def set_sorting_options(self, *args): pass
    def apply_tab_bar_settings(self): pass
    def set_folders_first(self, *args, **kwargs): pass
    def set_folder_size_display(self, *args): pass
    def set_recent_media_enabled(self, *args): pass
    def set_theme(self, *args): pass
    def save_profile_definitions(self, *args): pass
    def schedule_media_preview(self): pass


class TestDateStyleConfiguration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = QSettings(str(Path(self.temp.name) / 'settings.ini'), QSettings.Format.IniFormat)
        self.owner = Owner(self.settings)
        self.dialogs = []
    def tearDown(self):
        for dialog in self.dialogs:
            dialog.search_timer.stop()
            dialog.close()
        self.owner.close()
        self.app.processEvents()
        self.temp.cleanup()
    def dialog(self):
        with patch('mirivue.context_menu_settings.ContextMenuPage', ContextFixture):
            dialog = ConfigurationDialog(self.owner)
        self.dialogs.append(dialog)
        return dialog

    def test_two_native_radios_are_under_general_display_and_not_columns(self):
        dialog = self.dialog()
        general, columns = dialog.pages.widget(0), dialog.pages.widget(1)
        group = next(g for g in general.findChildren(QGroupBox) if g.title() == 'Affichage')
        radios = group.findChildren(QRadioButton)
        self.assertEqual(len(radios), 2)
        self.assertTrue(dialog.date_relative.text().startswith('Relative (Par exemple « '))
        self.assertTrue(dialog.date_absolute.text().startswith('Absolue (Par exemple « '))
        self.assertTrue(group.isAncestorOf(dialog.date_relative))
        self.assertFalse(columns.isAncestorOf(dialog.date_relative))
        self.assertFalse(any('date' in g.title().lower() for g in columns.findChildren(QGroupBox)))
        dialog.date_relative.setChecked(True)
        self.assertFalse(dialog.date_absolute.isChecked())
        dialog.category_search.setText('Style de date')
        dialog.filter_categories()
        self.assertFalse(dialog.categories.isRowHidden(0))
        self.assertTrue(dialog.categories.isRowHidden(1))

    def test_apply_persists_each_choice_and_reopening_reads_it(self):
        for mode in ('informal', 'locale'):
            with self.subTest(mode=mode):
                dialog = self.dialog()
                (dialog.date_relative if mode == 'informal' else dialog.date_absolute).setChecked(True)
                spies = [QSignalSpy(pane.model.dataChanged) for pane in self.owner.panes]
                self.assertTrue(dialog.apply())
                self.assertEqual(self.settings.value('view/date-format'), mode)
                for pane, spy in zip(self.owner.panes, spies):
                    model = pane.model
                    stamp = model.rows[0].modified_ns
                    self.assertEqual(model.date_format, mode)
                    self.assertEqual(spy.count(), 2)
                    self.assertEqual(model.data(model.index(0, 14)), modification_text(stamp, mode=mode))
                    self.assertEqual(model.data(model.index(0, 14), Qt.ItemDataRole.UserRole), stamp)
                reopened = self.dialog()
                self.assertEqual(reopened.date_relative.isChecked(), mode == 'informal')

    def test_cancel_preserves_an_existing_choice_including_legacy_iso(self):
        for mode in ('informal', 'locale', 'iso'):
            with self.subTest(mode=mode):
                self.settings.setValue('view/date-format', mode)
                dialog = self.dialog()
                self.assertEqual(dialog.date_relative.isChecked(), mode == 'informal')
                dialog.date_relative.setChecked(not dialog.date_relative.isChecked())
                dialog.reject()
                self.assertEqual(self.settings.value('view/date-format'), mode)

    def test_legacy_iso_becomes_absolute_only_when_applying(self):
        self.settings.setValue('view/date-format', 'iso')
        dialog = self.dialog()
        self.assertTrue(dialog.date_absolute.isChecked())
        self.assertEqual(self.settings.value('view/date-format'), 'iso')
        self.assertTrue(dialog.apply())
        self.assertEqual(self.settings.value('view/date-format'), 'locale')

    def test_relative_rendering_uses_the_native_formatter(self):
        path = os.environ.get('MIRIVUE_TEST_DATE_LIBRARY') or os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY')
        if not path:
            self.skipTest('Native library is built by Valider')
        library = ctypes.CDLL(path)
        formatter = library.mirivue_format_relative_date
        formatter.argtypes = [ctypes.c_longlong, ctypes.c_void_p, ctypes.c_size_t]
        formatter.restype = ctypes.c_int
        with patch.object(services, '_icon_theme_library', library):
            dialog = self.dialog()
            example = modification_text(time.time_ns() - 1800 * 1_000_000_000, mode='informal')
            self.assertIn(example, dialog.date_relative.text())
            for age in (30 * 60, 86400, 30 * 86400):
                timestamp = time.time_ns() - age * 1_000_000_000
                output = ctypes.create_string_buffer(4096)
                self.assertGreater(formatter(timestamp // 1_000_000, output, len(output)), 0)
                self.assertEqual(modification_text(timestamp, mode='informal'), output.value.decode())
