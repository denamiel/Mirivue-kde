"""Resolve command icons from the active desktop theme, with native Qt fallbacks."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMessageBox, QStyle, QToolButton


def themed_icon(name, widget=None, fallback=None):
    icon = QIcon.fromTheme(name)
    if not icon.isNull():
        return icon
    if widget is not None and fallback is not None:
        return widget.style().standardIcon(fallback)
    return QIcon()


def set_themed_action_icon(action, name):
    icon = QIcon.fromTheme(name)
    if not icon.isNull():
        action.setIcon(icon)
    return action


def context_help_button(parent, text, title="Informations"):
    """Return a compact, native contextual-help button.

    The same explanation is available by hover, keyboard focus and click, so
    simplifying a dialog never makes its help mouse-only.
    """
    button = QToolButton(parent)
    button.setAutoRaise(True)
    button.setIcon(themed_icon("help-contextual", parent, QStyle.StandardPixmap.SP_MessageBoxInformation))
    button.setToolTip(text)
    button.setAccessibleName(title)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.clicked.connect(lambda checked=False: QMessageBox.information(parent, title, text))
    return button


def set_destructive_action_icon(action, name="edit-delete"):
    """Set a theme glyph with Plasma's destructive foreground colour.

    Breeze's trash glyphs are intentionally theme-driven.  Tinting the
    alpha mask lets the permanent-delete action match Dolphin's red semantic
    emphasis without replacing or hard-coding the icon artwork.
    """
    source_icon = QIcon.fromTheme(name)
    if source_icon.isNull():
        return set_themed_action_icon(action, name)
    # Breeze's edit-delete SVG already carries ColorScheme-NegativeText.  Keep
    # that native themed icon intact; raster tinting can lose its semantic
    # glyph appearance and produces a misaligned-looking menu item.
    action.setIcon(source_icon)
    return action


def add_destructive_action(menu, text, callback, name="edit-delete"):
    """Add a native menu row with only its theme-provided icon in red.

    A QWidgetAction bypasses QMenu's selected-row painting.  Keeping this as
    a plain QAction lets Plasma draw the normal hover highlight, just as
    Dolphin does, while Breeze supplies the destructive icon colour.
    """
    action = QAction(menu)
    action.setText(text)
    set_destructive_action_icon(action, name)
    action.triggered.connect(lambda checked=False: callback())
    menu.addAction(action)
    return action


def add_dynamic_trash_action(menu, trash_callback, permanent_callback, trash_text, permanent_text, permanent=False):
    """Add a native menu item that changes while Shift is held.

    A QWidgetAction embeds a button that bypasses QMenu's highlighted-row
    painting, making an enabled trash command look disabled on Breeze.
    """
    action = QAction(menu)

    def set_mode(is_permanent):
        is_permanent = bool(is_permanent)
        text = permanent_text if is_permanent else trash_text
        icon_name = "edit-delete" if is_permanent else "trash-empty"
        action.setText(text)
        if is_permanent:
            set_destructive_action_icon(action, icon_name)
        else:
            set_themed_action_icon(action, icon_name)
        action._mirivue_permanent = is_permanent

    set_mode(permanent)
    action._mirivue_set_mode = set_mode
    action.triggered.connect(lambda checked=False: (permanent_callback() if action._mirivue_permanent else trash_callback()))
    menu.addAction(action)
    return action
