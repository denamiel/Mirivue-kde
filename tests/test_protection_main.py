# SPDX-License-Identifier: MIT
"""The main-branch ruleset must require every mandatory CI check by its real name."""
import copy
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
        self.assertEqual(set(protection.REQUIRED_CHECKS), actual)

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

    def test_tool_only_touches_its_named_ruleset(self):
        source = TOOL.read_text(encoding='utf-8')
        self.assertNotIn("'DELETE'", source)
        self.assertNotIn('branches/main/protection', source)
        self.assertIn("summary.get('name') == NAME", source)


if __name__ == '__main__':
    unittest.main()
