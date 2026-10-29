"""A long running Ark extraction must remain cancellable without a fixed deadline."""

import ast
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_extractor(clock):
    tree = ast.parse((ROOT / 'mirivue' / 'archive_backend.py').read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'extract_rar_with_ark')
    namespace = dict(Path=Path, tempfile=tempfile, subprocess=subprocess,
                     time=clock, os=os, errno=errno, shutil=shutil,
                     preflight_archive_members=lambda _path: None)
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<rar>', 'exec'), namespace)
    return namespace['extract_rar_with_ark']


class TestRarExtractionDuration(unittest.TestCase):
    def test_long_running_ark_is_not_killed_by_elapsed_time(self):
        ticks = [0]

        def sleep(_duration):
            ticks[0] += 200

        class Process:
            returncode = 1

            def __init__(self):
                self.polls = 0

            def poll(self):
                self.polls += 1
                return None if self.polls <= 3 else self.returncode

        process = Process()
        clock = SimpleNamespace(monotonic=lambda: ticks[0], sleep=sleep)
        extract = load_extractor(clock)
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(subprocess, 'Popen', return_value=process):
                ok, message = extract('ark', Path(directory) / 'big.rar', Path(directory) / 'out')
        self.assertFalse(ok)
        self.assertGreater(ticks[0], 120)
        self.assertEqual(message, 'Ark n’a pas pu extraire l’archive RAR.')


if __name__ == '__main__':
    unittest.main()
