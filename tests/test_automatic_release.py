"""Publication gates must reject stale, failed or untrusted source artefacts."""
import importlib.util
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
release = module('release', 'packaging/publier_release.py')
rpm_plan = module('rpm_plan', 'packaging/plan_rpm_publication.py')
copr = module('copr_verify', 'packaging/verifier_copr_publication.py')


class AutomaticReleaseTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cpio'), 'cpio is required for real RPM payload fixtures')
    def test_source_payload_supports_rpm5_and_rpm6_paths_and_rejects_missing_archive(self):
        import gzip
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name = 'Mirivue-1.0.4-KDE.tar.gz'
            content = gzip.compress(b'archive fixture')
            (root / name).write_bytes(content)
            for stored_name in (name, './' + name):
                payload = subprocess.run(['cpio', '--quiet', '-o', '-H', 'newc'],
                    input=(stored_name + '\n').encode(), cwd=root, capture_output=True, check=True).stdout
                self.assertEqual(copr.extract_source_archive(payload, name), content)
                with self.assertRaises(ValueError):
                    copr.extract_source_archive(payload, 'missing.tar.gz')

    def api(self, path, **kwargs):
        if path == 'branches/main':return {'protected':True,'commit':{'sha':'a'*40}}
        if path.startswith('releases/tags/'):return None
        if path.startswith('releases?'):return []
        if path.startswith('actions/workflows/'):
            return {'workflow_runs':[{'id':42,'head_sha':'a'*40,'head_branch':'main','event':'push','status':'completed','conclusion':'success'}]}
        raise AssertionError(path)

    def test_requires_successful_main_runs_for_both_workflows(self):
        with patch.object(release,'api',side_effect=self.api):
            self.assertEqual(release.plan('a'*40,'1.0.3')['arch_run'],42)
        for update in ({'head_sha':'b'*40},{'head_branch':'other'},{'event':'pull_request'},
                       {'status':'in_progress'},{'conclusion':'failure'},{'conclusion':'skipped'}):
            def api(path,**kwargs):
                result=self.api(path,**kwargs)
                if isinstance(result,dict) and 'workflow_runs' in result:result['workflow_runs'][0].update(update)
                return result
            with self.subTest(update=update),patch.object(release,'api',side_effect=api):
                self.assertIsNone(release.plan('a'*40,'1.0.3'))

    def test_same_published_version_is_a_noop(self):
        def api(path,**kwargs):
            if path.startswith('releases/tags/'):return {'draft':False}
            return self.api(path,**kwargs)
        with patch.object(release,'api',side_effect=api):self.assertIsNone(release.plan('a'*40,'1.0.2'))

    def test_unprotected_or_moved_main_is_rejected(self):
        for branch in ({'protected':False,'commit':{'sha':'a'*40}}, {'protected':True,'commit':{'sha':'b'*40}}):
            with patch.object(release,'api',return_value=branch):
                with self.assertRaises(ValueError):release.plan('a'*40,'1.0.3')

    def test_downgrade_is_rejected(self):
        def api(path,**kwargs):
            if path.startswith('releases?'):return [{'draft':False,'tag_name':'v1.0.4'}]
            return self.api(path,**kwargs)
        with patch.object(release,'api',side_effect=api):
            with self.assertRaises(ValueError):release.plan('a'*40,'1.0.3')

    def test_stale_plan_cannot_write_anything(self):
        with patch.object(release,'plan',return_value=None),patch.object(release,'api') as api:
            with self.assertRaises(ValueError):release.publish({'sha':'a'*40,'version':'1.0.3'},'/missing')
            api.assert_not_called()

    def test_assets_with_path_traversal_or_wrong_hash_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for content in ('0'*64+'  ../escape\n','0'*64+'  unwanted.pkg.tar.zst\n'):
                (root/'SHA256SUMS').write_text(content)
                with self.assertRaises(ValueError):release.verify_assets(root,'1.0.3')

    def test_rpm_revision_equal_skips_lower_refuses_higher_publishes(self):
        def spec(v):return f'Version: {v}\nRelease: 1%{{?dist}}\n'
        self.assertFalse(rpm_plan.decision(spec('1.0.2'),spec('1.0.2')))
        self.assertTrue(rpm_plan.decision(spec('1.0.2'),spec('1.0.3')))
        with self.assertRaises(ValueError):rpm_plan.decision(spec('1.0.2'),spec('1.0.1'))

    def test_source_archive_identity_includes_content_and_git_commit(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'source.py').write_text('print("source")\n')
            (root/'README.md').write_text('Archive fixture\n')
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=root,text=True)
            git('init','--quiet')
            git('add','.')
            git('-c','user.name=Archive test','-c','user.email=archive@example.invalid',
                '-c','commit.gpgsign=false','commit','--quiet','-m','Archive fixture')
            data=subprocess.check_output(['git','archive','--format=tar','HEAD'],cwd=root)
            commit,files=copr.archive_files(data)
            self.assertEqual(commit,git('rev-parse','HEAD').strip())
            self.assertNotEqual(files['source.py'],files['README.md'])


if __name__ == '__main__':unittest.main()
