"""Exercise the compiled KF6 programs, using disposable files and preferences."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class TestKioVisibilityIdentity(unittest.TestCase):
    def native_path(self, variable, name):
        candidate = os.environ.get(variable)
        if not candidate:
            library = os.environ.get('MIRIVUE_TEST_PRESENTATION_LIBRARY', '')
            candidate = str(Path(library).parent / name) if library else ''
        self.assertTrue(candidate and Path(candidate).is_file(),
                        'Compile the KF6 helpers with Valider-RC193.sh before testing.')
        return candidate

    def environment(self, root):
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        for name in ('CONFIG', 'DATA', 'CACHE', 'STATE'):
            directory = root/name.lower()
            directory.mkdir()
            environment['XDG_'+name+'_HOME'] = str(directory)
        if os.environ.get('MIRIVUE_TEST_KDE_PLUGIN_PATH'):
            environment['QT_PLUGIN_PATH'] = os.environ['MIRIVUE_TEST_KDE_PLUGIN_PATH']
        return environment

    def test_real_kio_lister_and_local_media_inventory_agree_about_hidden_files(self):
        from mirivue.file_visibility import local_is_hidden
        executable = self.native_path('MIRIVUE_TEST_KIO_LIST_EXECUTABLE', 'mirivue-kio-list')
        with tempfile.TemporaryDirectory(prefix='mirivue-kio-hidden-') as temporary:
            root = Path(temporary)
            folder = root/'files'
            folder.mkdir()
            for name in ('normal', 'secret', '.dot', ' name with spaces ', 'épisode'):
                (folder/name).write_text('test')
            (folder/'.hidden').write_bytes(b'\xef\xbb\xbfsecret\n name with spaces \n')
            environment = self.environment(root)
            result = subprocess.run([executable, folder.as_uri()], capture_output=True,
                                    text=True, timeout=12, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload['ok'], payload)
            states = {row['name']: row['hidden'] for row in payload['entries']}
            self.assertEqual(set(states), {p.name for p in folder.iterdir()})
            self.assertEqual({r['realName'] for r in payload['entries']}, set(states))
            for name, hidden in states.items():
                self.assertEqual(hidden, local_is_hidden(folder/name), name)
            self.assertTrue(states['secret'])
            self.assertTrue(states[' name with spaces '])
            self.assertFalse(states['normal'])

    def test_native_places_bridge_returns_the_actual_bookmark_caption(self):
        library = self.native_path('MIRIVUE_TEST_PLACES_LIBRARY', 'libmirivue-kio-places-widget.so')
        with tempfile.TemporaryDirectory(prefix='mirivue-kio-caption-') as temporary:
            root = Path(temporary)
            folder = root/'films'
            folder.mkdir()
            environment = self.environment(root)
            bookmark = Path(environment['XDG_DATA_HOME'])/'user-places.xbel'
            bookmark.write_text('<xbel><bookmark href="'+folder.as_uri()+'">'
                                '<title>Mes films personnels</title></bookmark></xbel>')
            script = '''import ctypes,json,sys
import shiboken6
from PySide6.QtWidgets import QApplication,QWidget
app=QApplication(['Mirivue-caption-test'])
parent=QWidget()
library=ctypes.CDLL(sys.argv[1])
library.mirivue_places_create.argtypes=[ctypes.c_void_p]*10+[ctypes.c_char_p]
library.mirivue_places_create.restype=ctypes.c_void_p
pointer=library.mirivue_places_create(shiboken6.getCppPointer(parent)[0],*([None]*9),b'Split')
assert pointer
library.mirivue_places_location_identity.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
library.mirivue_places_location_identity.restype=ctypes.c_char_p
print(library.mirivue_places_location_identity(pointer,sys.argv[2].encode()).decode())
'''
            result = subprocess.run([sys.executable, '-c', script, library, folder.as_uri()],
                                    capture_output=True, text=True, timeout=15, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            identity = json.loads(result.stdout)
            self.assertEqual(identity['name'], 'Mes films personnels')
            self.assertTrue(identity['icon'])


if __name__ == '__main__':
    unittest.main()
