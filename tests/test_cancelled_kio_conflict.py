"""Distinguish a dismissed local collision from a transfer error."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse
import unittest

source = Path(__file__).resolve().parents[1] / 'mirivue' / 'movement.py'
module = ast.parse(source.read_text())
function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'cancelled_existing_file_conflict')
class Url:
    def __init__(self, text): self.text = text
    def isLocalFile(self): return self.text.startswith('file://')
    def toLocalFile(self): return unquote(urlparse(self.text).path)
namespace = dict(Path=Path, QUrl=Url)
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
recognize = namespace['cancelled_existing_file_conflict']

class TestCancelledConflict(unittest.TestCase):
    def test_existing_files_and_no_error_are_a_cancel(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'from').mkdir(); (root/'to').mkdir()
            a = root/'from'/'item.pdf'; b = root/'to'/'item.pdf'
            a.write_text('source'); b.write_text('destination')
            self.assertTrue(recognize([a.as_uri()], (root/'to').as_uri(), ''))
            self.assertFalse(recognize([a.as_uri()], (root/'to').as_uri(), 'Permission denied'))
            self.assertFalse(recognize([a.as_uri(), a.as_uri()], (root/'to').as_uri(), ''))
            b.unlink()
            self.assertFalse(recognize([a.as_uri()], (root/'to').as_uri(), ''))
