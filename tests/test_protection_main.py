# SPDX-License-Identifier: MIT
"""The main-branch ruleset must require every mandatory CI check by its real name."""
import copy
from unittest import mock
import importlib.util
from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'packaging' / 'protection-main.py'
spec = importlib.util.spec_from_file_location('protection_main', TOOL)
protection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protection)


def check_names(workflow):
    """Expand job names the way GitHub names check runs (non-experimental matrix rows)."""
    data = yaml.safe_load((ROOT / '.github' / 'workflows' / workflow).read_text(encoding='utf-8'))
    names = {}
    for key, job in data['jobs'].items():
        if key == 'publish':
            continue
        template = job.get('name', key)
        matrix = job.get('strategy', {}).get('matrix')
        if not matrix:
            names[template] = job
            continue
        rows = matrix.get('include') or [{name: value} for name, values in matrix.items() for value in values]
        for row in rows:
            if row.get('experimental'):
                continue
            names[re.sub(r'\$\{\{\s*matrix\.(\w+)\s*\}\}', lambda m: str(row[m.group(1)]), template)] = job
    return names


class MainProtection(unittest.TestCase):
    def test_required_checks_match_the_real_job_names(self):
        actual = set(check_names('fedora-package.yml')) | set(check_names('arch-package.yml'))
        required, informative = set(protection.REQUIRED_CHECKS), set(protection.INFORMATIVE_CHECKS)
        self.assertFalse(required & informative)
        self.assertEqual(required | informative, actual, 'chaque job doit être obligatoire ou explicitement informatif')

    def test_graphical_tests_are_required(self):
        self.assertIn('TestLab — vraie fenêtre sous Xvfb (Fedora 45)', protection.REQUIRED_CHECKS)

    def test_expected_ruleset_is_compliant(self):
        self.assertEqual(protection.analyse(protection.expected_ruleset()), [])

    def test_absent_ruleset_is_reported(self):
        self.assertEqual(protection.analyse(None), ['règle absente : main n’exige aucun contrôle'])

    def test_weakened_rulesets_are_reported(self):
        cases = {
            'mode évaluation': lambda r: r.update(enforcement='evaluate'),
            'contournement': lambda r: r.update(bypass_actors=[{'actor_type': 'RepositoryRole', 'actor_id': 5}]),
            'contrôle retiré': lambda r: r['rules'][3]['parameters']['required_status_checks'].pop(),
            'autre application': lambda r: r['rules'][3]['parameters']['required_status_checks'][0].update(
                integration_id=1),
            'pull request non exigée': lambda r: r['rules'].pop(2),
            'branche non à jour': lambda r: r['rules'][3]['parameters'].update(
                strict_required_status_checks_policy=False),
            'autre branche': lambda r: r['conditions']['ref_name'].update(include=['refs/heads/dev']),
        }
        for label, weaken in cases.items():
            with self.subTest(label):
                ruleset = copy.deepcopy(protection.expected_ruleset())
                weaken(ruleset)
                self.assertTrue(protection.analyse(ruleset), label)

    def test_stricter_or_unknown_settings_are_reported_not_ignored(self):
        cases = {
            'règle supplémentaire': lambda r: r['rules'].append({'type': 'required_signatures'}),
            'approbation exigée': lambda r: r['rules'][2]['parameters'].update(required_approving_review_count=1),
            'paramètre inconnu': lambda r: r['rules'][2]['parameters'].update(allowed_merge_methods=['squash']),
            'contrôle en plus': lambda r: r['rules'][3]['parameters']['required_status_checks'].append(
                {'context': 'autre', 'integration_id': 15368}),
            'exclusion de branche': lambda r: r['conditions']['ref_name'].update(exclude=['refs/heads/x']),
        }
        for label, change in cases.items():
            with self.subTest(label):
                ruleset = copy.deepcopy(protection.expected_ruleset())
                change(ruleset)
                self.assertTrue(protection.analyse(ruleset), label)

    def test_check_order_and_ids_returned_by_github_do_not_matter(self):
        ruleset = copy.deepcopy(protection.expected_ruleset())
        ruleset.update(id=12, source='denamiel/Mirivue-kde', _links={})
        ruleset['rules'].reverse()
        ruleset['rules'][0]['parameters']['required_status_checks'].reverse()
        self.assertEqual(protection.analyse(ruleset), [])


