"""Stable natural-name keys shared by directory listing and Qt sorting."""

import re
import ctypes
import os
from functools import lru_cache, total_ordering
from pathlib import Path


def _source_fallback_key(name):
    parts = []
    for part in re.split(r'([0-9]+)', name.casefold()):
        if part.isascii() and part.isdigit():
            digits = part.lstrip('0') or '0'
            parts.append((1, len(digits), digits))
        else:
            parts.append((0, part))
    return (parts, name.casefold(), name)


@lru_cache(maxsize=1)
def native_comparator():
    """Load the pinned Dolphin comparator from the Qt presentation library."""
    root = Path(__file__).resolve().parent
    candidates = [os.environ.get('MIRIVUE_TEST_PRESENTATION_LIBRARY')]
    candidates += [folder / 'libmirivue-item-presentation.so' for folder in
                   (root / 'tools', root.parent / 'tools', root.parent / 'native' / 'bin')]
    for path in candidates:
        if not path:
            continue
        try:
            library = ctypes.CDLL(str(path))
            compare = library.mirivue_natural_compare
            compare.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            compare.restype = ctypes.c_int
            compare._library = library
            return compare
        except (OSError, AttributeError):
            continue
    return None


@total_ordering
class NaturalNameKey:
    """Cache the UTF-8 name once; comparisons execute Dolphin's C++ code."""
    __slots__ = ('name', 'encoded', 'fallback')

    def __init__(self, name):
        self.name = str(name)
        self.encoded = self.name.encode('utf-8', errors='replace')
        self.fallback = None

    def compare(self, other):
        compare = native_comparator()
        if compare is not None:
            return compare(self.encoded, other.encoded)
        # Uncompiled source checkouts can still enumerate folders. Installed
        # packages and the release validator build and require the native ABI.
        if self.fallback is None:
            self.fallback = _source_fallback_key(self.name)
        if other.fallback is None:
            other.fallback = _source_fallback_key(other.name)
        return (self.fallback > other.fallback) - (self.fallback < other.fallback)

    def __lt__(self, other):
        if not isinstance(other, NaturalNameKey):
            return NotImplemented
        return self.compare(other) < 0

    def __eq__(self, other):
        if not isinstance(other, NaturalNameKey):
            return NotImplemented
        return self.compare(other) == 0


def natural_name_key(name):
    return NaturalNameKey(name)


def cached_natural_name_key(row):
    """Reuse a row's comparison key until its displayed name changes."""
    name = str(row.values[0])
    cached = getattr(row, '_natural_sort_key', None)
    if cached is None or cached[0] != name:
        cached = (name, natural_name_key(name))
        row._natural_sort_key = cached
    return cached[1]


@lru_cache(maxsize=1)
def native_string_comparator():
    natural = native_comparator()
    if natural is None:
        return None
    compare = natural._library.mirivue_string_compare
    compare.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    compare.restype = ctypes.c_int
    compare._library = natural._library
    return compare


@lru_cache(maxsize=8192)
def string_compare(a, b, mode=0):
    compare = native_string_comparator()
    if compare is not None:
        return compare(str(a).encode('utf-8'), str(b).encode('utf-8'), mode)
    if mode == 0:
        return NaturalNameKey(a).compare(NaturalNameKey(b))
    key_a, key_b = ((str(a), str(b)) if mode == 1 else (str(a).casefold(), str(b).casefold()))
    return (key_a > key_b) - (key_a < key_b) or ((str(a)>str(b))-(str(a)<str(b)))
