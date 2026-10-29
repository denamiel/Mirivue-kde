# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Indices and aggregate facts following the file model's Qt notifications."""
from PySide6.QtCore import Qt


class ModelInventory:
    def init_inventory(self):
        self._path_positions = {}
        self._indexed_paths = []
        self._incomplete_flags = []
        self._incomplete_count = 0
        self._inventory_dirty = False
        self.modelReset.connect(self.invalidate_inventory)
        self.rowsRemoved.connect(self.invalidate_inventory)
        self.rowsInserted.connect(self.inventory_inserted)
        self.dataChanged.connect(self.inventory_changed)

    def invalidate_inventory(self, *_args):
        # A batch of removals can shift every remaining index. Rebuild once
        # when next requested, rather than after every individual removal.
        self._inventory_dirty = True
        self._path_positions.clear()
        self._indexed_paths.clear()
        self._incomplete_flags.clear()
        self._incomplete_count = 0

    def _ensure_inventory(self):
        if not self._inventory_dirty and len(self._indexed_paths) == len(self.rows):
            return
        self._path_positions = {}
        self._indexed_paths = []
        self._incomplete_flags = []
        self._incomplete_count = 0
        for index, row in enumerate(self.rows):
            self._append_inventory(index, row)
        self._inventory_dirty = False

    def _append_inventory(self, index, row):
        path = getattr(row, 'path', None)
        self._indexed_paths.append(path)
        if path is not None:
            self._path_positions.setdefault(path, set()).add(index)
        incomplete = self.inventory_is_incomplete(row)
        self._incomplete_flags.append(incomplete)
        self._incomplete_count += incomplete

    def inventory_inserted(self, parent, first, last):
        if self._inventory_dirty or first != len(self._indexed_paths):
            self.invalidate_inventory()
            return
        for index in range(first, last + 1):
            self._append_inventory(index, self.rows[index])

    def reindex_row(self, index):
        self._ensure_inventory()
        old = self._indexed_paths[index]
        row = self.rows[index]
        path = getattr(row, 'path', None)
        if old != path:
            positions = self._path_positions.get(old)
            if positions is not None:
                positions.discard(index)
                if not positions:
                    self._path_positions.pop(old)
            if path is not None:
                self._path_positions.setdefault(path, set()).add(index)
            self._indexed_paths[index] = path
        incomplete = self.inventory_is_incomplete(row)
        self._incomplete_count += incomplete - self._incomplete_flags[index]
        self._incomplete_flags[index] = incomplete

    def inventory_changed(self, first, last, roles=()):
        if not first.isValid() or not last.isValid():
            return
        # Preview/theme changes do not change media completeness or identity.
        if roles and all(role in (Qt.ItemDataRole.DecorationRole,
                                  Qt.ItemDataRole.ForegroundRole,
                                  Qt.ItemDataRole.BackgroundRole,
                                  Qt.ItemDataRole.FontRole) for role in roles):
            return
        self._ensure_inventory()
        for index in range(first.row(), last.row() + 1):
            self.reindex_row(index)

    def positions_for_path(self, path):
        self._ensure_inventory()
        return tuple(sorted(self._path_positions.get(path, ())))

    @property
    def incomplete_count(self):
        self._ensure_inventory()
        return self._incomplete_count
