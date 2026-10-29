"""Run real KDE style plugins with isolated configuration and cache directories."""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def available_styles(navigator):
    result = subprocess.run([str(navigator), 'styles'], capture_output=True,
                            text=True, env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), timeout=15)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    installed = json.loads(result.stdout)['styles']
    # The same checks run on ordinary systems without making Union a dependency.
    return ['breeze'] + (['union'] if 'union' in installed else [])


def check_native(test, executable, scenario, style, scheme=None):
    with tempfile.TemporaryDirectory(prefix='mirivue-native-style-') as temporary:
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', MIRIVUE_TEST_STYLE=style)
        for kind in ('CONFIG', 'DATA', 'STATE', 'CACHE'):
            directory = Path(temporary)/kind.lower()
            directory.mkdir()
            environment[f'XDG_{kind}_HOME'] = str(directory)
        diagnostic = os.environ.get('MIRIVUE_TEST_NAVIGATOR_IMAGE_DIR', str(Path(tempfile.gettempdir())/'mirivue-navigator-failures'))
        environment['MIRIVUE_TEST_NAVIGATOR_IMAGE_DIR'] = diagnostic
        if scheme:
            background = '250,249,248' if scheme == 'light' else '20,22,24'
            (Path(environment['XDG_CONFIG_HOME'])/'kdeglobals').write_text(
                '[Colors:View]\nBackgroundNormal=' + background + '\n'
                '[ColorEffects:Inactive]\nEnable=false\n')
        result = subprocess.run([str(executable), scenario], env=environment,
                                capture_output=True, text=True, timeout=20)
        test.assertEqual(result.returncode, 0, result.stdout + result.stderr + "\nDiagnostic images: " + diagnostic)
        report = json.loads(result.stdout.strip())
        test.assertTrue(report['ok'])
        test.assertEqual(report['scenario'], scenario)
        return report
