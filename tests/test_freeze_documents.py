"""Current publication instructions must point to the files actually shipped."""
from pathlib import Path
import re,unittest
ROOT=Path(__file__).resolve().parents[1]

class TestFreezeDocuments(unittest.TestCase):
    def test_current_freeze_commands_and_reports_exist(self):
        text=(ROOT/'STABILISATION.md').read_text()
        version=re.search(r"__version__\s*=\s*['\"]([^'\"]+)", (ROOT/'mirivue/__init__.py').read_text())[1]
        rc='RC'+version.rsplit('rc',1)[1]
        for name in [f'Valider-{rc}.sh',f'Verifier-installation-{rc}.sh',f'A-verifier-{rc}.md',f'VALIDATION-{rc}.md']:
            self.assertIn(name,text)
            self.assertTrue((ROOT/name).is_file(),name)
        for name in re.findall(r'`([^`]+\.(?:sh|md))`',text):
            self.assertTrue((ROOT/name.removeprefix('./')).is_file(),name)
    def test_changelog_has_one_nonempty_section_per_version(self):
        text=(ROOT/'CHANGELOG.md').read_text()
        matches=list(re.finditer(r'^## (.+)$',text,re.M));seen=set()
        for i,match in enumerate(matches):
            title=match[1]
            self.assertRegex(title,r'^1\.0\.0-rc\d+(?: — .+)?$')
            version=re.match(r'1\.0\.0-rc\d+',title)[0]
            self.assertNotIn(version,seen);seen.add(version)
            end=matches[i+1].start() if i+1<len(matches) else len(text)
            self.assertTrue(text[match.end():end].strip(),title)
