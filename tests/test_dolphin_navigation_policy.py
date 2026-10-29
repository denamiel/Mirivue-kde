"""Exercise navigation, desktop requests and sorting through the real Qt views."""
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QLocale, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mirivue.app import Window, VideoModel, FileSortProxy
from mirivue.launch_targets import LaunchRequest, parse_launch_requests
from mirivue.metadata import basic_entry
from mirivue.natural_sort import natural_name_key, native_comparator


class TestMultipleLaunchTargets(unittest.TestCase):
    def test_external_window_default_migrates_without_changing_existing_choices(self):
        from mirivue.app import mirivue_settings
        for existing, explicit, expected in ((False, None, True), (True, None, False),
                                              (True, False, False), (True, True, True)):
            with self.subTest(existing=existing, explicit=explicit), tempfile.TemporaryDirectory() as temp:
                settings = QSettings(str(Path(temp, 'settings.ini')), QSettings.IniFormat)
                legacy = QSettings(str(Path(temp, 'legacy.ini')), QSettings.IniFormat)
                if existing:
                    settings.setValue('view/mode', 0)
                if explicit is not None:
                    settings.setValue('startup/allow_multiple_instances', explicit)
                with patch('mirivue.app.QSettings', side_effect=lambda org, app:
                           settings if org == 'pdenams' else legacy):
                    current = mirivue_settings()
                self.assertEqual(current.value('startup/allow_multiple_instances', type=bool), expected)

    def test_all_folders_and_file_parents_are_retained_without_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp, 'A'), Path(temp, 'B')
            a.mkdir(); b.mkdir()
            first, second = a/'one.txt', b/'two.txt'
            first.touch(); second.touch()
            requests = parse_launch_requests([str(a), b.as_uri(), str(first), str(second), str(a)])
            self.assertEqual([r.folder for r in requests], [str(a), str(b)])
            self.assertEqual([r.files for r in requests], [(str(first),), (str(second),)])

    def test_show_items_groups_files_and_selected_folders_by_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp, 'A'), Path(temp, 'B')
            a.mkdir(); b.mkdir()
            first, second = a/'one.txt', b/'two.txt'
            first.touch(); second.touch()
            requests = parse_launch_requests([str(first), str(second), str(a)], show_items=True)
            self.assertEqual([r.folder for r in requests], [str(a), str(b), temp])
            self.assertEqual(requests[-1].files, (str(a),))


class TestDolphinNavigationPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mirivue-navigation-')
        self.root = Path(self.temp.name)
        self.a, self.b, self.c = [self.root/name for name in ('A', 'B', 'C')]
        for folder in (self.a, self.b, self.c):
            folder.mkdir()
            (folder/'z.txt').write_bytes(b'1'*42)
            (folder/'a.txt').write_bytes(b'2'*42)
        self.settings = QSettings(str(self.root/'settings.ini'), QSettings.IniFormat)
        self.settings.setValue('window/confirm-close-multiple-tabs', False)
        with patch('mirivue.app.mirivue_settings', return_value=self.settings):
            self.window = Window()
        self.window.show()
        self.window.prepare_startup_browsing(str(self.a))
        self.window.start_browsing()
        self.settle()

    def pending_routes(self):
        # A live desktop bus makes external requests asynchronous. Wait for
        # this window's exchanges, without consulting another desktop window.
        return any(job.window is self.window and not job.done
                   for job in getattr(self.app, '_mirivue_routes', ()))

    def settle(self):
        limit = time.monotonic()+5
        while time.monotonic() < limit:
            self.app.processEvents()
            if not self.pending_routes() and not any(p.scanning for t in self.window._tabs for p in t.panes):
                for _ in range(5): self.app.processEvents()
                return
            QTest.qWait(5)
        self.fail('Folder listing or external routing did not finish')

    def tearDown(self):
        self.window.quit_requested = True
        self.window.close()
        until = time.monotonic()+5
        while (self.window.isVisible() or self.pending_routes()) and time.monotonic() < until:
            self.app.processEvents()
        self.temp.cleanup()

    def assert_sort(self, column, order):
        header = self.window.table.horizontalHeader()
        self.assertEqual((header.sortIndicatorSection(), header.sortIndicatorOrder()), (column, order))
        self.assertEqual((self.window.proxy.sortColumn(), self.window.proxy.sortOrder()), (column, order))

    def test_common_sort_survives_navigation_in_all_three_views(self):
        self.settings.setValue('view/folder-styles-v1', {str(self.b): {'sort': [0, 0]}})
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            self.window.table.sortByColumn(14, Qt.DescendingOrder)
            self.window.navigate(str(self.b)); self.settle()
            self.assert_sort(14, Qt.DescendingOrder)
            self.window.navigate(str(self.a)); self.settle()
            self.assert_sort(14, Qt.DescendingOrder)
        self.assertEqual(self.settings.value('view/folder-styles-v1')[str(self.b)]['sort'], [0, 0])
        self.assertEqual(self.settings.value('sorting/common-sort'), [14, 1])

    def test_per_folder_sort_is_explicit_and_preserves_previous_preferences(self):
        self.settings.setValue('sorting/remember-per-folder', True)
        self.window.table.sortByColumn(1, Qt.DescendingOrder)
        self.window.navigate(str(self.b)); self.settle()
        self.window.table.sortByColumn(0, Qt.AscendingOrder)
        self.window.navigate(str(self.a)); self.settle()
        self.assert_sort(1, Qt.DescendingOrder)
        self.window.navigate(str(self.b)); self.settle()
        self.assert_sort(0, Qt.AscendingOrder)

    def test_repeated_external_request_reuses_the_existing_tab_and_selects_file(self):
        self.window.open_external_location(str(self.b)); self.settle()
        count = self.window.tab_bar.count()
        for mode in (0, 1, 2):
            self.window.tab_bar.setCurrentIndex(0)
            self.window.change_view(mode)
            self.window.tab_bar.setCurrentIndex(1)
            self.window.open_external_location(str(self.a), [self.a/'z.txt']); self.settle()
            self.assertEqual(self.window.tab_bar.count(), count)
            self.assertEqual(self.window._active_tab, 0)
            self.assertEqual(self.window.selected_paths(), [self.a/'z.txt'])
            for view in (self.window.table, self.window.icons, self.window.compact):
                self.assertEqual(len(view.selectionModel().selectedRows()), 1)
        self.window.open_external_location(self.a.as_uri()); self.settle()
        self.assertEqual(self.window.tab_bar.count(), count)

    def test_external_request_can_reuse_the_other_split_pane(self):
        self.window.set_split_view(True, navigate_new=False)
        right = self.window.panes[1]
        self.window.run_in_pane(right, self.window.navigate, str(self.b)); self.settle()
        self.window.open_external_location(str(self.b), [self.b/'a.txt']); self.settle()
        self.assertIs(self.window.bound_pane, right)
        self.assertEqual(self.window.tab_bar.count(), 1)
        self.assertEqual(self.window.selected_paths(), [self.b/'a.txt'])

    def test_window_preference_reuses_open_folders_before_creating_a_window(self):
        self.settings.setValue('startup/allow_multiple_instances', True)
        with patch.object(self.window, 'open_requests_in_new_window') as launch:
            self.window.open_external_location(str(self.a)); self.settle()
            launch.assert_not_called()
            self.window.open_external_location(str(self.b)); self.settle()
            self.assertEqual(launch.call_count, 1)
            self.assertEqual(launch.call_args.args[0], [LaunchRequest(str(self.b))])
        self.assertEqual(self.window.tab_bar.count(), 1)

    def test_multiple_external_folders_open_without_replacing_the_current_folder(self):
        requests = parse_launch_requests([str(self.b), str(self.c), str(self.b)])
        self.window.open_external_locations(requests); self.settle()
        self.assertEqual(self.window.tab_bar.count(), 3)
        self.assertEqual(self.window.folder, str(self.b))
        self.window.tab_bar.setCurrentIndex(2); self.settle()
        self.assertEqual(self.window.folder, str(self.c))

    def test_common_sort_in_split_view_is_applied_on_navigation_without_switching_panes(self):
        self.window.set_split_view(True, navigate_new=False)
        left, right = self.window.panes
        self.window.run_in_pane(right, self.window.navigate, str(self.b)); self.settle()
        self.window.activate_pane(left)
        self.window.table.sortByColumn(14, Qt.DescendingOrder)
        self.window.navigate(str(self.c)); self.settle()
        self.assert_sort(14, Qt.DescendingOrder)
        self.window.activate_pane(right)
        self.window.navigate(str(self.a)); self.settle()
        self.assert_sort(14, Qt.DescendingOrder)
        self.assertEqual(left.folder, str(self.c))

    def test_recalling_a_maximized_window_keeps_it_maximized(self):
        self.window.showMaximized(); self.app.processEvents()
        self.assertTrue(self.window.isMaximized())
        self.window.open_external_location(str(self.a))
        self.app.processEvents()
        self.assertTrue(self.window.isMaximized())
        self.window.showMinimized(); self.app.processEvents()
        self.window.restore_window(); self.app.processEvents()
        self.assertFalse(self.window.isMinimized())
        self.assertTrue(self.window.isMaximized())

    def test_middle_click_keeps_the_original_tab_and_shift_activates_the_new_one(self):
        pane = self.window.bound_pane
        folder = basic_entry(self.b, is_dir=True)
        pane.model.add(folder)
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            for _ in range(5): self.app.processEvents()
            view = self.window.active_view()
            row = next(i for i in range(pane.proxy.rowCount())
                       if pane.proxy.index(i, 0).data() == 'B')
            point = view.visualRect(pane.proxy.index(row, 0)).center()
            QTest.mouseClick(view.viewport(), Qt.MiddleButton, pos=point)
            self.assertEqual(self.window._active_tab, 0)
            self.assertEqual(self.window.folder, str(self.a))
            self.assertEqual(self.window.tab_bar.count(), 2)
            self.window.close_tab(1)
            QTest.mouseClick(view.viewport(), Qt.MiddleButton, Qt.ShiftModifier, pos=point)
            self.settle()
            self.assertEqual(self.window._active_tab, 1)
            self.assertEqual(self.window.folder, str(self.b))
            self.window.tab_bar.setCurrentIndex(0)
            self.window.close_tab(1)


