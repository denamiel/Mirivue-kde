"""Thread-safe, bounded-concurrency scheduling for quick media properties."""

from collections import deque
from threading import Lock


class DurationQueue:
    def __init__(self):
        self._lock = Lock()
        self._visible = deque()
        self._remaining = deque()
        self._seen = set()

    def add(self, paths, visible=()):
        visible = set(visible)
        with self._lock:
            for path in paths:
                if path in self._seen:
                    continue
                self._seen.add(path)
                (self._visible if path in visible else self._remaining).append(path)

    def take(self):
        with self._lock:
            pending = self._visible or self._remaining
            if not pending:
                return None
            return pending.popleft()

    def drain(self):
        with self._lock:
            paths = list(self._visible) + list(self._remaining)
            self._visible.clear()
            self._remaining.clear()
            return paths
