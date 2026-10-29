"""Native Dolphin file views; file facts remain in Mirivue's domain model."""
from PySide6.QtCore import Qt
from .dolphin_view import DetailsView, IconView

IS_DIRECTORY_ROLE = Qt.ItemDataRole.UserRole + 42
