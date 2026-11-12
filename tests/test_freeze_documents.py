"""Release documents and native notices must describe the current sources."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERSION = r"\d+\.\d+\.\d+(?:-(?:beta\.|rc)\d+)?"

class TestFreezeDocuments(unittest.TestCase):
    def test_current_freeze_commands_and_reports_exist(self):
        text = (ROOT / 'STABILISATION.md').read_text()
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)",
                            (ROOT / 'mirivue/__init__.py').read_text())[1]
        self.assertIn(version, text)
        self.assertIn('docs/AUDIT-STABLE.md', text)
        for name in re.findall(r'`([^`]+\.(?:sh|md))`', text):
            self.assertTrue((ROOT / name.removeprefix('./')).is_file(), name)

    def test_changelog_has_one_nonempty_section_per_version(self):
        text = (ROOT / 'CHANGELOG.md').read_text()
        matches = list(re.finditer(r'^#{1,2} (' + VERSION + r')(?: — [^\n]+)?$', text, re.M))
        self.assertTrue(matches, 'No release sections found')
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)",
                            (ROOT / 'mirivue/__init__.py').read_text())[1]
        self.assertEqual(matches[0][1], version)
        seen = set()
        for i, match in enumerate(matches):
            self.assertNotIn(match[1], seen)
            seen.add(match[1])
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            self.assertTrue(text[match.end():end].strip(), match[1])

    def test_native_mit_sources_are_indexed(self):
        index = (ROOT / 'LICENCES-TIERS.md').read_text()
        sources = [p for p in (ROOT / 'native').rglob('*')
                   if p.is_file() and p.suffix in ('.cpp', '.h')
                   and 'SPDX-License-Identifier: MIT' in p.read_text(errors='ignore')]
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source.relative_to(ROOT).as_posix()):
                self.assertIn('`' + source.relative_to(ROOT).as_posix() + '`', index)

if __name__ == '__main__':
    unittest.main()
