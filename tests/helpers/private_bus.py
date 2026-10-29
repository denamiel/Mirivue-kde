# SPDX-License-Identifier: MIT
"""Disposable bus: native Unix/EXTERNAL on Linux, TCP only if Unix is unavailable."""
import errno
from pathlib import Path
import socket
from xml.sax.saxutils import escape


def configuration(directory):
    directory=Path(directory)
    probe=directory/'socket-probe'
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.bind(str(probe))
    except OSError as error:
        if error.errno not in (errno.EPERM,errno.EACCES,errno.EAFNOSUPPORT,errno.EPROTONOSUPPORT):
            raise
        transport='tcp'
        endpoint='<listen>tcp:host=127.0.0.1,port=0,family=ipv4</listen><auth>ANONYMOUS</auth><allow_anonymous/>'
    else:
        transport='unix'
        endpoint='<listen>unix:tmpdir='+escape(str(directory))+'</listen><auth>EXTERNAL</auth>'
    finally:
        probe.unlink(missing_ok=True)
    return transport, ('<busconfig><type>session</type>'+endpoint+
        '<policy context="default"><allow send_destination="*"/>'
        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')


def isolated_environment(environment,address):
    result=dict(environment,DBUS_SESSION_BUS_ADDRESS=address,QT_QPA_PLATFORM='offscreen')
    for key in ('DBUS_STARTER_ADDRESS','DBUS_STARTER_BUS_TYPE','DBUS_SESSION_BUS_PID'):
        result.pop(key,None)
    return result
