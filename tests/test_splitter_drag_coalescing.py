"""A continuous divider drag should trigger one layout per frame and one save."""

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class Timer:
    def __init__(self):
        self.active = False
        self.starts = 0

    def isActive(self):
        return self.active

    def start(self, *_args):
        self.active = True
        self.starts += 1

    def fire(self):
        self.active = False


class TestSplitterDragCoalescing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'mirivue' / 'panes.py').read_text())
        mixin = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PaneMixin')
        names = {'schedule_path_toolbar_alignment', 'schedule_breadcrumb_reveal',
                 'schedule_pane_splitter_save', 'save_pane_splitter_sizes'}
        selected = [node for node in mixin.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {}
        module = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
            name='Methods', bases=[], keywords=[], body=selected, decorator_list=[])], type_ignores=[]))
        exec(compile(module, '<splitter scheduling>', 'exec'), namespace)
        cls.methods = namespace['Methods']

    def test_many_movements_coalesce_layout_but_debounce_settings(self):
        owner = self.methods()
        owner._path_alignment_drag_timer = Timer()
        owner._breadcrumb_reveal_timer = Timer()
        owner._pane_splitter_save_timer = Timer()
        saved = []
        owner.settings = SimpleNamespace(setValue=lambda key, value: saved.append((key, value)))
        first, second = SimpleNamespace(container=object()), SimpleNamespace(container=object())
        owner.panes = [first, second]
        owner.split_enabled = True
        owner.pane_splitter = SimpleNamespace(sizes=lambda: [420, 580],
                                              indexOf=lambda widget: 0 if widget is first.container else 1)
        for _ in range(25):
            owner.schedule_path_toolbar_alignment()
            owner.schedule_breadcrumb_reveal()
            owner.schedule_pane_splitter_save()
        self.assertEqual(owner._path_alignment_drag_timer.starts, 1)
        self.assertEqual(owner._breadcrumb_reveal_timer.starts, 1)
        self.assertEqual(owner._pane_splitter_save_timer.starts, 25)
        self.assertEqual(saved, [])
        owner._pane_splitter_save_timer.fire()
        owner.save_pane_splitter_sizes()
        self.assertEqual(saved, [('panes/splitter-sizes', [420, 580])])


if __name__ == '__main__':
    unittest.main()
