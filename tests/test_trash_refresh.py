"""The Trash must refresh in every tab when emptying has completed."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


class FakeUrl:
    def __init__(self, value):
        self.value = value

    def scheme(self):
        return urlsplit(self.value).scheme


def load_pane_method(name):
    source = (ROOT / 'mirivue' / 'panes.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    pane_mixin = next(node for node in module.body
                      if isinstance(node, ast.ClassDef) and node.name == 'PaneMixin')
    method = next(node for node in pane_mixin.body
                  if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = {'QUrl': FakeUrl}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])),
                 '<refresh_trash_panes>', 'exec'), namespace)
    return namespace[name]


class TestTrashRefresh(unittest.TestCase):
    def test_active_and_background_trash_views_refresh(self):
        def pane(folder):
            rows = ['ancien élément']
            model = SimpleNamespace(rows=rows, clear=rows.clear)
            return SimpleNamespace(folder=folder, model=model, scanning=False,
                                   pending_navigation=None, worker=None)

        trash = pane('trash:/')
        nested = pane('trash:/sous-dossier')
        local = pane('/tmp/dossier')
        remote = pane('smb://serveur/partage')

        class Window:
            _tabs = [SimpleNamespace(panes=[trash, local]),
                     SimpleNamespace(panes=[nested, remote])]

            def __init__(self):
                self.visited = []
                self.captured = False
                self.model = trash.model
                self.scanning = False
                self.worker = None

            def capture_pane(self):
                self.captured = True

            def run_in_pane(self, pane, callback, folder):
                original = self.model
                self.model = pane.model
                try:
                    callback(folder)
                finally:
                    self.model = original

            _clear_and_reload_trash_pane = load_pane_method('_clear_and_reload_trash_pane')

            def update_empty_state(self):
                pass

            def update_summary(self):
                pass

            def scan(self):
                self.visited.append(self.model)

        window = Window()
        load_pane_method('refresh_trash_panes')(window)
        self.assertTrue(window.captured)
        self.assertEqual(window.visited, [trash.model, nested.model])
        self.assertEqual(trash.model.rows, [])
        self.assertEqual(nested.model.rows, [])
        self.assertEqual(local.model.rows, ['ancien élément'])
        self.assertEqual(remote.model.rows, ['ancien élément'])

    def test_pending_scan_cannot_keep_old_trash_rows(self):
        worker = SimpleNamespace(cancelled=False)

        def cancel():
            worker.cancelled = True

        worker.cancel = cancel
        rows = ['ancien élément']
        model = SimpleNamespace(rows=rows, clear=rows.clear)

        class Window:
            scanning = True
            pending_navigation = None

            def __init__(self):
                self.model = model
                self.worker = worker

            def update_empty_state(self):
                pass

            def update_summary(self):
                pass

        window = Window()
        load_pane_method('_clear_and_reload_trash_pane')(window, 'trash:/')
        self.assertEqual(rows, [])
        self.assertTrue(worker.cancelled)
        self.assertEqual(window.pending_navigation, ('trash:/', None))

    def test_stale_trash_rows_allow_native_menu_to_recheck(self):
        trash = SimpleNamespace(folder='trash:/', model=SimpleNamespace(rows=['ancien élément']))
        local = SimpleNamespace(folder='/tmp/dossier', model=SimpleNamespace(rows=['fichier']))

        class Window:
            _tabs = [SimpleNamespace(panes=[local, trash])]

            def capture_pane(self):
                pass

        check = load_pane_method('trash_view_has_items')
        self.assertTrue(check(Window()))
        trash.model.rows.clear()
        self.assertFalse(check(Window()))


if __name__ == '__main__':
    unittest.main()