class TestDolphinNameSorting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_native_comparator_is_available_in_a_validated_release(self):
        self.assertIsNotNone(native_comparator(), 'Build the native presentation library first')

    def test_accents_decimals_versions_and_extensions_match_dolphin(self):
        previous = QLocale()
        try:
            QLocale.setDefault(QLocale('fr_FR'))
            cases = [(['zèbre.mkv', 'éclair.mkv', 'abricot.mkv'],
                      ['abricot.mkv', 'éclair.mkv', 'zèbre.mkv']),
                     (['film1.2.mkv', 'film1.10.mkv'], ['film1.10.mkv', 'film1.2.mkv']),
                     (['v1.10.0.mkv', 'v1.2.0.mkv'], ['v1.2.0.mkv', 'v1.10.0.mkv']),
                     (['film10.mkv', 'film2.mkv'], ['film2.mkv', 'film10.mkv'])]
            for names, expected in cases:
                self.assertEqual(sorted(names, key=natural_name_key), expected)
        finally:
            QLocale.setDefault(previous)

    def test_equal_size_and_duration_use_names_even_after_incremental_insertion(self):
        with tempfile.TemporaryDirectory() as temp:
            model = VideoModel()
            proxy = FileSortProxy()
            proxy.setSourceModel(model)
            proxy.setSortRole(Qt.UserRole)
            for name in ('z.txt', 'a.txt', 'm.txt'):
                path = Path(temp, name); path.write_bytes(b'1'*42)
                item = basic_entry(path)
                item.sort_values[2] = 120.0
                model.add(item)
            for column in (1, 2):
                proxy.sort(column, Qt.AscendingOrder)
                self.assertEqual([proxy.index(r, 0).data() for r in range(proxy.rowCount())],
                                 ['a.txt', 'm.txt', 'z.txt'])
                proxy.sort(column, Qt.DescendingOrder)
                self.assertEqual([proxy.index(r, 0).data() for r in range(proxy.rowCount())],
                                 ['z.txt', 'm.txt', 'a.txt'])
