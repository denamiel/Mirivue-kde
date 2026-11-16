"""Publish Arch assets only from fully validated, protected main commits."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = 'denamiel/Mirivue-kde'
WORKFLOWS = ('fedora-package.yml', 'arch-package.yml')
VERSION = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$')


def api(path, method='GET', body=None, optional=False):
    result = subprocess.run(['gh', 'api', '--method', method, 'repos/' + REPO + '/' + path,
        *(['--input', '-'] if body is not None else [])], input=json.dumps(body) if body is not None else None,
        capture_output=True, text=True)
    if optional and result.returncode and 'HTTP 404' in result.stderr:
        return None
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout or '{}')


def version_key(value):
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError('Unsupported release version')
    major, minor, patch, stage, number = match.groups()
    return int(major), int(minor), int(patch), {'alpha': 0, 'beta': 1, 'rc': 2, None: 3}[stage], int(number or 0)


def plan(sha, version):
    version_key(version)
    branch = api('branches/main')
    if not branch['protected'] or branch['commit']['sha'] != sha:
        raise ValueError('Only the current protected main commit may publish')
    release = api('releases/tags/v' + version, optional=True)
    if release and not release['draft']:
        return None  # An ordinary merge with the same version never replaces it.
    published = [r for r in api('releases?per_page=100') if not r['draft'] and VERSION.fullmatch(r['tag_name'].removeprefix('v'))]
    if published and version_key(version) <= max(version_key(r['tag_name'].removeprefix('v')) for r in published):
        raise ValueError('New releases must have a strictly increasing version')
    runs = {}
    for workflow in WORKFLOWS:
        found = api(f'actions/workflows/{workflow}/runs?branch=main&event=push&per_page=100')['workflow_runs']
        matching = [r for r in found if r['head_sha'] == sha and r['head_branch'] == 'main' and r['event'] == 'push']
        if not matching:
            return None
        run = max(matching, key=lambda r: r['id'])
        if run['status'] != 'completed' or run['conclusion'] != 'success':
            return None
        runs[workflow] = run['id']
    return dict(sha=sha, version=version, arch_run=runs['arch-package.yml'], fedora_run=runs['fedora-package.yml'])


def verify_assets(directory, version):
    directory = Path(directory)
    pkgver = version.replace('-', '').replace('beta.', 'beta').replace('alpha.', 'alpha').replace('rc.', 'rc')
    expected = {f'mirivue-kde-{pkgver}-1-x86_64.pkg.tar.zst', f'mirivue-kde-debug-{pkgver}-1-x86_64.pkg.tar.zst'}
    entries = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9_.+~-]+)', line)
        if not match or match[2] in entries:
            raise ValueError('Invalid or duplicate checksum entry')
        entries[match[2]] = match[1]
    if set(entries) != expected or {p.name for p in directory.iterdir()} != expected | {'SHA256SUMS'}:
        raise ValueError('Unexpected release assets')
    for name, checksum in entries.items():
        path = directory / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError('Release checksum mismatch')
    return expected | {'SHA256SUMS'}


def publish(expected, directory):
    if plan(expected['sha'], expected['version']) != expected:
        raise ValueError('Release plan is stale or no longer fully validated')
    assets = verify_assets(directory, expected['version'])
    tag = 'v' + expected['version']
    reference = api('git/ref/tags/' + tag, optional=True)
    if reference is None:
        api('git/refs', 'POST', {'ref': 'refs/tags/' + tag, 'sha': expected['sha']})
    else:
        target = reference['object']
        for _ in range(5):
            if target['type'] != 'tag':
                break
            target = api('git/tags/' + target['sha'])['object']
        if target['type'] != 'commit' or target['sha'] != expected['sha']:
            raise ValueError('Existing tag refers to a different commit')
    release = api('releases/tags/' + tag, optional=True)
    if release is None:
        release = api('releases', 'POST', dict(tag_name=tag, target_commitish=expected['sha'],
            name='Mirivue KDE ' + expected['version'], draft=True, prerelease='-' in expected['version'],
            body=f"Version validée sur le commit `{expected['sha']}`.\n\n[Modifications](https://github.com/{REPO}/blob/{expected['sha']}/CHANGELOG.md)\n\nRPM Fedora 44/45 vérifiés dans COPR ; paquets Arch ci-joints. Le dépôt Pacman signé se met à jour après ses propres contrôles."))
    if not release['draft']:
        raise ValueError('Published releases are immutable')
    existing = {a['name'] for a in release['assets']}
    if existing - assets:
        raise ValueError('Unexpected assets in existing draft')
    for name in sorted(assets):
        path = Path(directory) / name
        if name in existing:
            with tempfile.TemporaryDirectory() as folder:
                subprocess.run(['gh', 'release', 'download', tag, '--repo', REPO, '--pattern', name, '--dir', folder], check=True)
                if Path(folder, name).read_bytes() != path.read_bytes():
                    raise ValueError('Refusing to replace an existing asset')
        else:
            subprocess.run(['gh', 'release', 'upload', tag, '--repo', REPO, str(path)], check=True)
    # Recheck the current head immediately before making the draft public.
    if api('branches/main')['commit']['sha'] != expected['sha']:
        raise ValueError('main moved during publication; draft retained')
    api('releases/' + str(release['id']), 'PATCH', {'draft': False})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('plan', 'publish'))
    parser.add_argument('--directory', default='dist')
    args = parser.parse_args()
    if args.action == 'plan':
        sha = os.environ['GITHUB_SHA']
        event_sha = os.environ.get('EVENT_SHA') or sha
        if event_sha != sha:
            value = None
        else:
            tree = ast.parse(Path('mirivue/__init__.py').read_text())
            version = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
            value = plan(sha, version)
        Path('release-plan.json').write_text(json.dumps(value))
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write('publish=' + str(value is not None).lower() + '\n')
            if value:
                output.write('arch_run=' + str(value['arch_run']) + '\n')
    else:
        publish(json.loads(Path('release-plan.json').read_text()), args.directory)


if __name__ == '__main__':
    main()
