"""Exercise discovery and dispatch between real independent Qt processes."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from helpers.private_bus import configuration as private_bus_configuration, isolated_environment


class TestWindowInstancesDBus(unittest.TestCase):
    def test_detached_window_reuse_batching_and_activation_token_on_private_bus(self):
        daemon = shutil.which('dbus-daemon')
        self.assertIsNotNone(daemon, 'dbus-daemon is required for the desktop integration test')
        root_source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='mirivue-bus-') as temporary:
            root = Path(temporary)
            folders = [root / name for name in ('a', 'b', 'c', 'd')]
            for folder in folders:
                folder.mkdir()
            configuration = root / 'bus.conf'
            # Match a Linux desktop's native authenticated transport. The cloud
            # fallback remains private when its Unix sockets are prohibited.
            transport, bus_xml = private_bus_configuration(root)
            configuration.write_text(bus_xml)
            processes = []
            diagnostics = root / 'processes.log'
            with diagnostics.open('w+') as errors:
                try:
                    bus = subprocess.Popen([daemon, '--config-file='+str(configuration), '--nofork', '--print-address'],
                                           stdout=subprocess.PIPE, stderr=errors, text=True)
                    processes.append(bus)
                    self.assertTrue(select.select([bus.stdout], [], [], 5)[0], 'The disposable bus did not start')
                    address = bus.stdout.readline().strip()
                    self.assertTrue(address.startswith(transport+':'), address)
                    env = isolated_environment(os.environ, address)
                    env['PYTHONPATH'] = str(root_source)+os.pathsep+env.get('PYTHONPATH', '')
                    for name in ('CONFIG', 'CACHE', 'DATA', 'STATE'):
                        directory = root / name.lower()
                        directory.mkdir()
                        env['XDG_'+name+'_HOME'] = str(directory)
                    outputs = []
                    for number, folder in enumerate(folders[:2]):
                        output = root / f'peer{number}.json'
                        outputs.append(output)
                        peer = subprocess.Popen([sys.executable, str(root_source/'tests/helpers/instance_peer.py'),
                                                 str(root), str(folder), str(output)], env=env,
                                                stdout=subprocess.PIPE, stderr=errors, text=True, cwd=root_source)
                        processes.append(peer)
                        self.assertTrue(select.select([peer.stdout], [], [], 8)[0], 'A Qt peer did not start')
                        ready = peer.stdout.readline().strip()
                        if ready != 'READY':
                            errors.flush()
                            self.fail('Qt peer startup failed: '+diagnostics.read_text()[-2500:])
                    client = '''import json,sys
from PySide6.QtWidgets import QApplication
from mirivue.window_instances import route_to_windows
from mirivue.launch_targets import LaunchRequest
app=QApplication(['Mirivue-test-client'])
print('CLIENT initialized',flush=True)
from PySide6.QtDBus import QDBusConnection,QDBusMessage
from mirivue.window_instances import PREFIX,OBJECT,INTERFACE
bus=QDBusConnection.sessionBus()
names=[n for n in bus.interface().registeredServiceNames().value() if n.startswith(PREFIX)]
assert names
for invalid in ('{"locations":null}', '{"locations":[{"folder":"smb://["}]}', '['*1200+'0'+']'*1200):
    message=QDBusMessage.createMethodCall(names[0],OBJECT,INTERFACE,'Dispatch')
    message.setArguments([invalid])
    reply=bus.call(message,timeout=1000)
    assert reply.arguments()==[False], reply.arguments()
print('CLIENT invalid inputs rejected',flush=True)
assert route_to_windows([LaunchRequest(p) for p in json.loads(sys.argv[1])], activation_token='private-test-token', split=True)
print('CLIENT route complete',flush=True)
'''
                    subprocess.run([sys.executable, '-c', client, json.dumps(list(map(str, folders)))],
                                   env=env, stderr=errors, stdout=errors, timeout=8, check=True)
                    until = time.monotonic()+4
                    while time.monotonic()<until:
                        snapshots = [json.loads(p.read_text()) for p in outputs]
                        if any(r['event']=='spawn' for snapshot in snapshots for r in snapshot['records']):
                            break
                        time.sleep(0.02)
                    else:
                        self.fail('The private bus did not dispatch the external batch')
                    self.assertEqual([s['tabs'] for s in snapshots], [1, 1])
                    spawned = [r for s in snapshots for r in s['records'] if r['event']=='spawn']
                    self.assertEqual(len(spawned), 1)
                    self.assertEqual(spawned[0]['folders'], list(map(str, folders[2:])))
                    self.assertTrue(spawned[0]['options']['split'])
                    self.assertEqual(spawned[0]['options']['activation_token'], 'private-test-token')
                    # The second request targets the independently registered,
                    # --new-window peer, not just the first process.
                    subprocess.run([sys.executable, '-c', client, json.dumps([str(folders[1])])],
                                   env=env, stderr=errors, stdout=errors, timeout=8, check=True)
                    until = time.monotonic()+4
                    while time.monotonic()<until:
                        second = json.loads(outputs[1].read_text())
                        activations = [r for r in second['records'] if r['event']=='activate']
                        if activations:
                            break
                        time.sleep(0.02)
                    self.assertEqual(activations[-1]['token'], 'private-test-token')
                    self.assertEqual(second['tabs'], 1)
                except (subprocess.SubprocessError, AssertionError):
                    errors.flush()
                    print("Private bus diagnostics:\n"+diagnostics.read_text(), flush=True)
                    raise
                finally:
                    for process in reversed(processes):
                        if process.poll() is None:
                            process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=3)
                        if process.stdout:
                            process.stdout.close()
