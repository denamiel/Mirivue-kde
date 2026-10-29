# SPDX-License-Identifier: MIT
import errno
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from helpers.private_bus import configuration,isolated_environment

class TestPrivateBusTransport(unittest.TestCase):
    def test_native_linux_transport_uses_external_auth_and_no_anonymous_access(self):
        with tempfile.TemporaryDirectory() as folder,patch('helpers.private_bus.socket.socket',return_value=MagicMock()):
            kind,xml=configuration(folder)
        self.assertEqual(kind,'unix')
        self.assertIn('unix:tmpdir=',xml)
        self.assertIn('<auth>EXTERNAL</auth>',xml)
        self.assertNotIn('ANONYMOUS',xml)
        self.assertNotIn('tcp:',xml)

    def test_restricted_environment_retains_private_loopback_bus(self):
        with tempfile.TemporaryDirectory() as folder,patch('helpers.private_bus.socket.socket',side_effect=PermissionError(errno.EPERM,'restricted')):
            kind,xml=configuration(folder)
        self.assertEqual(kind,'tcp')
        self.assertIn('host=127.0.0.1,port=0',xml)

    def test_other_socket_errors_are_not_hidden_by_a_fallback(self):
        with tempfile.TemporaryDirectory() as folder,patch('helpers.private_bus.socket.socket',side_effect=OSError(errno.EMFILE,'too many files')):
            with self.assertRaises(OSError):configuration(folder)

    def test_private_bus_cannot_inherit_desktop_activation_address(self):
        original=dict(DBUS_SESSION_BUS_ADDRESS='personal',DBUS_STARTER_ADDRESS='personal-starter',DBUS_STARTER_BUS_TYPE='session',DBUS_SESSION_BUS_PID='123',UNCHANGED='value')
        result=isolated_environment(original,'unix:path=/test')
        self.assertEqual(result['DBUS_SESSION_BUS_ADDRESS'],'unix:path=/test')
        self.assertEqual(result['UNCHANGED'],'value')
        self.assertNotIn('DBUS_STARTER_ADDRESS',result)
        self.assertEqual(original['DBUS_STARTER_ADDRESS'],'personal-starter')
