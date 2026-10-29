import os
import ast
import subprocess
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mirivue.launch_targets import parse_show_items


ROOT = Path(__file__).resolve().parents[1]


class TestShowItems(unittest.TestCase):
    def test_selects_files_and_folders_from_the_first_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / 'document téléchargé.pdf'
            second = root / 'dossier'
            elsewhere = root / 'autre' / 'ignoré.txt'
            first.write_bytes(b'pdf')
            second.mkdir()
            elsewhere.parent.mkdir()
            elsewhere.write_text('x', encoding='utf-8')
            request = parse_show_items((first.as_uri(), second.as_uri(), elsewhere.as_uri()))
            self.assertEqual(request.folder, str(root))
            self.assertEqual(request.files, (str(first), str(second)))

    def test_unknown_item_falls_back_without_crashing(self):
        request = parse_show_items(('file:///fichier/absent',))
        self.assertEqual(request.folder, '')
        self.assertEqual(request.files, ())


class TestActivationFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'mirivue' / 'filemanager1.py').read_text(encoding='utf-8')
        cls.app = (ROOT / 'mirivue' / 'app.py').read_text(encoding='utf-8')

    def test_implements_standard_interface_and_methods(self):
        self.assertIn("SERVICE_NAME = 'org.freedesktop.FileManager1'", self.source)
        self.assertIn("OBJECT_PATH = '/org/freedesktop/FileManager1'", self.source)
        for method in ('ShowItems', 'ShowFolders', 'ShowItemProperties'):
            self.assertIn(f'def {method}(', self.source)

    def test_user_activation_is_limited_to_mirivue_as_default(self):
        self.assertIn("xdg-mime', 'query', 'default', 'inode/directory'", self.source)
        self.assertIn("DESKTOP_ID = 'org.pdenams.Mirivue.Qt.desktop'", self.source)
        self.assertIn("'dbus-1' / 'services' / 'org.freedesktop.FileManager1.service'", self.source)
        self.assertIn('# Managed by Mirivue KDE', self.source)

    def test_activation_dispatches_each_desktop_without_starting_gui(self):
        launcher = ROOT / 'Lancer.sh'
        for desktop, expected in (
            ('GNOME', 'nautilus'), ('GNOME:KDE', 'nautilus'),
            ('KDE', 'mirivue'), ('KDE:Plasma', 'mirivue'),
            ('Cinnamon', 'unsupported'), ('XFCE', 'unsupported'),
        ):
            with self.subTest(desktop=desktop):
                result = subprocess.run(
                    [str(launcher), '--file-manager-activation-check'],
                    env={**os.environ, 'XDG_CURRENT_DESKTOP': desktop},
                    capture_output=True, text=True, timeout=3, check=True,
                )
                self.assertEqual(result.stdout.strip(), expected)

    def test_gnome_never_installs_or_claims_mirivue_service(self):
        tree = ast.parse(self.source)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        namespace = {'os': os}
        exec(compile(ast.Module(body=[functions['plasma_session']], type_ignores=[]),
                     'filemanager1.py', 'exec'), namespace)
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME:KDE'}):
            self.assertFalse(namespace['plasma_session']())
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'KDE'}):
            self.assertTrue(namespace['plasma_session']())
        exec(compile(ast.Module(body=[functions['ensure_user_activation']], type_ignores=[]),
                     'filemanager1.py', 'exec'), namespace)
        with tempfile.TemporaryDirectory() as temporary:
            service = Path(temporary) / 'org.freedesktop.FileManager1.service'
            service.write_text('# Managed by Mirivue KDE\nExec=/old/Lancer.sh --file-manager-service\n', encoding='utf-8')
            namespace['activation_file_path'] = lambda: service
            namespace['ACTIVATION_MARKER'] = '# Managed by Mirivue KDE'
            namespace['installed_launcher'] = lambda: '/new/Lancer.sh'
            namespace['activation_contents'] = lambda launcher: (
                '# Managed by Mirivue KDE\nExec=' + launcher + ' --file-manager-service\n')
            namespace['tempfile'] = tempfile
            namespace['Path'] = Path
            with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME'}):
                self.assertFalse(namespace['ensure_user_activation']())
            self.assertIn('Exec=/new/Lancer.sh', service.read_text(encoding='utf-8'))
            self.assertTrue(service.exists(), 'GNOME doit conserver le service délégué pour Plasma')
            service.unlink()
            with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME'}):
                self.assertFalse(namespace['ensure_user_activation']())
            self.assertFalse(service.exists(), 'GNOME ne doit pas créer un nouveau service Mirivue')
        self.assertIn('if not plasma_session() or not ensure_user_activation():', self.source)
        register = functions['register_file_manager_service']
        exec(compile(ast.Module(body=[register], type_ignores=[]), 'filemanager1.py', 'exec'),
             namespace)
        namespace['ensure_user_activation'] = lambda: self.fail('GNOME ne doit pas enregistrer le nom D-Bus')
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'GNOME'}):
            self.assertFalse(namespace['register_file_manager_service'](object(), object()))

    def test_application_registers_after_showing_the_main_window(self):
        shown = self.app.index('window.show()')
        registered = self.app.index('register_file_manager_service(app, window)', shown)
        self.assertLess(shown, registered)

    def test_package_does_not_claim_dolphins_system_activation_file(self):
        package = (ROOT / 'packaging' / 'PKGBUILD.template').read_text(encoding='utf-8')
        self.assertNotIn('/usr/share/dbus-1/services/org.freedesktop.FileManager1.service', package)

    def test_browser_request_uses_the_shared_existing_view_router(self):
        tree = ast.parse(self.source)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'FileManager1')
        show = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_show')
        namespace = {
            'parse_show_items': lambda values: SimpleNamespace(folder='/tmp/downloads', files=('/tmp/downloads/item',)),
            'parse_launch_requests': lambda values, **kwargs: [SimpleNamespace(folder='/tmp/downloads', files=('/tmp/downloads/item',))],
        }
        exec(compile(ast.Module(body=[show], type_ignores=[]), 'filemanager1.py', 'exec'), namespace)
        routed = []
        setting = {'startup/allow_multiple_instances': False}
        window = SimpleNamespace(
            settings=SimpleNamespace(value=lambda key, default, type=None: setting.get(key, default)),
            open_external_locations=lambda requests, **kwargs: routed.append(('tab', tuple((r.folder, r.files) for r in requests), kwargs)),
            open_place_in_new_window=lambda *args, **kwargs: routed.append(('window', args, kwargs)),
        )
        service = SimpleNamespace(window=window)
        namespace['_show'](service, ['file:///tmp/downloads/item'])
        self.assertEqual(routed[-1], ('tab', (('/tmp/downloads', ('/tmp/downloads/item',)),), {'properties': False, 'activation_token': ''}))
        setting['startup/allow_multiple_instances'] = True
        namespace['_show'](service, ['file:///tmp/downloads/item'])
        self.assertEqual(routed[-1], ('tab', (('/tmp/downloads', ('/tmp/downloads/item',)),), {'properties': False, 'activation_token': ''}))


if __name__ == '__main__':
    unittest.main()
