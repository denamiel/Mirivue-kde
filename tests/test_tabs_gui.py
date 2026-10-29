"""Offscreen navigation smoke test; run on a system with PySide6 installed."""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class TestIndependentTabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['Mirivue-test'])

    def test_history_arrow_menu_uses_active_pane(self):
        from mirivue.app import Window

        with tempfile.TemporaryDirectory(prefix='mirivue-history-') as temp:
            first, second = Path(temp, 'first'), Path(temp, 'second')
            first.mkdir()
            second.mkdir()
            settings = QSettings(str(Path(temp, 'settings.ini')), QSettings.Format.IniFormat)
            # This test finishes with two tabs. Suppress the confirmation
            # dialog, which cannot be dismissed in the offscreen test run.
            settings.setValue('window/confirm-close-multiple-tabs', False)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
            try:
                def settle():
                    until = time.monotonic() + 5
                    while window.scanning and time.monotonic() < until:
                        self.app.processEvents()
                    self.assertFalse(window.scanning)

                window.prepare_startup_browsing(str(first))
                window.navigate(str(second))
                settle()
                window.populate_navigation_history(window.back_history_menu, -1)
                actions = window.back_history_menu.actions()
                self.assertEqual(len(actions), 1)
                self.assertEqual(actions[0].toolTip(), str(first))
                actions[0].trigger()
                settle()
                self.assertEqual(window.folder, str(first))
                window.populate_navigation_history(window.forward_history_menu, 1)
                self.assertEqual(window.forward_history_menu.actions()[0].toolTip(), str(second))
                window.open_new_tab(str(second))
                window.populate_navigation_history(window.back_history_menu, -1)
                self.assertFalse(window.back_history_menu.actions())
                window.tab_bar.setCurrentIndex(0)
                window.populate_navigation_history(window.forward_history_menu, 1)
                self.assertEqual(window.forward_history_menu.actions()[0].toolTip(), str(second))
            finally:
                window.quit_requested = True
                window.close()

    def test_tabs_keep_navigation_split_and_search_state(self):
        from mirivue.app import Window

        with tempfile.TemporaryDirectory(prefix='mirivue-tabs-') as temp:
            left = Path(temp, 'gauche')
            right = Path(temp, 'droite')
            left.mkdir()
            right.mkdir()
            # A user's startup/split preference must not determine the test's
            # initial layout or be changed by a test run.
            settings = QSettings(str(Path(temp, 'settings.ini')), QSettings.Format.IniFormat)
            settings.setValue('window/confirm-close-multiple-tabs', False)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
            try:
                window.prepare_startup_browsing(str(left))
                self.assertEqual(len(window.panes), 1)
                window.open_new_tab(str(right))
                self.assertEqual(window.tab_bar.count(), 2)
                self.assertEqual(window.folder, str(right))
                window.set_split_view(True, navigate_new=False)
                self.assertEqual(len(window.panes), 2)
                window.tab_bar.setCurrentIndex(0)
                self.assertEqual(window.folder, str(left))
                self.assertFalse(window.split_enabled)
                window.tab_bar.setCurrentIndex(1)
                self.assertTrue(window.split_enabled)
                self.assertEqual(window.folder, str(right))
                window.open_external_location(str(left))
                until = time.monotonic() + 5
                while window.folder != str(left) and time.monotonic() < until:
                    self.app.processEvents()
                self.assertEqual(window.tab_bar.count(), 2)
                self.assertEqual(window.folder, str(left))
                window.tab_bar.setCurrentIndex(1)
                self.assertEqual(window.folder, str(right))
                window.tab_bar.setCurrentIndex(0)
                until = time.monotonic() + 5
                while any(p.scanning for tab in window._tabs for p in tab.panes) and time.monotonic() < until:
                    self.app.processEvents()
                self.assertFalse(any(p.scanning for tab in window._tabs for p in tab.panes))
                window.close_tab(1)
                self.assertEqual(window.tab_bar.count(), 1)
                self.assertEqual(window.folder, str(left))
            finally:
                window.quit_requested = True
                window.close()

    def test_split_width_is_restored_per_tab_and_after_reopening(self):
        from mirivue.app import Window

        def set_active_widths(window, left, right):
            # QSplitter retains the hidden panes of other tabs. Its list of
            # sizes must include every child, not just the two visible panes.
            sizes = [0] * window.pane_splitter.count()
            for pane, width in zip(window.panes, (left, right)):
                sizes[window.pane_splitter.indexOf(pane.container)] = width
            window.pane_splitter.setSizes(sizes)

        def active_widths(window):
            sizes = window.pane_splitter.sizes()
            return [sizes[window.pane_splitter.indexOf(p.container)] for p in window.panes]

        with tempfile.TemporaryDirectory(prefix='mirivue-tab-widths-') as temp:
            settings = QSettings(str(Path(temp, 'settings.ini')), QSettings.Format.IniFormat)
            # This test ends with two tabs open. An offscreen confirmation
            # dialog would wait indefinitely for a click that cannot occur.
            settings.setValue('window/confirm-close-multiple-tabs', False)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                window = Window()
            try:
                window.show()
                window.prepare_startup_browsing(temp)
                window.set_split_view(True, navigate_new=False)
                self.app.processEvents()
                set_active_widths(window, 700, 300)
                self.app.processEvents()
                first = active_widths(window)
                self.assertGreater(first[0], first[1], 'initial sizing of tab 1')
                window.schedule_pane_splitter_save()
                window.open_new_tab(temp)
                window.set_split_view(True, navigate_new=False)
                self.app.processEvents()
                set_active_widths(window, 300, 700)
                self.app.processEvents()
                second = active_widths(window)
                self.assertLess(second[0], second[1], 'initial sizing of tab 2')
                window.schedule_pane_splitter_save()
                window.tab_bar.setCurrentIndex(0)
                self.app.processEvents()
                active = active_widths(window)
                self.assertGreater(active[0], active[1], 'tab 1 after switching')
                window.tab_bar.setCurrentIndex(1)
                self.app.processEvents()
                active = active_widths(window)
                self.assertLess(active[0], active[1], 'tab 2 after switching')
                window.set_split_view(False)
                window.set_split_view(True, navigate_new=False)
                self.app.processEvents()
                active = active_widths(window)
                self.assertLess(active[0], active[1], 'tab 2 after toggling split view')
                until = time.monotonic() + 5
                while any(p.scanning for tab in window._tabs for p in tab.panes) and time.monotonic() < until:
                    self.app.processEvents()
                self.assertFalse(any(p.scanning for tab in window._tabs for p in tab.panes))
                window.close_tab(1)
                window.reopen_closed_tab()
                self.app.processEvents()
                active = active_widths(window)
                self.assertLess(active[0], active[1], 'tab 2 after reopening')
            finally:
                window.quit_requested = True
                window.close()

    def test_places_width_survives_restart_and_hidden_panel(self):
        from mirivue.app import Window

        with tempfile.TemporaryDirectory(prefix='mirivue-places-width-') as temp:
            settings = QSettings(str(Path(temp, 'settings.ini')), QSettings.Format.IniFormat)
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                first = Window()
            try:
                first.show()
                self.app.processEvents()
                first.main_splitter.setSizes([350, 650])
                self.app.processEvents()
                first.schedule_sidebar_width_save()
                first.set_places_panel_visible(False)
                self.assertGreater(first.main_splitter.sizes()[-1], 0)
                saved = int(settings.value('panes/sidebar-width-v1'))
                self.assertGreater(saved, 250)
            finally:
                first.quit_requested = True
                first.close()
            with patch('mirivue.app.mirivue_settings', return_value=settings):
                second = Window()
            try:
                second.show()
                self.app.processEvents()
                self.assertAlmostEqual(second.main_splitter.sizes()[0], saved, delta=15)
            finally:
                second.quit_requested = True
                second.close()


if __name__ == '__main__':
    unittest.main()
