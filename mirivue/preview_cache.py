"""Bounded, least-recently-used cache for decoded preview images."""

from collections import OrderedDict


class PreviewCache:
    def __init__(self, max_bytes=256 * 1024 * 1024):
        self.max_bytes = max_bytes
        self._items = OrderedDict()
        self._used = 0

    @staticmethod
    def _cost(value):
        image = value[0] if isinstance(value, tuple) else value
        return max(0, int(image.sizeInBytes()))

    def get(self, key, default=None):
        if key not in self._items:
            return default
        self._items.move_to_end(key)
        return self._items[key][0]

    def __setitem__(self, key, value):
        old = self._items.pop(key, None)
        if old is not None:
            self._used -= old[1]
        cost = self._cost(value)
        if cost > self.max_bytes:
            return
        self._items[key] = (value, cost)
        self._used += cost
        while self._used > self.max_bytes:
            _, (_, removed) = self._items.popitem(last=False)
            self._used -= removed

    def clear(self):
        self._items.clear()
        self._used = 0
