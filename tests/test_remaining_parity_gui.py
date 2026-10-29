"""Real listings, native painting roles and tab lifetimes, not source matching."""
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from mirivue.app import Scanner, KioScanner
from mirivue.background_listing import RecursiveSearchWorker
from mirivue.configuration import ConfigurationDialog
from mirivue.metadata import basic_entry
import test_dolphin_parity_gui as parity


class DelayedScanner(Scanner):
    """Deliver a deliberately late batch even after cooperative cancellation."""
    def __init__(self, *args):
        super().__init__(*args)
        self.release = threading.Event()

    def run(self):
        self.release.wait(4)
        self.initial.emit([basic_entry(Path(self.folder) / 'note.txt')])


class TestRemainingParity(unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    def settle(self):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.app.processEvents()
            # The bound pane's live fields are held by Window until capture.
            for window in self.windows:
                window.capture_pane()
            if not any(p.scanning for w in self.windows for tab in w._tabs for p in tab.panes):
                QTest.qWait(15)
                return
            QTest.qWait(5)
        self.fail('A directory listing did not finish')

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(predicate())

    def names(self, worker, signal='initial'):
        rows = []
        getattr(worker, signal).connect(rows.extend)
        worker.run()
        return rows

    def hidden_files(self):
        root = self.folders[0]
        (root/'secret.txt').write_text('hidden')
        (root/'.dot.txt').write_text('hidden')
        (root/'secret folder').mkdir()
        (root/'secret folder'/'nested.txt').write_text('hidden')
        (root/' name with spaces ').write_text('hidden')
        (root/'.hidden').write_text('secret.txt\nsecret folder\n name with spaces \n')
        return root

    def test_local_listing_hides_dot_hidden_members_and_their_children(self):
        root = self.hidden_files()
        rows = self.names(Scanner(str(root), False, False))
        self.assertEqual([r.path.name for r in rows], ['note.txt'])
        search = self.names(RecursiveSearchWorker(root, '', show_hidden=False), 'listed')
        self.assertEqual([r.path.name for r in search], ['note.txt'])

    def test_hidden_members_have_a_native_painting_role_in_all_views(self):
        root = self.hidden_files()
        self.window.hidden.setChecked(True)
        self.settle()
        for row in self.window.model.rows:
            position = self.window.model.rows.index(row)
            hidden = row.path.name != 'note.txt'
            self.assertEqual(self.window.model.index(position, 0).data(Qt.ItemDataRole.UserRole + 44), hidden)
        self.window.set_sorting_options(0, True)
        for order in (Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder):
            self.window.proxy.sort(0, order)
            self.assertEqual(self.window.proxy.index(0, 0).data(), 'note.txt')
        for mode, view in enumerate((self.window.table, self.window.icons, self.window.compact)):
            self.window.change_view(mode)
            backend = view._backend
            self.assertTrue(backend is not None)
            for index in range(self.window.proxy.rowCount()):
                expected = self.window.proxy.index(index, 0).data() != 'note.txt'
                self.assertEqual(backend.query(op='item', row=index)['hidden'], expected)

    def test_remote_hidden_status_uses_kio_flag_and_source_url(self):
        entries = [dict(name='Visible label', url='smb://host/share/.secret', hidden=True),
                   dict(name='Hidden by server', url='smb://host/share/plain', hidden=True),
                   dict(name='.Shown by server', url='smb://host/share/shown', hidden=False),
                   dict(name='ordinary', url='smb://host/share/ordinary', hidden=False)]
        with patch('mirivue.app.services.list_kio_location', return_value=entries):
            visible = self.names(KioScanner('smb://host/share', False), 'listed')
            all_rows = self.names(KioScanner('smb://host/share', True), 'listed')
        self.assertEqual([r.values[0] for r in visible], ['.Shown by server', 'ordinary'])
        self.assertEqual([r.is_hidden for r in all_rows], [True, True, False, False])

    def test_changes_to_dot_hidden_update_rows_without_resetting_the_model(self):
        root = self.folders[0]
        self.window.watch_visible_directories()
        resets = []
        self.window.model.modelReset.connect(lambda: resets.append(True))
        (root/'.hidden').write_text('note.txt\n')
        self.window.sync_visible_directories()
        self.wait_for(lambda: not self.window.model.rows)
        self.assertFalse(self.window.model.rows)
        (root/'.hidden').unlink()
        self.window.sync_visible_directories()
        self.wait_for(lambda: bool(self.window.model.rows))
        self.assertEqual([r.path.name for r in self.window.model.rows], ['note.txt'])
        self.assertEqual(resets, [])

    def delayed_tab(self, active):
        pane = self.window.open_new_tab(str(self.folders[1]), active=False)
        with patch('mirivue.app.Scanner', DelayedScanner):
            if active:
                self.window.tab_bar.setCurrentIndex(1)
            else:
                self.window.run_in_pane(pane, self.window.navigate, str(self.folders[1]))
        return pane, pane.worker if not active else self.window.worker

    def test_busy_state_belongs_to_pane_before_the_first_worker_signal(self):
        with patch('mirivue.app.Scanner', DelayedScanner):
            self.window.scan()
        worker = self.window.worker
        try:
            self.assertTrue(self.window.bound_pane.scanning)
            self.assertIs(self.window.bound_pane.worker, worker)
        finally:
            worker.release.set()
            self.settle()

    def test_closing_loading_tab_is_immediate_and_ignores_late_signals(self):
        for active in (False, True):
            pane, worker = self.delayed_tab(active)
            try:
                started = time.monotonic()
                self.window.close_tab(1)
                self.assertLess(time.monotonic()-started, .5)
                self.assertEqual(len(self.window._tabs), 1)
                self.assertTrue(worker.isInterruptionRequested())
                touched = []
                self.window.run_in_pane(pane, lambda: touched.append(True))
                self.window.run_in_pane_silent(pane, lambda: touched.append(True))
                self.assertEqual(touched, [])
            finally:
                worker.release.set()
                worker.wait(2000)
                QTest.qWait(30)
            self.assertEqual(self.window.folder, str(self.folders[0]))
            self.assertEqual([r.path.parent for r in self.window.model.rows], [self.folders[0]])

    def test_detaching_loading_tab_only_cancels_after_successful_spawn(self):
        pane, worker = self.delayed_tab(False)
        try:
            with patch.object(self.window, 'open_requests_in_new_window', return_value=False):
                self.window.detach_tab(1)
            self.assertEqual(len(self.window._tabs), 2)
            self.assertFalse(worker.isInterruptionRequested())
            with patch.object(self.window, 'open_requests_in_new_window', return_value=True) as spawn:
                self.window.detach_tab(1)
            self.assertEqual(len(self.window._tabs), 1)
            self.assertEqual(spawn.call_args.kwargs['detached_tab']['locations'], [str(self.folders[1])])
            self.assertTrue(worker.isInterruptionRequested())
        finally:
            worker.release.set()
            worker.wait(2000)
            QTest.qWait(30)

    def test_tab_settings_apply_immediately_and_survive_a_new_window(self):
        dialog = ConfigurationDialog(self.window)
        try:
            dialog.always_show_tabs.setChecked(True)
            dialog.close_buttons_on_tabs.setChecked(False)
            dialog.apply()
            self.assertFalse(self.window.tab_bar.isHidden())
            self.assertFalse(self.window.tab_bar.tabsClosable())
            self.window.open_new_tab(str(self.folders[1]), active=False)
            self.window.close_tab(1)
            self.assertFalse(self.window.tab_bar.isHidden())
            second = self.new_window()
            self.assertFalse(second.tab_bar.isHidden())
            self.assertFalse(second.tab_bar.tabsClosable())
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_places_name_is_shared_by_window_and_tab_and_tab_has_an_icon(self):
        native = type('Places', (), {'location_identity': lambda _, value: ('Mes documents', 'folder-documents')})()
        with patch.object(self.window, 'native_places', native):
            self.window.update_pane_titles()
        self.assertEqual(self.window.windowTitle(), 'Mes documents — Mirivue')
        self.assertEqual(self.window.tab_bar.tabText(0), 'Mes documents')
        self.assertFalse(self.window.tab_bar.tabIcon(0).isNull())

    def test_custom_tab_label_is_not_subject_to_the_automatic_40_character_limit(self):
        title = 'Mon classement personnel ' * 4
        self.window.rename_tab(0, title)
        self.assertEqual(self.window.tab_bar.tabText(0), title)


if __name__ == '__main__':
    unittest.main()
