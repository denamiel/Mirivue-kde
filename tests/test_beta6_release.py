"""Release identity and plain incident explanations stay consistent."""
import ast
from pathlib import Path
import tomllib
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class TestBeta6Release(unittest.TestCase):
    def test_version_consistent_in_application_python_and_appstream(self):
        tree = ast.parse((ROOT/'mirivue/__init__.py').read_text())
        version = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t,ast.Name) and t.id=='__version__' for t in n.targets))
        python_version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        self.assertEqual(version, '1.0.0-beta.6')
        self.assertEqual(python_version, '1.0.0b6')
        for path in ('packaging/org.pdenams.Mirivue.Qt.metainfo.xml','packaging/mirivue-local.xml'):
            release = ET.parse(ROOT/path).find('.//release')
            self.assertEqual(release.attrib['version'], version, path)
            self.assertEqual(release.attrib['date'], '2026-11-08')

    def test_rpm_upgrade_keeps_version_and_increases_legacy_release_counter(self):
        spec = (ROOT/'packaging/fedora/mirivue-kde.spec').read_text()
        self.assertIn('Version: 1.0.0', spec)
        self.assertIn('Release: 0.201.beta6.1%{?dist}', spec)
        self.assertIn('Mirivue-1.0.0-beta.6-KDE.tar.gz', spec)

    def test_media_read_failure_is_explained_without_claiming_a_crash(self):
        tree = ast.parse((ROOT/'mirivue/metadata.py').read_text())
        failed = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='failed')
        scope = {'Video': lambda *args,**kwargs:(args,kwargs), 'tr':lambda text:text}
        exec(compile(ast.Module(body=[failed],type_ignores=[]),'metadata.py','exec'),scope)
        args,_ = scope['failed'](Path('incomplete.mkv'),'EBML header parsing failed')
        detail = args[3]
        self.assertIn('incomplet', detail)
        self.assertIn('Aucun contenu n’a été modifié', detail)
        self.assertIn('EBML header parsing failed', detail)

if __name__=='__main__': unittest.main()
