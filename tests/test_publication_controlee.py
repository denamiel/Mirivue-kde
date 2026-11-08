"""Publications only on explicit maintainer authorization.

A merge into main (push), a pull request, a schedule, a release or a tag must
never publish packages. Each publish job runs only for a manual
workflow_dispatch on main with the typed confirmation PUBLIER, in a protected
environment, and COPR refuses an equal or lower RPM Epoch:Version-Release.
"""
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'
GUARD = ROOT / 'packaging' / 'fedora' / 'verifier-revision-publication.py'
spec = importlib.util.spec_from_file_location('verifier_revision', GUARD)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

PUBLISHING = re.compile(r'git push|gh release (upload|create|edit)|copr-cli|curl[^\n]*webhook')


def workflow(name):
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding='utf-8'))
    data['on'] = data.get('on', data.get(True))   # YAML 1.1 reads "on" as True
    return data


def evaluate(condition, context):
    """Evaluate the restricted GitHub expressions used by publish jobs.

    Only terms "name == 'value'" or "name != 'value'" joined by && are allowed;
    anything else (||, !, functions) is rejected so a weaker condition cannot
    slip in unnoticed.
    """
    text = ' '.join(str(condition).replace('${{', '').replace('}}', '').split())
    if '||' in text or re.search(r'!(?!=)', text) or '(' in text:
        raise AssertionError(f'condition non restreinte : {text}')
    result = True
    for term in text.split('&&'):
        match = re.fullmatch(r"\s*([\w.]+)\s*(==|!=)\s*'([^']*)'\s*", term)
        if not match:
            raise AssertionError(f'terme non pris en charge : {term!r}')
        name, operator, value = match.groups()
        actual = context.get(name, '')
        result = result and ((actual == value) if operator == '==' else (actual != value))
    return result


def events(inputs_key, extra=None):
    """GitHub contexts that must never publish, and the single one that may."""
    extra = extra or {}
    denied = {
        'fusion dans main (push)': {'github.event_name': 'push', 'github.ref': 'refs/heads/main'},
        'pull request': {'github.event_name': 'pull_request', 'github.ref': 'refs/pull/7/merge'},
        'planification': {'github.event_name': 'schedule', 'github.ref': 'refs/heads/main'},
        'release publiée': {'github.event_name': 'release', 'github.ref': 'refs/tags/v1.0.0-beta.6'},
        'push de tag': {'github.event_name': 'push', 'github.ref': 'refs/tags/v1.0.0-beta.6'},
        'manuel sans confirmation': {'github.event_name': 'workflow_dispatch', 'github.ref': 'refs/heads/main', **extra},
        'manuel, confirmation inexacte': {'github.event_name': 'workflow_dispatch', 'github.ref': 'refs/heads/main',
                                          inputs_key: 'publier', **extra},
        'manuel depuis une autre branche': {'github.event_name': 'workflow_dispatch',
                                            'github.ref': 'refs/heads/preparation/beta6-kio-securite',
                                            inputs_key: 'PUBLIER', **extra},
    }
    allowed = {'github.event_name': 'workflow_dispatch', 'github.ref': 'refs/heads/main',
               inputs_key: 'PUBLIER', **extra}
    return denied, allowed


