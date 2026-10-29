"""Central ownership and shutdown rules for background Qt threads."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal
from shiboken6 import isValid


@dataclass(frozen=True)
class RuntimeTask:
    name: str
    cancellable: bool = True


class RuntimeTaskRegistry(QObject):
    """Own every application thread and provide one cancellation boundary."""

    changed = Signal(int)

    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner
        # Keep an integer identity so a queued finished/destroyed callback
        # never needs to inspect a C++ QObject whose wrapper is already dead.
        self._threads: dict[int, tuple[QThread, RuntimeTask]] = {}

    def track(self, thread: QThread, name: str, cancellable: bool = True) -> QThread:
        key = id(thread)
        if key in self._threads:
            return thread
        if thread.parent() is None:
            thread.setParent(self._owner)
        self._threads[key] = (thread, RuntimeTask(str(name), bool(cancellable)))
        thread.finished.connect(lambda key=key: self._forget(key))
        thread.destroyed.connect(lambda _object=None, key=key: self._forget(key))
        return thread

    def start(self, thread: QThread, name: str, cancellable: bool = True) -> QThread:
        self.track(thread, name, cancellable)
        thread.start()
        self.changed.emit(len(self.running()))
        return thread

    def _forget(self, key: int) -> None:
        if self._threads.pop(key, None) is not None:
            self.changed.emit(len(self.running()))

    def running(self) -> list[QThread]:
        active = []
        for key, (thread, _task) in tuple(self._threads.items()):
            if not isValid(thread):
                self._threads.pop(key, None)
                continue
            try:
                if thread.isRunning():
                    active.append(thread)
            except RuntimeError:
                self._threads.pop(key, None)
        return active

    def request_stop_all(self, exclude=()) -> list[QThread]:
        protected = {id(thread) for thread in exclude}
        running = [thread for thread in self.running() if id(thread) not in protected]
        for thread in running:
            tracked = self._threads.get(id(thread))
            if tracked is not None and tracked[1].cancellable:
                cancel = getattr(thread, 'cancel', None)
                if callable(cancel):
                    cancel()
                thread.requestInterruption()
        return running

    def descriptions(self) -> list[str]:
        return [self._threads[id(thread)][1].name for thread in self.running()]
