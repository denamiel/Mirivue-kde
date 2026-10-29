# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
# Original Mirivue implementation; behavior compared with Dolphin v26.08.2.
# No Dolphin source code is copied into this module.
"""Discover every Mirivue window on the session bus, including --new-window.

D-Bus service ownership supplies liveness and cleanup; no stale on-disk window
registry is maintained. The local socket remains a fallback without a session bus.
"""
import json
import os
import time
from PySide6.QtCore import QObject, Slot, QTimer, Signal
from . import __version__
from .launch_targets import LaunchRequest, is_browsable_location

PREFIX = 'org.pdenams.Mirivue.Instance.v' + __version__.replace('.', '_').replace('-', '_') + '.p'
INTERFACE = 'org.pdenams.Mirivue.Window'
OBJECT = '/Mirivue/Window'


def request_payload(requests, **options):
    return dict(locations=[dict(folder=r.folder, files=list(r.files)) for r in requests], **options)


# Mirivue IPC limits, not Dolphin limits: bound allocation and queued work.
MAX_MESSAGE_BYTES = 1 << 20
MAX_LOCATIONS = 100
MAX_STRING_LENGTH = 32768  # UTF-8 bytes: permits long network URLs, bounds tokens.
MAX_FILES = 10000


def normalize_payload(payload):
    """Return a detached, typed payload or None; never enqueue raw input."""
    if not isinstance(payload, dict) or 'detached_tab' in payload:
        return None
    allowed = {'locations', 'split', 'force_tabs', 'properties', 'activate_first', 'activation_token'}
    if set(payload) - allowed:
        return None
    locations = payload.get('locations')
    if not isinstance(locations, list) or not 1 <= len(locations) <= MAX_LOCATIONS:
        return None
    def bounded(value):
        if not isinstance(value, str) or '\x00' in value:
            return False
        try:
            return len(value.encode('utf-8')) <= MAX_STRING_LENGTH
        except UnicodeError:
            return False
    result = {'locations': []}
    total_files = 0
    for item in locations:
        if not isinstance(item, dict) or set(item) - {'folder', 'files'}:
            return None
        folder, files = item.get('folder'), item.get('files', [])
        if not bounded(folder) or not folder or not isinstance(files, list):
            return None
        total_files += len(files)
        if total_files > MAX_FILES or not all(bounded(f) and f for f in files):
            return None
        try:
            if not is_browsable_location(folder):
                return None
        except (ValueError, TypeError, OSError, RecursionError):
            return None
        result['locations'].append({'folder': folder, 'files': list(files)})
    for key, default in (('split', False), ('force_tabs', False), ('properties', False), ('activate_first', True)):
        value = payload.get(key, default)
        if type(value) is not bool:
            return None
        result[key] = value
    token = payload.get('activation_token', '')
    if not bounded(token):
        return None
    result['activation_token'] = token
    try:
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > MAX_MESSAGE_BYTES:
            return None
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return None
    return result


def decode_payload(raw):
    if not isinstance(raw, str) or len(raw) > MAX_MESSAGE_BYTES:
        return None
    try:
        if len(raw.encode('utf-8')) > MAX_MESSAGE_BYTES:
            return None
        return normalize_payload(json.loads(raw))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        return None


def validated_requests(payload):
    normalized = normalize_payload(payload)
    if normalized is None:
        return []
    return [LaunchRequest(item['folder'], tuple(item['files'])) for item in normalized['locations']]


def route_plan(requests, locations):
    """Find each URL across all windows before grouping unclaimed locations."""
    from .external_locations import location_key
    known = [(peer, {location_key(path) for path in paths}) for peer, paths in locations]
    routed = {}
    missing = []
    for request in requests:
        key = location_key(request.folder)
        peer = next((peer for peer, paths in known if key in paths), None)
        if peer is None:
            missing.append(request)
        else:
            routed.setdefault(peer, []).append(request)
    return routed, missing