class TestPublishJobsNeedExplicitAuthorization(unittest.TestCase):
    def check_publish_job(self, name, inputs_key, environment, extra=None):
        data = workflow(name)
        job = data['jobs']['publish']
        denied, allowed = events(inputs_key, extra)
        for label, context in denied.items():
            with self.subTest(workflow=name, event=label):
                self.assertFalse(evaluate(job['if'], context), f'{name} publierait sur : {label}')
        self.assertTrue(evaluate(job['if'], allowed), f'{name} ne pourrait jamais publier')
        self.assertEqual(job.get('environment'), environment)
        self.assertIn(inputs_key.split('.', 1)[1], data['on']['workflow_dispatch']['inputs'])
        return data

    def test_copr_publication_requires_manual_confirmation(self):
        self.check_publish_job('fedora-package.yml', 'inputs.publier_copr', 'publication-copr')

    def test_arch_release_assets_require_manual_confirmation_and_tag(self):
        data = self.check_publish_job('arch-package.yml', 'inputs.publier_arch', 'publication-arch',
                                      {'inputs.tag': 'v1.0.0-beta.6'})
        job = data['jobs']['publish']
        without_tag = {'github.event_name': 'workflow_dispatch', 'github.ref': 'refs/heads/main',
                       'inputs.publier_arch': 'PUBLIER'}
        self.assertFalse(evaluate(job['if'], without_tag))
        self.assertNotIn('release', data['on'], 'une release ne doit plus déclencher de publication')
        script = '\n'.join(step.get('run', '') for step in job['steps'])
        self.assertIn('"$tag_commit" != "$TESTED_COMMIT"', script)
        uploads = [line for line in script.splitlines() if 'gh release upload' in line]
        self.assertEqual(len(uploads), 1)
        self.assertNotIn('--clobber', uploads[0], 'un fichier déjà publié ne doit jamais être remplacé')

    def test_only_publish_jobs_write_to_distributions(self):
        for path in sorted(WORKFLOWS.glob('*.yml')):
            data = workflow(path.name)
            for job_name, job in data['jobs'].items():
                script = '\n'.join(step.get('run', '') for step in job.get('steps', []))
                with self.subTest(workflow=path.name, job=job_name):
                    if PUBLISHING.search(script):
                        self.assertEqual(job_name, 'publish', 'commande de publication hors du job protégé')
                        self.assertTrue(job.get('environment'), 'job de publication sans environnement')

    def test_copr_publication_requires_the_mandatory_graphical_tests(self):
        """A failed or skipped TestLab run must block COPR, without weakening the
        manual authorization: the publish condition keeps no status function, so
        GitHub's implicit success() applies to every needed job."""
        jobs = workflow('fedora-package.yml')['jobs']
        publish = jobs['publish']
        self.assertTrue({'rpm', 'python', 'testlab'} <= set(publish['needs']), publish['needs'])
        self.assertNotRegex(str(publish['if']), r'always|failure|cancelled|success|!')
        testlab = jobs['testlab']
        self.assertNotIn('if', testlab, 'TestLab doit tourner pour chaque révision testée')
        self.assertNotIn('continue-on-error', testlab)
        for step in testlab['steps']:
            self.assertNotIn('continue-on-error', step, step.get('name'))
        self.assertEqual(testlab['permissions'], {'contents': 'read'})
        self.assertNotIn('secrets.', str(testlab), 'aucun secret dans le job de test')
        self.assertEqual(testlab['env']['MIRIVUE_TESTLAB_REQUIRE_DISPLAY'], '1')
        self.assertEqual(testlab['env']['MIRIVUE_TESTLAB_REQUIRE_CONFINEMENT'], '1')
        self.assertTrue(testlab['env']['MIRIVUE_TESTLAB_USER'])
        script = '\n'.join(step.get('run', '') for step in testlab['steps'])
        self.assertIn('test_testlab_harness.py', script)
        self.assertIn('tests/testlab/run.py nouveau-dossier', script)
        # The publish job still requires the manual confirmation and environment.
        self.check_publish_job('fedora-package.yml', 'inputs.publier_copr', 'publication-copr')

    def test_copr_job_checks_head_ancestry_and_increasing_release(self):
        script = '\n'.join(step.get('run', '') for step in workflow('fedora-package.yml')['jobs']['publish']['steps'])
        self.assertIn('git rev-parse origin/main', script)
        self.assertIn('git merge-base --is-ancestor origin/publication', script)
        self.assertIn('verifier-revision-publication.py', script)
        self.assertLess(script.index('verifier-revision-publication.py'), script.index('git push'))


ENV_TOOL = ROOT / 'packaging' / 'environnements-publication.py'
env_spec = importlib.util.spec_from_file_location('environnements_publication', ENV_TOOL)
environnements = importlib.util.module_from_spec(env_spec)
env_spec.loader.exec_module(environnements)


class TestEnvironmentRules(unittest.TestCase):
    MAINTAINER = 42

    def environment(self, reviewers=((('User', 42),)), prevent=False, timer=0, bypass=False, custom=True):
        rules = [{'type': 'required_reviewers', 'prevent_self_review': prevent,
                  'reviewers': [{'type': kind, 'reviewer': {'id': ident, 'login': f'compte{ident}'}}
                                for kind, ident in reviewers]}]
        if timer:
            rules.append({'type': 'wait_timer', 'wait_timer': timer})
        return {'protection_rules': rules, 'can_admins_bypass': bypass,
                'deployment_branch_policy': {'protected_branches': not custom, 'custom_branch_policies': custom}}

    def branches(self, *policies):
        return {'branch_policies': [{'type': kind, 'name': name} for kind, name in policies]}

    def analyse(self, environment, branches):
        return environnements.analyse(environment, branches, self.MAINTAINER)

    def test_compliant_environment(self):
        self.assertEqual(self.analyse(self.environment(), self.branches(('branch', 'main'))), ([], []))

    def test_absent_environment_is_only_created_by_apply(self):
        self.assertEqual(self.analyse(None, None), ([], ['environnement absent']))

    def test_other_reviewers_block_apply_instead_of_being_replaced(self):
        blocking, _ = self.analyse(self.environment(reviewers=(('User', 42), ('User', 7), ('Team', 9))),
                                   self.branches(('branch', 'main')))
        self.assertTrue(any('autres approbateurs' in item for item in blocking), blocking)

    def test_other_branch_or_tag_policies_block_apply(self):
        for extra in (('branch', 'dev'), ('tag', 'v*')):
            with self.subTest(extra=extra):
                blocking, _ = self.analyse(self.environment(), self.branches(('branch', 'main'), extra))
                self.assertTrue(any('autres règles' in item for item in blocking), blocking)

    def test_admin_bypass_is_reported_as_blocking(self):
        blocking, _ = self.analyse(self.environment(bypass=True), self.branches(('branch', 'main')))
        self.assertTrue(any('administrateurs' in item for item in blocking), blocking)

    def test_safe_differences_are_fixable(self):
        for environment, branches, expected in (
                (self.environment(prevent=True), self.branches(('branch', 'main')), 'prevent_self_review'),
                (self.environment(timer=10), self.branches(('branch', 'main')), 'délai'),
                (self.environment(custom=False), self.branches(), 'non limité'),
                (self.environment(), self.branches(), 'main non déclarée'),
                (self.environment(reviewers=()), self.branches(('branch', 'main')), 'non obligatoire')):
            with self.subTest(expected=expected):
                blocking, fixable = self.analyse(environment, branches)
                self.assertEqual(blocking, [])
                self.assertTrue(any(expected in item for item in fixable), fixable)


