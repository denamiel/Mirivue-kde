"""Test --split and --select through main(), not just the argument parser."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class TestRealLaunch(unittest.TestCase):
    def test_split_and_select_keep_requests_in_the_correct_panes(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='mirivue-main-') as temporary:
            root = Path(temporary)
            folders = [root/'a', root/'b']
            files = []
            for folder in folders:
                folder.mkdir()
                item = folder/'item.txt'
                item.write_text('test')
                files.append(item)
            scenarios = [
                (['--split', '--select', *map(str,files)],
                 dict(folders=list(map(str,folders)), selected=[[str(p)] for p in files])),
                (['--select', str(folders[0])],
                 dict(folders=[str(root)], selected=[[str(folders[0])]])),
            ]
            for number, (arguments, expected) in enumerate(scenarios):
                with self.subTest(arguments=arguments):
                    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', XDG_CURRENT_DESKTOP='GNOME')
                    env['PYTHONPATH'] = str(source)+os.pathsep+env.get('PYTHONPATH','')
                    case = root/str(number)
                    case.mkdir()
                    for name in ('CONFIG','CACHE','STATE','DATA'):
                        env['XDG_'+name+'_HOME'] = str(case/name.lower())
                    result = subprocess.run([sys.executable, str(source/'tests/helpers/launch_main.py'),
                                             str(case), json.dumps(arguments), json.dumps(expected)],
                                            cwd=source, env=env, capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr[-4000:])
                    self.assertIn('LAUNCH_OK',result.stdout)
