"""Verify stable COPR targets and the exact git archive contained in their SRPM."""
import gzip
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import json
import urllib.request
BASE = 'https://copr.fedorainfracloud.org/api_3/'
TARGETS = {'fedora-44-x86_64', 'fedora-45-x86_64'}


def api(path):
    with urllib.request.urlopen(BASE + path, timeout=40) as response:
        return json.load(response)


def archive_files(data):
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        files = {}
        for item in archive.getmembers():
            if item.isfile():
                files[item.name] = (item.mode, hashlib.sha256(archive.extractfile(item).read()).hexdigest())
            elif item.issym():
                files[item.name] = ('link', item.linkname)
        return archive.pax_headers.get('comment'), files


def extract_source_archive(payload, name):
    # RPM 6 prefixes source payload paths with './'; older RPMs omit it.
    result = subprocess.run(['cpio', '--quiet', '-i', '--to-stdout', name, './' + name],
                            input=payload, capture_output=True, check=True).stdout
    if not result:
        raise ValueError('Expected source archive is missing from the RPM payload')
    return result


def verify_sources(srpm, version, sha):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'source.rpm'
        with urllib.request.urlopen(srpm, timeout=60) as response:
            path.write_bytes(response.read(128 * 1024 * 1024 + 1))
        if path.stat().st_size > 128 * 1024 * 1024:
            raise ValueError('Source RPM exceeds size limit')
        payload = subprocess.check_output(['rpm2cpio', str(path)])
        actual = extract_source_archive(payload, f'Mirivue-{version}-KDE.tar.gz')
    expected = subprocess.check_output(['git', 'archive', '--format=tar', f'--prefix=Mirivue-{version}-KDE/', sha])
    comment, files = archive_files(gzip.decompress(actual))
    if comment != sha or files != archive_files(expected)[1]:
        raise ValueError('COPR source archive does not match the tested commit')


def main():
    spec = importlib.util.spec_from_file_location('rpm_guard', Path(__file__).parent / 'fedora/verifier-revision-publication.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    _, version, release = guard.spec_evr(Path('packaging/fedora/mirivue-kde.spec').read_text())
    expected = version + '-' + release
    for _ in range(60):
        builds = api('build/list/?ownername=pdenams&projectname=Mirivue-kde&limit=10')['items']
        matching = [b for b in builds if (b.get('source_package') or {}).get('version') == expected]
        if matching:
            build = max(matching, key=lambda b: b['id'])
            states = {b['name']: b['state'] for b in api(f"build-chroot/list/?build_id={build['id']}")['items']}
            print(build['id'], expected, states, flush=True)
            if any(states.get(name) in ('failed', 'canceled') for name in TARGETS):
                raise ValueError('COPR stable build failed')
            if all(states.get(name) == 'succeeded' for name in TARGETS):
                verify_sources(build['source_package']['url'], version, os.environ['GITHUB_SHA'])
                print('Both stable targets and the exact source commit are verified.')
                return
        time.sleep(20)
    raise TimeoutError('COPR publication did not complete within twenty minutes')


if __name__ == '__main__':
    main()
