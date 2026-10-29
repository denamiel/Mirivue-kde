"""Exercise view scope, real tab gestures, session state and external batches."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from mirivue.app import Window
from mirivue.launch_targets import LaunchRequest, parse_launch_requests
from mirivue.window_instances import route_plan, WindowEndpoint
from mirivue.metadata import remote_entry


class TestDolphinParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['Mirivue-test'])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='mirivue-parity-')
        self.root = Path(self.temporary.name)
        self.folders = [self.root/name for name in ('alpha', 'beta', 'gamma', 'delta')]
        for folder in self.folders:
            folder.mkdir()
            (folder/'note.txt').write_text('test')
        self.settings = QSettings(str(self.root/'settings.ini'), QSettings.Format.IniFormat)
        self.settings.setValue('window/confirm-close-multiple-tabs', False)
        self.settings.setValue('startup/allow_multiple_instances', False)
        self.patcher = patch('mirivue.app.mirivue_settings', return_value=self.settings)
        self.patcher.start()
        self.windows = []
        self.window = self.new_window()
        self.window.prepare_startup_browsing(str(self.folders[0]))
        self.window.start_browsing()
        self.settle()

    def new_window(self):
        window = Window()
        self.windows.append(window)
        window.show()
        self.app.processEvents()
        return window

    def settle(self):
        until = time.monotonic()+8
        while time.monotonic() < until:
            self.app.processEvents()
            for window in self.windows:
                window.capture_pane()
            if not any(p.scanning for w in self.windows for tab in w._tabs for p in tab.panes):
                QTest.qWait(10)
                return
            QTest.qWait(5)
        # Keep the 8 s limit. Capture the stalled worker/state instead of hiding
        # the failure with a longer wait; artifacts survive the isolated run.
        import faulthandler
        trace = Path(os.environ.get('MIRIVUE_TEST_ARTIFACT_DIR', tempfile.gettempdir()))/'mirivue-startup-timeout.txt'
        trace.parent.mkdir(parents=True, exist_ok=True)
        with trace.open('w') as output:
            faulthandler.dump_traceback(file=output, all_threads=True)
            for window in self.windows:
                for tab in window._tabs:
                    for pane in tab.panes:
                        worker = pane.worker
                        output.write(str(dict(folder=str(pane.folder), scanning=pane.scanning,
                            running=worker.isRunning() if worker else None,
                            preliminary=len(pane.model.pending_preliminary),
                            resolved=len(pane.model.pending_resolved)))+'\n')
        self.fail('A directory listing did not finish; diagnostics: '+str(trace))

    def tearDown(self):
        self.settings.setValue('window/confirm-close-multiple-tabs', False)
        for window in reversed(self.windows):
            window.quit_requested = True
            window.close()
            deadline = time.monotonic()+8
            while window.runtime_tasks.running() and time.monotonic()<deadline:
                QTest.qWait(5)
            window.close()
            self.app.processEvents()
        self.patcher.stop()
        self.temporary.cleanup()

    def test_common_style_ignores_but_preserves_old_folder_overrides(self):
        target = str(self.folders[1])
        old = {target: {'mode': 1, 'hidden': False, 'previews': False}}
        self.settings.setValue('view/folder-styles-v1', old)
        self.settings.setValue('view/folder-modes-v1', {target: 1})
        self.window.change_view(0)
        self.window.hidden.setChecked(True)
        self.settle()
        self.window.preview_action.setChecked(True)
        self.window.zoom_details(1)
        size = self.window.table.iconSize()
        self.window.navigate(target)
        self.settle()
        self.assertEqual(self.window.content_stack.currentIndex(), 0)
        self.assertTrue(self.window.hidden.isChecked())
        self.assertTrue(self.window.model.show_thumbnails)
        self.assertEqual(self.window.table.iconSize(), size)
        self.assertEqual(self.settings.value('view/folder-styles-v1'), old)
        self.settings.setValue('view/remember-per-folder', True)
        self.window.restore_folder_view(target)
        self.assertEqual(self.window.content_stack.currentIndex(), 1)
        self.assertFalse(self.window.hidden.isChecked())
        self.assertFalse(self.window.model.show_thumbnails)

    def test_folder_styles_are_opt_in_for_all_display_choices(self):
        self.settings.setValue('view/remember-per-folder', True)
        self.window.change_view(2)
        self.window.hidden.setChecked(True)
        self.settle()
        self.window.preview_action.setChecked(True)
        self.window.navigate(str(self.folders[1]))
        self.settle()
        self.window.change_view(0)
        self.window.navigate(str(self.folders[0]))
        self.settle()
        self.assertEqual(self.window.content_stack.currentIndex(), 2)
        self.assertTrue(self.window.hidden.isChecked())
        self.assertTrue(self.window.model.show_thumbnails)

    def test_folder_open_inserts_after_current_but_ctrl_t_appends(self):
        for folder in self.folders[1:3]:
            self.window.open_new_tab(str(folder))
            self.settle()
        self.window.tab_bar.setCurrentIndex(0)
        pane = self.window.open_new_tab(str(self.folders[3]), active=False)
        self.assertIs(self.window._tabs[1].bound, pane)
        self.assertEqual(self.window._active_tab, 0)
        self.window.new_tab_action.trigger()
        self.settle()
        self.assertEqual(self.window._active_tab, len(self.window._tabs)-1)

    def test_close_returns_to_last_viewed_tab_even_after_reordering(self):
        for folder in self.folders[1:3]:
            self.window.open_new_tab(str(folder))
            self.settle()
        self.window.tab_bar.setCurrentIndex(0)
        previous = self.window._tabs[0]
        self.window.tab_bar.setCurrentIndex(2)
        self.window.tab_bar.moveTab(0, 1)
        self.window.close_tab(self.window._active_tab)
        self.assertIs(self.window._tabs[self.window._active_tab], previous)

    def test_real_middle_click_closes_and_double_click_opens_tab(self):
        self.window.open_new_tab(str(self.folders[1]))
        self.settle()
        bar = self.window.tab_bar
        QTest.mouseClick(bar, Qt.MouseButton.MiddleButton, pos=bar.tabRect(0).center())
        self.assertEqual(bar.count(), 1)
        self.window.open_new_tab(str(self.folders[2]))
        self.settle()
        location = self.window.folder
        QTest.mouseDClick(bar, Qt.MouseButton.LeftButton, pos=bar.tabRect(bar.currentIndex()).center())
        self.settle()
        self.assertEqual(bar.count(), 3)
        self.assertEqual(self.window.folder, location)

    def test_context_menu_rename_split_title_and_detach_failure(self):
        self.window.set_split_view(True, navigate_new=False)
        self.window.run_in_pane(self.window.panes[1], self.window.navigate, str(self.folders[1]))
        self.settle()
        self.assertIn('alpha | (beta)', self.window.tab_bar.tabText(0))
        self.window.activate_pane(self.window.panes[1])
        self.assertIn('(alpha) | beta', self.window.tab_bar.tabText(0))
        self.window.rename_tab(0, 'Films & séries')
        self.assertEqual(self.window.tab_bar.tabText(0), 'Films && séries')
        self.window.navigate(str(self.folders[2]))
        self.settle()
        self.assertEqual(self.window.tab_bar.tabText(0), 'Films && séries')
        menu = self.window.tab_bar.create_context_menu(0)
        labels = [a.text() for a in menu.actions()]
        self.assertIn('Fermer les onglets à droite', labels)
        self.assertIn('Renommer l’onglet…', labels)
        with patch.object(self.window, 'open_requests_in_new_window', return_value=False) as spawn:
            self.window.detach_tab(0)
            self.assertEqual(len(self.window._tabs), 1)
            self.assertEqual(spawn.call_args.kwargs['detached_tab']['title'], 'Films & séries')
        menu.deleteLater()

    def test_session_roundtrip_preserves_tabs_split_active_pane_and_names(self):
        self.window.set_split_view(True, navigate_new=False)
        self.window.run_in_pane(self.window.panes[1], self.window.navigate, str(self.folders[1]))
        self.window.activate_pane(self.window.panes[1])
        self.window.rename_tab(0, 'Médias')
        self.window.open_new_tab(str(self.folders[2]))
        self.settle()
        self.window.tab_bar.setCurrentIndex(0)
        self.settings.setValue('startup/location', 'session')
        self.window.save_tab_session()
        snapshot = self.window.session_snapshot()
        reopened = self.new_window()
        reopened.prepare_startup_browsing()
        reopened.start_browsing()
        self.settle()
        restored = reopened.session_snapshot()
        for before, after in zip(snapshot['tabs'], restored['tabs']):
            old_widths, new_widths = before.pop('widths'), after.pop('widths')
            self.assertEqual(before, after)
            if old_widths and new_widths:
                self.assertAlmostEqual(old_widths[0]/sum(old_widths), new_widths[0]/sum(new_widths), places=2)
        self.assertEqual(restored['active'], snapshot['active'])
        self.assertEqual(reopened.folder, str(self.folders[1]))
        self.assertTrue(reopened.split_enabled)
        self.assertEqual(reopened.tab_bar.tabText(0), 'Médias')

    def test_explicit_startup_location_does_not_restore_session(self):
        self.settings.setValue('startup/location', 'session')
        self.window.open_new_tab(str(self.folders[1]))
        self.settle()
        self.window.save_tab_session()
        reopened = self.new_window()
        reopened.prepare_startup_browsing(str(self.folders[3]))
        self.assertEqual(len(reopened._tabs), 1)
        self.assertEqual(reopened.folder, str(self.folders[3]))

    def test_close_dialog_offers_current_tab_and_session_skips_question(self):
        self.window.open_new_tab(str(self.folders[1]))
        self.settle()
        self.settings.setValue('window/confirm-close-multiple-tabs', True)
        def choose_current():
            box = self.app.activeModalWidget()
            self.assertIsInstance(box, QMessageBox)
            buttons = {b.text(): b for b in box.buttons()}
            self.assertIn('Fermer la fenêtre', buttons)
            buttons['Fermer l’onglet courant'].click()
        QTimer.singleShot(0, choose_current)
        self.assertFalse(self.window.confirm_tab_window_close())
        self.assertEqual(len(self.window._tabs), 1)
        self.settings.setValue('startup/location', 'session')
        self.window.open_new_tab(str(self.folders[2]))
        self.settle()
        self.assertTrue(self.window.confirm_tab_window_close())

    def test_multiple_missing_external_folders_launch_one_window(self):
        self.settings.setValue('startup/allow_multiple_instances', True)
        requests = [LaunchRequest(str(p)) for p in self.folders]
        with patch.object(self.window, 'open_requests_in_new_window', return_value=True) as launch:
            self.window.open_external_locations(requests, across_windows=False, activation_token='token')
        self.assertEqual(launch.call_count, 1)
        self.assertEqual([r.folder for r in launch.call_args.args[0]], list(map(str, self.folders[1:])))
        self.assertEqual(launch.call_args.kwargs['activation_token'], 'token')
        self.assertEqual(len(self.window._tabs), 1)

    def test_split_external_batch_constructs_pairs_in_same_tabs(self):
        requests = [LaunchRequest(str(p)) for p in self.folders[1:3]]
        self.window.open_external_locations(requests, across_windows=False, split=True)
        self.settle()
        self.assertEqual(len(self.window._tabs), 2)
        self.assertTrue(self.window.split_enabled)
        self.assertEqual([p.folder for p in self.window.panes], list(map(str, self.folders[1:3])))

    def test_global_route_finds_each_window_including_detached(self):
        requests = [LaunchRequest(str(p)) for p in self.folders]
        routes, missing = route_plan(requests, [('primary', [str(self.folders[0])]),
                                                 ('detached', [str(self.folders[2])])])
        self.assertEqual(routes['detached'], [requests[2]])
        self.assertEqual(missing, [requests[1], requests[3]])
        endpoint = WindowEndpoint(self.window)
        self.assertEqual(json.loads(endpoint.Locations()), [str(self.folders[0])])

    def test_select_directories_and_session_argument_are_not_misparsed(self):
        requests = parse_launch_requests(['--select', str(self.folders[1]), '--session-tab', '{"x":1}'])
        self.assertEqual(requests, (LaunchRequest(str(self.root), (str(self.folders[1]),)),))

    def test_special_folder_columns_use_kio_dates_and_restore_normal_columns(self):
        normal = [c for c in range(self.window.model.columnCount()) if not self.window.table.isColumnHidden(c)]
        self.window.restore_folder_view('trash:/')
        self.assertEqual([c for c in range(self.window.model.columnCount()) if not self.window.table.isColumnHidden(c)], [0, 37, 39])
        row = remote_entry('trash:/film.mkv', 'film.mkv', modified=10, accessed=20,
                           original_path='/media/videos/film.mkv', deleted='2026-10-23T12:00:00')
        self.assertEqual(row.values[37], '/media/videos')
        self.assertGreater(row.sort_values[39], 0)
        self.assertEqual(row.sort_values[38], 20_000_000_000)
        self.window.restore_folder_view(str(self.folders[0]))
        self.assertEqual([c for c in range(self.window.model.columnCount()) if not self.window.table.isColumnHidden(c)], normal)

    def test_serialized_window_batch_preserves_mixed_folders_and_selected_files(self):
        from mirivue.window_instances import request_payload
        requests = [LaunchRequest(str(self.folders[0]), (str(self.folders[0]/'note.txt'),)),
                    LaunchRequest(str(self.folders[1]))]
        result = parse_launch_requests(['--new-window', '--locations-json', json.dumps(request_payload(requests))])
        self.assertEqual(list(result), requests)

    def test_recent_dates_are_grouped_by_the_native_dolphin_engine(self):
        from mirivue.metadata import Video
        from PySide6.QtCore import QDateTime
        now = QDateTime.currentDateTime().toSecsSinceEpoch()
        rows = [remote_entry('recentlyused:/new.txt', 'new.txt', accessed=now),
                remote_entry('recentlyused:/old.txt', 'old.txt', accessed=now-8*86400)]
        self.window.set_initial_listing(rows)
        self.window.restore_folder_view('recentlyused:/files')
        self.app.processEvents()
        backend = self.window.table._backend
        backend.configure()
        groups = backend.query(op='groups')['groups']
        self.assertEqual([g['row'] for g in groups], [0, 1])
        self.assertTrue(all(g['label'] for g in groups))
        self.assertEqual(self.window.table.horizontalHeader().sortIndicatorSection(), 38)
        self.assertFalse(self.window.proxy.folders_first)
        self.assertEqual(backend.query(op='groups')['groups'], groups)

    def test_visiting_trash_does_not_replace_the_saved_media_column_layout(self):
        pane = self.window.bound_pane
        # Exact byte comparison is meaningful for a fixed custom layout.
        # Automatic widths are allowed to change while Qt processes layouts.
        self.window.set_pane_fill_view_width(pane, False)
        self.window.set_pane_column_width_mode(pane, 'custom')
        header = self.window.table.horizontalHeader()
        header.resizeSection(0, 333)
        self.app.processEvents()
        normal = bytes(header.saveState())
        def layout():
            return ([(header.isSectionHidden(c), header.sectionSize(c), header.visualIndex(c))
                     for c in range(header.count())],
                    header.sortIndicatorSection(), header.sortIndicatorOrder())
        normal_layout = layout()
        self.window.folder = 'trash:/'
        self.window.restore_folder_view('trash:/')
        self.window.save_pane_column_state(self.window.bound_pane)
        self.assertEqual(bytes(self.settings.value('columns-pane-left-v1')), normal)
        self.window.folder = str(self.folders[0])
        self.window.restore_folder_view(self.window.folder)
        self.assertEqual(layout(), normal_layout)

    def test_old_column_state_does_not_expose_new_special_columns(self):
        from PySide6.QtWidgets import QTableWidget
        old = QTableWidget(0, 37)
        for c in range(1, 37):
            old.setColumnHidden(c, c not in (1, 2, 14))
        state = old.horizontalHeader().saveState()
        self.settings.setValue('columns-pane-left-v1', state)
        self.settings.setValue('columns-pane-right-v1', state)
        reopened = self.new_window()
        reopened.prepare_startup_browsing(str(self.folders[0]))
        reopened.set_split_view(True, navigate_new=False)
        for pane in reopened.panes:
            self.assertTrue(all(pane.table.isColumnHidden(c) for c in (37, 38, 39)))
        old.deleteLater()

    def test_hidden_last_and_sorting_modes_apply_in_all_three_views(self):
        for name in ('A10', 'a2', '.hidden'):
            (self.folders[0]/name).write_text('file')
        self.window.hidden.setChecked(True)
        self.settle()
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            self.window.set_sorting_options(0, True)
            for direction in (Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder):
                self.window.table.sortByColumn(0, direction)
                names = [self.window.proxy.index(r,0).data() for r in range(self.window.proxy.rowCount())]
                self.assertEqual(names[-1], '.hidden')
            self.window.set_sorting_options(1, False)
            self.window.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
            names = [self.window.proxy.index(r,0).data() for r in range(self.window.proxy.rowCount())]
            self.assertLess(names.index('A10'), names.index('a2'))
