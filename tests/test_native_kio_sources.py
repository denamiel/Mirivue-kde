from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'native'


class TestNativeKioSources(unittest.TestCase):
    def test_all_runtime_helpers_have_reviewable_sources(self):
        expected = {
            'mirivue-kio-list': 'kio-list.cpp',
            'mirivue-kio-places': 'kio-places.cpp',
            'mirivue-kio-preview': 'kio-preview.cpp',
            'mirivue-kio-service': 'kio-service.cpp',
            'mirivue-kio-transfer': 'kio-transfer.cpp',
        }
        cmake = (NATIVE / 'CMakeLists.txt').read_text(encoding='utf-8')
        for executable, source_name in expected.items():
            source = (NATIVE / source_name).read_text(encoding='utf-8')
            self.assertIn('SPDX-License-Identifier: MIT', source)
            self.assertIn(f'add_executable({executable} {source_name})', cmake)
            self.assertFalse((ROOT / 'tools' / executable).exists())
        self.assertIn('add_executable(mirivue-job-progress job-progress.cpp)', cmake)
        self.assertIn('KUiServerV2JobTracker', (NATIVE / 'job-progress.cpp').read_text(encoding='utf-8'))

    def test_service_protocol_covers_current_operations(self):
        service = (NATIVE / 'kio-service.cpp').read_text(encoding='utf-8')
        for command in ('copy', 'move', 'link', 'trash', 'mkdir', 'cancel',
                        'state', 'undo', 'redo', 'shutdown'):
            self.assertIn(f'"{command}"', service)
        for event in ('complete', 'progress', 'state'):
            self.assertIn(f'"{event}"', service)


if __name__ == '__main__':
    unittest.main()