def runs(names, conclusion='success', app=15368):
    return [{'name': name, 'conclusion': conclusion, 'app': {'id': app}} for name in names]


class ApplyDecision(unittest.TestCase):
    ALL = protection.REQUIRED_CHECKS

    def test_existing_different_ruleset_is_never_replaced(self):
        ruleset = copy.deepcopy(protection.expected_ruleset())
        ruleset['rules'].append({'type': 'required_signatures'})
        action, messages = protection.decide(ruleset, runs(self.ALL))
        self.assertEqual(action, 'refuser')
        self.assertTrue(any('required_signatures' in message for message in messages))

    def test_compliant_ruleset_needs_nothing(self):
        self.assertEqual(protection.decide(protection.expected_ruleset(), [])[0], 'rien')

    def test_creation_is_refused_while_a_required_check_is_missing_on_main(self):
        present = [name for name in self.ALL if not name.startswith('TestLab')]
        action, messages = protection.decide(None, runs(present))
        self.assertEqual(action, 'refuser')
        self.assertIn('TestLab', messages[0])

    def test_failed_skipped_or_foreign_checks_do_not_count(self):
        for check_runs in (runs(self.ALL, conclusion='failure'), runs(self.ALL, conclusion='skipped'),
                           runs(self.ALL, app=1)):
            with self.subTest(check_runs[0]):
                self.assertEqual(protection.decide(None, check_runs)[0], 'refuser')

    def test_creation_when_absent_and_every_check_succeeded(self):
        self.assertEqual(protection.decide(None, runs(self.ALL))[0], 'creer')


class ApplyCommand(unittest.TestCase):
    """main() with a fake GitHub: only POST of the expected rule, never PUT or DELETE."""

    def run_main(self, existing, check_runs, argv='--appliquer'):
        calls = []
        state = {'rulesets': [existing] if existing else []}

        def fake_gh(*arguments, body=None):
            calls.append((arguments, body))
            if arguments[:2] == ('-X', 'POST'):
                state['rulesets'] = [dict(body, id=99)]
                return {}
            path = arguments[0]
            if path.endswith('check-runs?per_page=100'):
                return {'check_runs': check_runs}
            if '/rulesets?' in path:
                return [{'id': r.get('id', 1), 'name': r['name']} for r in state['rulesets']]
            if '/rulesets/' in path:
                return state['rulesets'][0]
            raise AssertionError(arguments)
        with mock.patch.object(protection, 'gh', side_effect=fake_gh), mock.patch('builtins.print'):
            code = protection.main(['protection-main.py', argv])
        methods = [arguments[1] for arguments, _ in calls if arguments[0] == '-X']
        return code, methods, calls

    def test_existing_different_rule_is_left_untouched(self):
        existing = copy.deepcopy(protection.expected_ruleset())
        existing.update(id=1)
        existing['bypass_actors'] = [{'actor_type': 'RepositoryRole', 'actor_id': 5, 'bypass_mode': 'always'}]
        code, methods, _ = self.run_main(existing, runs(protection.REQUIRED_CHECKS))
        self.assertEqual((code, methods), (1, []))

    def test_missing_checks_on_main_prevent_creation(self):
        code, methods, _ = self.run_main(None, runs(protection.REQUIRED_CHECKS[:2]))
        self.assertEqual((code, methods), (1, []))

    def test_absent_rule_is_created_exactly_once(self):
        code, methods, calls = self.run_main(None, runs(protection.REQUIRED_CHECKS))
        self.assertEqual((code, methods), (0, ['POST']))
        posted = [body for arguments, body in calls if arguments[:2] == ('-X', 'POST')][0]
        self.assertEqual(posted, protection.expected_ruleset())

    def test_verifier_never_writes(self):
        code, methods, _ = self.run_main(None, runs(protection.REQUIRED_CHECKS), argv='--verifier')
        self.assertEqual((code, methods), (1, []))

    def test_source_contains_no_replacement_or_deletion(self):
        source = TOOL.read_text(encoding='utf-8')
        for forbidden in ("'PUT'", "'PATCH'", "'DELETE'", 'branches/main/protection'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
