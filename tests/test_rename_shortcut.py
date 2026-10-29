from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestRenameShortcut(unittest.TestCase):
    def test_f2_has_one_qt_shortcut_owner(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('self.rename_shortcut = QShortcut', source)
        self.assertIn("add('rename', tr('Renommer'), tr('F2'), self.rename_action)", source)
        self.assertIn("self.rename_action.setShortcut(QKeySequence(tr('F2')))", source)

    def test_legacy_global_key_interception_is_removed(self):
        source = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn("self.event_matches_shortcut(event, 'rename')", source)
        # Physical F2 and custom bindings are exercised in test_keyboard_gui.
        self.assertIn("self.rename_action = file_menu.addAction", source)


if __name__ == '__main__':
    unittest.main()
