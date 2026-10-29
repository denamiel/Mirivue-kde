"""Regressions in inactive/restored tabs, proved with real native Qt views."""
import json
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from mirivue.launch_targets import LaunchRequest
import test_dolphin_parity_gui as parity


class TestSessionEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['Mirivue-test'])

    setUp = parity.TestDolphinParity.setUp
    tearDown = parity.TestDolphinParity.tearDown
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle

    def saved_tabs(self, active=0):
        self.settings.setValue('startup/location','session')
        self.settings.setValue('session/tabs-v1',json.dumps(dict(version=1,active=active,tabs=[
            dict(locations=list(map(str,self.folders[:2])),split=True,active=0,widths=[170,830],title='Deux panneaux'),
            dict(locations=[str(self.folders[2])],split=False,active=0,widths=None,title='Autre'),
        ])))

    def test_restored_inactive_split_tab_loads_both_panes_when_selected(self):
        self.saved_tabs(active=1)
        restored=self.new_window()
        restored.prepare_startup_browsing()
        restored.start_browsing()
        self.settle()
        restored.tab_bar.setCurrentIndex(0)
        self.settle()
        self.assertTrue(restored.split_enabled)
        for pane in restored.panes:
            self.assertEqual([row.path.name for row in pane.model.rows],['note.txt'])
            self.assertFalse(getattr(pane,'_session_listing_pending',False))

    def test_restored_split_proportions_survive_creating_following_tabs(self):
        self.saved_tabs(active=1)
        restored=self.new_window()
        restored.prepare_startup_browsing()
        widths=restored._tabs[0].splitter_sizes
        self.assertAlmostEqual(widths[0]/sum(widths),.17,delta=.015)
        restored.tab_bar.setCurrentIndex(0)
        self.settle()
        actual=[restored.pane_splitter.sizes()[restored.pane_splitter.indexOf(p.container)] for p in restored.panes]
        self.assertAlmostEqual(actual[0]/sum(actual),.17,delta=.015)

    def test_reopening_an_unvisited_background_tab_uses_its_requested_folder(self):
        pane=self.window.open_new_tab(str(self.folders[1]),active=False)
        self.assertIsNone(pane.folder)
        self.window.close_tab(1)
        self.window.reopen_closed_tab()
        self.settle()
        self.assertEqual(self.window.folder,str(self.folders[1]))

    def test_reopening_a_renamed_tab_preserves_its_name(self):
        self.window.open_new_tab(str(self.folders[1]))
        self.settle()
        self.window.rename_tab(1,'Mes films')
        self.window.close_tab(1)
        self.window.populate_recently_closed_tabs()
        self.assertEqual(self.window.recently_closed_tabs_menu.actions()[0].text(),'Mes films')
        self.window.reopen_closed_tab()
        self.settle()
        self.assertEqual(self.window.tab_bar.tabText(self.window._active_tab),'Mes films')

    def test_external_selection_waits_for_an_unvisited_background_tab(self):
        pane=self.window.open_new_tab(str(self.folders[1]),active=False)
        self.window.open_external_locations([
            LaunchRequest(str(self.folders[0])),
            LaunchRequest(str(self.folders[1]),(str(self.folders[1]/'note.txt'),)),
        ],across_windows=False)
        self.assertTrue(pane.external_request_pending)
        self.window.tab_bar.setCurrentIndex(1)
        self.settle()
        self.assertEqual(self.window.selected_entries(),[self.folders[1]/'note.txt'])

    def test_session_restoration_does_not_start_background_scanners(self):
        self.saved_tabs(active=1)
        restored=self.new_window()
        restored.prepare_startup_browsing()
        restored.start_browsing()
        self.settle()
        for pane in restored._tabs[0].panes:
            self.assertFalse(pane.scanning)
            self.assertTrue(pane._session_listing_pending)
            self.assertFalse(pane.model.rows)

    def test_restoring_before_show_preserves_the_requested_split(self):
        from mirivue.app import Window
        self.saved_tabs(active=0)
        restored=Window()
        self.windows.append(restored)
        self.assertFalse(restored.isVisible())
        restored.prepare_startup_browsing()
        restored.show()
        restored.start_browsing()
        self.settle()
        actual=[restored.pane_splitter.sizes()[restored.pane_splitter.indexOf(p.container)] for p in restored.panes]
        self.assertTrue(all(n>0 for n in actual))
        self.assertAlmostEqual(actual[0]/sum(actual),.17,delta=.015)

    def test_reopening_unsplit_right_pane_does_not_restore_the_hidden_left_folder(self):
        self.window.set_split_view(True,navigate_new=False)
        right=self.window.panes[1]
        self.window.run_in_pane(right,self.window.navigate,str(self.folders[1]))
        self.settle()
        self.window.activate_pane(right)
        self.window.set_split_view(False)
        self.window.open_new_tab(str(self.folders[2]),active=False)
        self.window.close_tab(0)
        self.window.reopen_closed_tab()
        self.settle()
        self.assertEqual(self.window.folder,str(self.folders[1]))
        self.assertFalse(self.window.split_enabled)

    def test_external_selection_in_restored_inactive_right_pane_is_not_lost(self):
        self.saved_tabs(active=1)
        restored=self.new_window()
        restored.prepare_startup_browsing()
        restored.start_browsing()
        self.settle()
        restored.open_external_locations([
            LaunchRequest(str(self.folders[2])),
            LaunchRequest(str(self.folders[1]),(str(self.folders[1]/'note.txt'),)),
        ],across_windows=False)
        target=restored._tabs[0].panes[1]
        self.assertTrue(target.external_request_pending)
        restored.tab_bar.setCurrentIndex(0)
        self.settle()
        self.assertEqual(restored.run_in_pane(target,restored.selected_entries),[self.folders[1]/'note.txt'])

    def test_native_canvas_wrapper_matches_the_actual_qt_type(self):
        from PySide6.QtWidgets import QAbstractScrollArea, QWidget
        backend=self.window.table._backend
        self.assertTrue(backend.canvas.inherits('QWidget'))
        self.assertFalse(backend.canvas.inherits('QAbstractScrollArea'))
        self.assertIsInstance(backend.canvas,QWidget)
        self.assertNotIsInstance(backend.canvas,QAbstractScrollArea)
        self.assertEqual(backend.canvas.rect().size(),backend.canvas.size())