class WindowEndpoint(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @Slot(result=bool)
    def Active(self):
        return self.window.isActiveWindow()

    @Slot(result=str)
    def Locations(self):
        window = self.window
        locations = []
        for index, tab in enumerate(window._tabs):
            panes = window.panes if index == window._active_tab else tab.panes
            split = window.split_enabled if index == window._active_tab else tab.split
            bound = window.bound_pane if index == window._active_tab else tab.bound
            for pane in panes if split else [bound]:
                if not pane.search_active:
                    folder = window.folder if pane is window.bound_pane else pane.folder or tab.location
                    if folder:
                        locations.append(str(folder))
        return json.dumps(locations)

    @Slot(str, result=bool)
    def Dispatch(self, raw):
        payload = decode_payload(raw)
        if payload is None:
            return False
        QTimer.singleShot(0, self, lambda: self.window.receive_launch_payload(payload))
        return True


def register_window(application, window):
    from PySide6.QtDBus import QDBusConnection
    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    endpoint = WindowEndpoint(window)
    if not bus.registerObject(OBJECT, INTERFACE, endpoint, QDBusConnection.RegisterOption.ExportAllSlots):
        return False
    name = PREFIX + str(os.getpid())
    if not bus.registerService(name):
        bus.unregisterObject(OBJECT)
        return False
    application._mirivue_window_endpoint = endpoint
    application._mirivue_window_service = name
    application._mirivue_window_bus = bus
    return True


# A single deadline covers discovery, queries and dispatch, not one per window.
ROUTE_BUDGET_MS = 1500


class RouteResult:
    def __init__(self, remaining, delivered=(), uncertain=()):
        self.remaining = list(remaining)
        self.delivered = list(delivered)
        self.uncertain = list(uncertain)

    def __bool__(self):
        # Uncertain dispatches must never be repeated automatically.
        return bool(self.delivered or self.uncertain) and not self.remaining


class WindowRoute(QObject):
    """Finite asynchronous exchange; never run a blocking bus.call in a window."""
    finished = Signal(object)

    def __init__(self, requests, window=None, options=None, bus=None, budget_ms=ROUTE_BUDGET_MS):
        from PySide6.QtDBus import QDBusConnection
        from PySide6.QtWidgets import QApplication
        super().__init__(window or QApplication.instance())
        self.requests = list(requests)
        self.remaining = list(requests)
        self.delivered = []
        self.uncertain = []
        self.window = window
        self.options = options or {}
        self.bus = bus or QDBusConnection.sessionBus()
        self.application = QApplication.instance()
        self.own_name = getattr(self.application, '_mirivue_window_service', None)
        self.budget_ms = budget_ms
        self.done = False
        self.pending = 0
        self.peers = {}
        self.dispatching = None
        self.queue = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.expire)

    def start(self):
        self.deadline = time.monotonic() + self.budget_ms / 1000
        self.timer.start(self.budget_ms)
        if not self.requests or not self.bus.isConnected():
            self.finish()
            return
        self.call('org.freedesktop.DBus', 'ListNames', [], self.discovered,
                  path='/org/freedesktop/DBus', interface='org.freedesktop.DBus')

    def call(self, name, method, arguments, callback, path=OBJECT, interface=INTERFACE):
        from PySide6.QtDBus import QDBusMessage, QDBusPendingCallWatcher
        if self.done:
            return
        remaining_ms = int((self.deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            if method == 'Dispatch':
                self.dispatching = None  # nothing has been sent yet
            self.expire()
            return
        if name == self.own_name and self.window is not None:
            def local():
                if self.done:
                    return
                try:
                    value = getattr(self.application._mirivue_window_endpoint, method)(*arguments)
                    callback(value, '')
                except (ValueError, TypeError, RuntimeError):
                    callback(None, 'local-error')
            QTimer.singleShot(0, self, local)
            return
        message = QDBusMessage.createMethodCall(name, path, interface, method)
        message.setArguments(arguments)
        watcher = QDBusPendingCallWatcher(self.bus.asyncCall(message, min(1000, remaining_ms)), self)
        def complete():
            if self.done:
                watcher.deleteLater()
                return
            reply = watcher.reply()
            values = reply.arguments()
            error = reply.errorName() if reply.type() == QDBusMessage.MessageType.ErrorMessage else ''
            callback(values[0] if values and not error else None, error)
            watcher.deleteLater()
        watcher.finished.connect(complete)

    def discovered(self, names, error):
        if error or not isinstance(names, list):
            self.finish()
            return
        names = [name for name in names if isinstance(name, str) and name.startswith(PREFIX)]
        if self.own_name in names:
            names.remove(self.own_name)
            names.insert(0, self.own_name)
        self.pending = len(names) * 2
        if not self.pending:
            self.finish()
            return
        for name in names:
            self.peers[name] = {'paths': None, 'active': False}
        for name in names:
            self.call(name, 'Locations', [], lambda value, error, n=name: self.peer_reply(n, 'paths', value, error))
            self.call(name, 'Active', [], lambda value, error, n=name: self.peer_reply(n, 'active', value, error))

    def peer_reply(self, name, key, value, error):
        if self.done:
            return
        if not error:
            if key == 'paths':
                try:
                    paths = json.loads(value)
                    if isinstance(paths, list) and len(paths) <= 10000 and all(isinstance(p, str) and len(p) <= MAX_STRING_LENGTH for p in paths):
                        self.peers[name][key] = paths
                except (ValueError, TypeError, RecursionError):
                    pass
            else:
                self.peers[name][key] = value is True
        self.pending -= 1
        if self.pending == 0:
            self.plan()

    def plan(self):
        peers = [(n, p) for n, p in self.peers.items() if p['paths'] is not None]
        peers.sort(key=lambda pair: not pair[1]['active'])
        if not peers:
            self.finish()
            return
        try:
            routed, missing = route_plan(self.requests, [(n, p['paths']) for n, p in peers])
        except (ValueError, TypeError):
            self.finish()
            return
        self.queue = [(n, batch, True) for n, batch in routed.items()]
        if missing:
            self.queue.append((peers[0][0], missing, False))
        self.dispatch_next()

    def dispatch_next(self):
        if self.done:
            return
        if not self.queue:
            self.finish()
            return
        # Do not mark a dispatch in flight before the budget permits sending it.
        if time.monotonic() >= self.deadline:
            self.finish()
            return
        name, batch, force = self.queue.pop(0)
        options = dict(self.options, activate_first=not bool(self.delivered or self.uncertain))
        if force:
            options['force_tabs'] = True
        payload = normalize_payload(request_payload(batch, **options))
        if payload is None:
            self.dispatch_next()
            return
        self.dispatching = list(batch)
        self.call(name, 'Dispatch', [json.dumps(payload, ensure_ascii=False)], self.dispatched)

    def consume(self, batch, uncertain=False):
        target = self.uncertain if uncertain else self.delivered
        for request in batch:
            if request in self.remaining:
                self.remaining.remove(request)
                target.append(request)

    def dispatched(self, accepted, error):
        batch, self.dispatching = self.dispatching or [], None
        if accepted is True and not error:
            self.consume(batch)
        elif error and error not in ('org.freedesktop.DBus.Error.ServiceUnknown',
                                    'org.freedesktop.DBus.Error.NameHasNoOwner',
                                    'org.freedesktop.DBus.Error.UnknownObject',
                                    'org.freedesktop.DBus.Error.UnknownMethod'):
            # The recipient may have accepted it before its reply was lost.
            self.consume(batch, uncertain=True)
        self.dispatch_next()

    def expire(self):
        if self.dispatching:
            self.consume(self.dispatching, uncertain=True)
            self.dispatching = None
        self.finish()

    def finish(self):
        if self.done:
            return
        self.done = True
        self.timer.stop()
        self.finished.emit(RouteResult(self.remaining, self.delivered, self.uncertain))


def route_to_windows(requests, *, window=None, completion=None, **options):
    """Async for live windows; startup-only wait pumps Qt before any UI exists."""
    from PySide6.QtCore import QEventLoop, QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    job = WindowRoute(requests, window, options)
    application = QApplication.instance()
    jobs = getattr(application, '_mirivue_routes', None)
    if jobs is None:
        application._mirivue_routes = jobs = []
    jobs.append(job)
    def cleanup(result):
        if job in jobs:
            jobs.remove(job)
        job.deleteLater()
    if completion is not None:
        job.finished.connect(completion)
        job.finished.connect(cleanup)
        QTimer.singleShot(0, job, job.start)
        return job
    # Only the pre-window launcher uses this compatibility path. Network calls
    # remain asynchronous and timers continue to run while awaiting its result.
    loop = QEventLoop()
    results = []
    job.finished.connect(lambda result: (results.append(result), loop.quit()))
    job.finished.connect(cleanup)
    QTimer.singleShot(0, job, job.start)
    loop.exec(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
    # The launcher may exit without ever entering QApplication.exec(). Flush
    # this completed job, including its watchers, before tearing Qt down.
    QCoreApplication.sendPostedEvents(job, QEvent.Type.DeferredDelete)
    return results[0]
