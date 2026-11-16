"""Plan a strictly increasing RPM publication; never publish from PRs or schedules."""
import importlib.util
import os
from pathlib import Path
import subprocess


def decision(published, candidate):
    spec = importlib.util.spec_from_file_location('rpm_guard', Path(__file__).parent / 'fedora/verifier-revision-publication.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    compared = guard.compare_evr(guard.spec_evr(candidate), guard.spec_evr(published))
    if compared < 0:
        raise ValueError('Refusing an RPM downgrade')
    return compared > 0


def main():
    publish = False
    if (os.environ.get('GITHUB_EVENT_NAME') in ('push', 'workflow_dispatch')
            and os.environ.get('GITHUB_REF') == 'refs/heads/main'):
        subprocess.run(['git', 'fetch', 'origin', 'publication'], check=True)
        published = subprocess.check_output(['git', 'show', 'FETCH_HEAD:packaging/fedora/mirivue-kde.spec'], text=True)
        publish = decision(published, Path('packaging/fedora/mirivue-kde.spec').read_text())
    print('New RPM revision: ' + str(publish).lower())
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write('publish=' + str(publish).lower() + '\n')


if __name__ == '__main__':
    main()
