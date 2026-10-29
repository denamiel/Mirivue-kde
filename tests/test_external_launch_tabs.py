"""A second launch reuses the window by adding a tab, not replacing its view."""

import ast
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from mirivue.launch_targets import LaunchRequest


SOURCE = Path(__file__).resolve().parents[1] / 'mirivue' / 'app.py'


class Socket:
    def __init__(self, payload):
        self.payload = payload
        self.readyRead = SimpleNamespace(connect=lambda callback: None)

    def setParent(self, parent):
        pass

    def bytesAvailable(self):
        return len(self.payload)

    def readAll(self):
        return self.payload

    def disconnectFromServer(self):
        pass

    def deleteLater(self):
        pass


class TestExternalLaunchTabs(unittest.TestCase):
    def test_multi_folder_socket_request_can_arrive_in_several_chunks(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'deliver_launches')
        namespace = {'__package__': 'mirivue', 'json': json, 'Path': Path, 'tr': lambda value: value,
                     'is_browsable_location': lambda value: bool(value), 'LaunchRequest': LaunchRequest}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
        body = json.dumps({'locations': [{'folder': '/a', 'files': []},
                                         {'folder': '/b', 'files': []}]}).encode()
        socket = Socket(body[:15])
        callbacks = []
        socket.readyRead.connect = callbacks.append
        sockets = [socket]
        server = SimpleNamespace(hasPendingConnections=lambda: bool(sockets),
                                 nextPendingConnection=lambda: sockets.pop())
        calls = []
        window = SimpleNamespace(open_external_locations=calls.append,
                                 restore_window=lambda: self.fail('Incomplete JSON is not an empty launch'))
        namespace['deliver_launches'](server, window)
        self.assertFalse(calls)
        socket.payload = body[15:]
        callbacks[0]()
        self.assertEqual([request.folder for request in calls[0]], ['/a', '/b'])

    def test_second_launch_adds_tab_and_keeps_file_selection(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'deliver_launches')
        namespace = {
            '__package__': 'mirivue',
            'json': json,
            'Path': Path,
            'tr': lambda value: value,
            'is_browsable_location': lambda value: bool(value),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            item = folder / 'item'
            item.write_text('download', encoding='utf-8')
            payload = json.dumps({'folder': str(folder), 'files': [str(item)]}).encode()
            sockets = [Socket(payload)]
            server = SimpleNamespace(hasPendingConnections=lambda: bool(sockets),
                                     nextPendingConnection=lambda: sockets.pop())
            calls = []
            window = SimpleNamespace(
                open_external_location=lambda *args: calls.append(('tab', args)),
                navigate=lambda *_: self.fail('The current tab must remain in place'),
                restore_window=lambda: calls.append(('restored', ())),
            )
            namespace['deliver_launches'](server, window)
            self.assertEqual(calls, [('tab', (str(folder), [item]))])


if __name__ == '__main__':
    unittest.main()
