from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestStartupLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        cls.panes = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')

    def test_layout_is_prepared_before_the_window_is_shown(self):
        prepare = self.app.index('window.prepare_startup_browsing(request.folder or ')
        show = self.app.index('window.show()', prepare)
        loading = self.app.index('QTimer.singleShot(0, window.start_browsing)', show)
        self.assertLess(prepare, show)
        self.assertLess(show, loading)

    def test_split_startup_does_not_navigate_while_building_the_layout(self):
        self.assertIn('self.set_split_view(True, navigate_new=False)', self.app)
        self.assertIn('def set_split_view(self, enabled, navigate_new=True):', self.panes)
        self.assertIn('if pane and navigate_new:', self.panes)

    def test_each_pane_remembers_its_own_last_folder(self):
        self.assertIn("f'panes/{pane.column_slot}-folder'", self.app)
        self.assertIn("self.settings.value('panes/right-folder', '')", self.app)
        self.assertIn("self.settings.value('panes/left-folder'", self.app)

    def test_absent_local_startup_location_falls_back_safely(self):
        start = self.app.index('def startup_location_or(')
        end = self.app.index('def remember_pane_folder(', start)
        helper = self.app[start:end]
        self.assertIn('if path.is_dir():', helper)
        self.assertIn('return fallback', helper)

    def test_startup_alignment_is_not_repeated_over_visible_timers(self):
        start = self.app.index('def resizeEvent(')
        end = self.app.index('def update_toolbar_responsiveness(', start)
        resize = self.app[start:end]
        self.assertNotIn('QTimer.singleShot(80, self.sync_path_toolbar_alignment)', resize)
        self.assertNotIn('QTimer.singleShot(160, self.sync_path_toolbar_alignment)', resize)

        show_start = self.app.index('def showEvent(')
        show_end = self.app.index('def eventFilter(', show_start)
        show_event = self.app[show_start:show_end]
        self.assertNotIn('QTimer.singleShot(80, self.sync_path_toolbar_alignment)', show_event)

    def test_breadcrumbs_are_rebuilt_only_when_the_location_changes(self):
        self.assertIn('pane.rendered_path = None', self.panes)
        self.assertIn("if not force and pane.rendered_path == (folder or '') and pane.rendered_full_path == show_full:", self.panes)
        self.assertIn("pane.rendered_path = folder or ''", self.panes)
        self.assertIn('self.update_pane_path_bar(self.bound_pane)', self.app)

    def test_initial_directory_inventory_is_published_atomically(self):
        self.assertIn('initial = Signal(object)', self.app)
        self.assertIn('self.initial.emit(initial)', self.app)
        self.assertNotIn('self.listed.emit(initial[offset:offset + 128])', self.app)
        self.assertIn('def set_initial_listing(self, rows):', self.app)
        self.assertIn('model.beginResetModel()', self.app)
        self.assertIn('model.rows = prepared', self.app)
        self.assertIn('self.worker.initial.connect(', self.app)


if __name__ == '__main__':
    unittest.main()
