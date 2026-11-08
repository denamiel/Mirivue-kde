#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Refuse a COPR publication whose RPM EVR does not strictly increase.

Usage : verifier-revision-publication.py SPEC_PUBLIE SPEC_CANDIDAT
Codes : 0 = candidate strictly newer ; 1 = equal or older (refused) ;
        2 = unreadable spec or unsupported macro (refused).

The comparison follows rpm's rpmvercmp() (epoch, then version, then release,
including the "~" and "^" rules), so it matches what dnf will decide.
"""
import re
import sys

ASCII_DIGITS = '0123456789'
ASCII_ALPHA = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def _alnum(character):
    return character in ASCII_DIGITS or character in ASCII_ALPHA


def rpmvercmp(a, b):
    """Return 1, 0 or -1 like rpm's rpmvercmp(a, b)."""
    if a == b:
        return 0
    i = j = 0
    while i < len(a) or j < len(b):
        while i < len(a) and not _alnum(a[i]) and a[i] not in '~^':
            i += 1
        while j < len(b) and not _alnum(b[j]) and b[j] not in '~^':
            j += 1
        # A tilde sorts before anything, even the end of the string.
        if (i < len(a) and a[i] == '~') or (j < len(b) and b[j] == '~'):
            if i >= len(a) or a[i] != '~':
                return 1
            if j >= len(b) or b[j] != '~':
                return -1
            i += 1
            j += 1
            continue
        # A caret sorts after the end of the string but before anything else.
        if (i < len(a) and a[i] == '^') or (j < len(b) and b[j] == '^'):
            if i >= len(a):
                return -1
            if j >= len(b):
                return 1
            if a[i] != '^':
                return 1
            if b[j] != '^':
                return -1
            i += 1
            j += 1
            continue
        if i >= len(a) or j >= len(b):
            break
        start_a, start_b = i, j
        numeric = a[i] in ASCII_DIGITS
        kind = ASCII_DIGITS if numeric else ASCII_ALPHA
        while i < len(a) and a[i] in kind:
            i += 1
        while j < len(b) and b[j] in kind:
            j += 1
        segment_a, segment_b = a[start_a:i], b[start_b:j]
        if not segment_b:
            return 1 if numeric else -1
        if numeric:
            segment_a, segment_b = segment_a.lstrip('0'), segment_b.lstrip('0')
            if len(segment_a) != len(segment_b):
                return 1 if len(segment_a) > len(segment_b) else -1
        if segment_a != segment_b:
            return 1 if segment_a > segment_b else -1
    if i >= len(a) and j >= len(b):
        return 0
    return -1 if i >= len(a) else 1


def compare_evr(left, right):
    """Compare (epoch, version, release) tuples the way rpm does."""
    if int(left[0]) != int(right[0]):
        return 1 if int(left[0]) > int(right[0]) else -1
    return rpmvercmp(left[1], right[1]) or rpmvercmp(left[2], right[2])


def spec_evr(text):
    """Read Epoch/Version/Release from a spec; only %{?dist} is accepted."""
    values = {}
    for line in text.splitlines():
        match = re.match(r'^(Epoch|Version|Release)\s*:\s*(\S+)\s*$', line)
        if match and match.group(1) not in values:
            values[match.group(1)] = match.group(2)
    if 'Version' not in values or 'Release' not in values:
        raise ValueError('Version ou Release introuvable dans le spec')
    release = values['Release'].replace('%{?dist}', '')
    for field in (values.get('Epoch', '0'), values['Version'], release):
        if '%' in field:
            raise ValueError(f'macro non prise en charge : {field}')
    return values.get('Epoch', '0'), values['Version'], release


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding='utf-8') as published, open(argv[2], encoding='utf-8') as candidate:
            old, new = spec_evr(published.read()), spec_evr(candidate.read())
    except (OSError, ValueError) as error:
        print(f'Publication refusée : {error}', file=sys.stderr)
        return 2
    label = lambda evr: f'{evr[0]}:{evr[1]}-{evr[2]}'
    if compare_evr(new, old) <= 0:
        print(f'Publication refusée : {label(new)} n’est pas supérieure à la version publiée {label(old)}.',
              file=sys.stderr)
        return 1
    print(f'Révision croissante : {label(old)} → {label(new)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
