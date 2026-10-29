#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Validate metadata; allow only the documented absence of a homepage."""
import os
import re
import subprocess
import sys


def accepted(returncode, output):
    if returncode == 0:
        return True
    issues = re.findall(r'^[WE]:.*$', output, re.MULTILINE)
    return (
        returncode > 0
        and len(issues) == 1
        and re.fullmatch(r'W: org\.pdenams\.Mirivue\.Qt:[^\n]*: url-homepage-missing', issues[0]) is not None
        and re.search(r'Validation failed: warnings: 1(?:, pedantic: \d+)?\s*$', output) is not None
    )


def self_test():
    warning = 'W: org.pdenams.Mirivue.Qt:~: url-homepage-missing\n\n✘ Validation failed: warnings: 1, pedantic: 1\n'
    assert accepted(0, 'Validation successful')
    for code in (1, 3, 7):
        assert accepted(code, warning)
    assert not accepted(-15, warning)
    assert not accepted(1, warning.replace('url-homepage-missing', 'xml-invalid'))
    assert not accepted(1, 'E: broken XML\n' + warning)
    assert not accepted(1, 'W: additional issue\n' + warning)
    assert not accepted(1, 'command failed')
    assert not accepted(1, warning.replace('warnings: 1', 'errors: 1, warnings: 1'))
    assert not accepted(1, warning.replace('org.pdenams.Mirivue.Qt', 'other.app'))
    print('AppStream validator policy: OK')


def main():
    if sys.argv[1:] == ['--self-test']:
        self_test()
        return 0
    if len(sys.argv) < 2:
        print('Usage: valider-appstream.py FILE...', file=sys.stderr)
        return 2
    r = subprocess.run(
        ['appstreamcli', 'validate', '--no-net', '--no-color', *sys.argv[1:]],
        env={**os.environ, 'LC_ALL': 'C'}, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    print(r.stdout, end='')
    if accepted(r.returncode, r.stdout):
        if r.returncode:
            print('Absence de site officiel acceptee ; autres controles conserves.')
        return 0
    return r.returncode if r.returncode > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
