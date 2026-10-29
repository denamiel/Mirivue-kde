from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestReleaseContract(unittest.TestCase):
    def test_development_validation_is_not_a_runtime_module(self):
        self.assertFalse((ROOT / 'mirivue' / 'stability.py').exists())
        self.assertTrue((ROOT / 'tests' / 'support' / 'stability.py').exists())
        app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')
        self.assertNotIn('StabilityWorker', app)
        self.assertNotIn('start_stability_check', app)

    def test_window_file_does_not_grow_back_after_consolidation(self):
        lines = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8').count('\n') + 1
        self.assertLess(lines, 5_900)

    def test_application_workers_use_the_central_registry(self):
        direct_starts = []
        for path in (ROOT / 'mirivue').glob('*.py'):
            if path.name in {'runtime_tasks.py', 'responsive.py'}:
                continue
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if 'worker.start()' in line:
                    direct_starts.append(f'{path.name}:{number}')
        self.assertEqual(direct_starts, [])


if __name__ == '__main__':
    unittest.main()

