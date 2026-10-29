"""Permanent delete remains a native, theme-highlighted menu action."""
import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'mirivue' / 'iconography.py'
MODULE = ast.parse(SOURCE.read_text(encoding='utf-8'))
FUNCTION = next(
    node for node in MODULE.body
    if isinstance(node, ast.FunctionDef) and node.name == 'add_destructive_action'
)
FUNCTION_SOURCE = ast.get_source_segment(SOURCE.read_text(encoding='utf-8'), FUNCTION)


class TestDestructiveMenuHighlight(unittest.TestCase):
    def test_native_action_keeps_plasma_hover_painting(self):
        self.assertIn('QAction(menu)', FUNCTION_SOURCE)
        self.assertNotIn('action = QWidgetAction', FUNCTION_SOURCE)
        self.assertNotIn('button = QToolButton', FUNCTION_SOURCE)
        self.assertNotIn('setPalette', FUNCTION_SOURCE)

    def test_only_the_icon_receives_destructive_semantics(self):
        self.assertIn('set_destructive_action_icon(action, name)', FUNCTION_SOURCE)
        self.assertNotIn('setStyleSheet', FUNCTION_SOURCE)


if __name__ == '__main__':
    unittest.main()