class TestRpmReleaseGuard(unittest.TestCase):
    def test_rpmvercmp_cases(self):
        cases = [
            ('1.0', '1.0', 0), ('1.0', '1.1', -1), ('1.10', '1.9', 1), ('1.0a', '1.0', 1),
            ('1.0~rc1', '1.0', -1), ('1.0~rc1', '1.0~rc2', -1), ('1.0^git1', '1.0', 1),
            ('1.0^git1', '1.0.1', -1), ('0.201.beta6.1', '0.200.beta5.3', 1),
            ('0.200.beta5.3', '0.200.beta5.3', 0), ('0.199.beta4.2', '0.200.beta5.3', -1),
            ('1.01', '1.1', 0), ('1.0_1', '1.0.1', 0), ('a', '1', -1),
        ]
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertEqual(verifier.rpmvercmp(left, right), expected)
                self.assertEqual(verifier.rpmvercmp(right, left), -expected)

    def test_epoch_dominates(self):
        self.assertEqual(verifier.compare_evr(('1', '0.1', '1'), ('0', '9.9', '9')), 1)
        self.assertEqual(verifier.compare_evr(('0', '9.9', '9'), ('1', '0.1', '1')), -1)

    def test_matches_librpm_when_available(self):
        try:
            import rpm
        except ImportError:
            self.skipTest('python3-rpm absent')
        import random
        generator = random.Random(8)
        pieces = ['0', '1', '9', '10', '01', 'a', 'beta', 'rc', '.', '_', '~', '^']
        build = lambda: ''.join(generator.choice(pieces) for _ in range(generator.randint(1, 5)))
        for _ in range(3000):
            left = (str(generator.randint(0, 1)), build(), build())
            right = (str(generator.randint(0, 1)), build(), build())
            self.assertEqual(verifier.compare_evr(left, right), rpm.labelCompare(left, right), (left, right))

    def run_guard(self, published, candidate):
        with tempfile.TemporaryDirectory() as directory:
            old, new = Path(directory) / 'publie.spec', Path(directory) / 'candidat.spec'
            old.write_text(published)
            new.write_text(candidate)
            return subprocess.run([sys.executable, str(GUARD), str(old), str(new)],
                                  capture_output=True, text=True, timeout=30).returncode

    def spec(self, release, version='1.0.0', epoch=None):
        return (f'Name: mirivue-kde\n' + (f'Epoch: {epoch}\n' if epoch else '')
                + f'Version: {version}\nRelease: {release}%{{?dist}}\n')

    def test_guard_refuses_equal_and_lower_and_accepts_higher(self):
        self.assertEqual(self.run_guard(self.spec('0.200.beta5.3'), self.spec('0.200.beta5.3')), 1)
        self.assertEqual(self.run_guard(self.spec('0.200.beta5.3'), self.spec('0.199.beta4.2')), 1)
        self.assertEqual(self.run_guard(self.spec('0.200.beta5.3'), self.spec('0.201.beta6.1')), 0)
        self.assertEqual(self.run_guard(self.spec('9', version='2.0'), self.spec('1', version='1.0', epoch=1)), 0)

    def test_guard_refuses_unreadable_or_macro_versions(self):
        self.assertEqual(self.run_guard(self.spec('0.200.beta5.3'), 'Name: x\n'), 2)
        self.assertEqual(self.run_guard(self.spec('0.200.beta5.3'), self.spec('%{rel}')), 2)

    def test_current_spec_is_readable(self):
        evr = verifier.spec_evr((ROOT / 'packaging' / 'fedora' / 'mirivue-kde.spec').read_text())
        self.assertNotIn('%', ''.join(evr))


if __name__ == '__main__':
    unittest.main()
