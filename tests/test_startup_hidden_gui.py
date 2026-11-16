"""Startup hiding wins over saved styles without resetting a live window."""
import json
import os
import subprocess
import sys
import unittest
from mirivue.launch_targets import LaunchRequest
import test_dolphin_parity_gui as parity


class TestStartupHidden(unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle

    def saved_visible_hidden(self, *, enabled=True, per_folder=False):
        for folder in self.folders:
            (folder / '.secret').write_text('hidden')
        self.settings.setValue('view/hide-hidden-on-startup', enabled)
        self.settings.setValue('view/hidden', True)
        self.settings.setValue('view/remember-per-folder', per_folder)
        self.settings.setValue('view/common-style', {'hidden': True})
        self.settings.setValue('view/folder-styles-v1', {
            str(folder): {'hidden': True} for folder in self.folders})

    def assert_hidden(self, pane):
        self.assertFalse(pane.hidden_state)
        if pane.native_navigator is not None:
            self.assertFalse(pane.native_navigator.shows_hidden_folders())
        self.assertNotIn('.secret', [row.path.name for row in pane.model.rows])

    def test_fresh_start_hides_saved_common_and_folder_styles(self):
        for per_folder in (False, True):
            with self.subTest(per_folder=per_folder):
                self.saved_visible_hidden(per_folder=per_folder)
                window = self.new_window()
                window.prepare_startup_browsing(str(self.folders[0]))
                window.start_browsing()
                self.settle()
                self.assert_hidden(window.bound_pane)
                self.assertEqual([r.path.name for r in window.model.rows], ['note.txt'])
                self.assertFalse(window.hidden.isChecked())
                self.assertFalse(window.hidden_action.isChecked())
                self.assertTrue(self.settings.value('view/common-style')['hidden'])

    def test_disabled_option_preserves_saved_visibility(self):
        self.saved_visible_hidden(enabled=False)
        window = self.new_window()
        window.prepare_startup_browsing(str(self.folders[0]))
        window.start_browsing()
        self.settle()
        self.assertTrue(window.hidden.isChecked())
        self.assertIn('.secret', [r.path.name for r in window.model.rows])

    def test_restored_session_hides_all_panes_including_lazy_tabs(self):
        self.saved_visible_hidden(per_folder=True)
        self.settings.setValue('startup/location', 'session')
        self.settings.setValue('session/tabs-v1', json.dumps(dict(version=1, active=1, tabs=[
            dict(locations=list(map(str, self.folders[:2])), split=True, active=0),
            dict(locations=[str(self.folders[2])], split=False, active=0),
        ])))
        window = self.new_window()
        window.prepare_startup_browsing()
        window.start_browsing()
        self.settle()
        self.assert_hidden(window.bound_pane)
        window.tab_bar.setCurrentIndex(0)
        self.settle()
        for pane in window.panes:
            self.assert_hidden(pane)
            self.assertEqual([r.path.name for r in pane.model.rows], ['note.txt'])

    def test_initial_extra_tabs_hide_before_their_first_listing(self):
        self.saved_visible_hidden()
        self.window.open_external_locations([LaunchRequest(str(self.folders[1]))],
            activate_first=False, across_windows=False, startup=True)
        pane = self.window._tabs[1].bound
        self.assert_hidden(pane)
        self.assertFalse(pane.scanning)
        self.window.tab_bar.setCurrentIndex(1)
        self.settle()
        self.assert_hidden(pane)
        self.assertEqual([r.path.name for r in pane.model.rows], ['note.txt'])

    def test_initial_extra_split_tabs_hide_both_sides(self):
        self.saved_visible_hidden()
        self.window.open_external_locations([
            LaunchRequest(str(folder)) for folder in self.folders[1:3]],
            activate_first=False, across_windows=False, split=True, startup=True)
        self.settle()
        for pane in self.window._tabs[1].panes:
            self.assert_hidden(pane)
            self.assertEqual([r.path.name for r in pane.model.rows], ['note.txt'])

    def test_reactivating_an_existing_window_preserves_visibility(self):
        self.saved_visible_hidden()
        self.window.hidden.setChecked(True)
        self.settle()
        self.window.hide()
        self.window.restore_window()
        self.app.processEvents()
        self.assertTrue(self.window.hidden.isChecked())
        self.assertIn('.secret', [r.path.name for r in self.window.model.rows])

    def test_user_can_show_hidden_after_startup(self):
        self.saved_visible_hidden()
        window = self.new_window()
        window.prepare_startup_browsing(str(self.folders[0]))
        window.start_browsing()
        self.settle()
        window.hidden.setChecked(True)
        self.settle()
        self.assertTrue(window.hidden.isChecked())
        self.assertIn('.secret', [r.path.name for r in window.model.rows])

    def test_navigation_and_new_tabs_keep_startup_hiding(self):
        for per_folder in (False, True):
            with self.subTest(per_folder=per_folder):
                self.saved_visible_hidden(per_folder=per_folder)
                window = self.new_window()
                window.prepare_startup_browsing(str(self.folders[0]))
                window.start_browsing()
                self.settle()
                window.navigate(str(self.folders[1]))
                self.settle()
                self.assert_hidden(window.bound_pane)
                window.open_new_tab(str(self.folders[2]))
                self.settle()
                self.assert_hidden(window.bound_pane)
                self.assertTrue(self.settings.value('view/common-style')['hidden'])

    def test_explicit_show_hidden_releases_startup_hiding_for_navigation(self):
        self.saved_visible_hidden()
        window = self.new_window()
        window.prepare_startup_browsing(str(self.folders[0]))
        window.start_browsing()
        self.settle()
        window.hidden.setChecked(True)
        self.settle()
        window.navigate(str(self.folders[1]))
        self.settle()
        self.assertTrue(window.hidden.isChecked())
        self.assertIn('.secret', [r.path.name for r in window.model.rows])

    def test_real_split_command_line_hides_both_initial_folders(self):
        self.saved_visible_hidden()
        self.settings.sync()
        program = r'''
import sys, time, traceback
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
import mirivue.app as module
settings = QSettings(sys.argv.pop(1), QSettings.IniFormat)
module.mirivue_settings = lambda: settings
module.Window.show_first_use_help = lambda self: None
original_exec = QApplication.exec
def checked_exec():
    application = QApplication.instance()
    deadline = time.monotonic() + 7
    def inspect():
        try:
            window = next(w for w in application.topLevelWidgets() if isinstance(w, module.Window))
            if any(p.scanning for p in window.panes):
                assert time.monotonic() < deadline, 'startup listing timed out'
                QTimer.singleShot(10, inspect)
                return
            assert window.split_enabled and len(window.panes) == 2
            for pane in window.panes:
                assert not pane.hidden_state, str(pane.folder)
                if pane.native_navigator is not None:
                    assert not pane.native_navigator.shows_hidden_folders(), str(pane.folder)
                assert [r.path.name for r in pane.model.rows] == ['note.txt']
            print('STARTUP_HIDDEN_OK', flush=True)
            window.quit_requested = True
            window.close()
            application.exit(0)
        except BaseException:
            traceback.print_exc()
            application.exit(1)
    QTimer.singleShot(100, inspect)
    return original_exec()
QApplication.exec = staticmethod(checked_exec)
module.main()
'''
        result = subprocess.run([sys.executable, '-c', program, self.settings.fileName(),
            '--new-window', '--split', *map(str, self.folders[:2])],
            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('STARTUP_HIDDEN_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
