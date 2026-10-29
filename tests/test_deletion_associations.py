"""A delete confirmation must reveal companions and default to selected files."""

import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from mirivue.locations import Location


ROOT = Path(__file__).resolve().parents[1]


class FakeMessageBox:
    Icon = SimpleNamespace(Question=1)
    ButtonRole = SimpleNamespace(AcceptRole=1, ActionRole=2)
    StandardButton = SimpleNamespace(Cancel=3)
    latest = None

    def __init__(self, _parent):
        type(self).latest = self
        self.buttons = []
        self.default = None

    def setWindowTitle(self, _value):
        pass

    def setIcon(self, _value):
        pass

    def setText(self, _value):
        pass

    def setInformativeText(self, value):
        self.information = value

    def setDetailedText(self, value):
        self.details = value

    def addButton(self, label, _role=None):
        button = SimpleNamespace(text=label, setText=lambda _value: None)
        self.buttons.append(button)
        return button

    def setDefaultButton(self, button):
        self.default = button

    def exec(self):
        self.clicked = self.default

    def clickedButton(self):
        return self.clicked


def load_choose():
    tree = ast.parse((ROOT / 'mirivue' / 'movement.py').read_text(encoding='utf-8'))
    klass = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MovementMixin')
    function = next(node for node in klass.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'choose_associated_entries')
    class RemoveImports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            return None

    function = RemoveImports().visit(function)
    namespace = dict(Location=Location, normalize_sources=lambda paths: list(dict.fromkeys(paths)),
                     companion=lambda path: path.with_suffix('.xmp'),
                     EXTENSIONS={'.mkv'}, AUDIO_EXT={'.mp3'}, IMAGE_EXT={'.jpg'},
                     QMessageBox=FakeMessageBox, tr=lambda value: value,
                     trf=lambda value, *parts: value.replace('\x1f0\x1f', str(parts[0])).replace(
                         '\x1f1\x1f', str(parts[1]) if len(parts) > 1 else ''))
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<associations>', 'exec'), namespace)
    return namespace['choose_associated_entries']


class TestDeletionAssociations(unittest.TestCase):
    def test_xmp_is_named_and_selected_only_is_default(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / 'film.mkv'
            sidecar = video.with_suffix('.xmp')
            video.write_bytes(b'video')
            sidecar.write_bytes(b'xmp')
            window = SimpleNamespace(associated_entries=lambda _paths: [])
            result = load_choose()(window, [video], 'suppression', include_xmp=True)
            box = FakeMessageBox.latest
            self.assertEqual(result, [video])
            self.assertIn(str(sidecar), box.information)
            self.assertIn(str(sidecar), box.details)
            self.assertEqual(box.default.text, 'Fichier(s) sélectionné(s) seulement')


if __name__ == '__main__':
    unittest.main()
