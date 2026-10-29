# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Native QAction descriptions for commands that cannot currently run."""

def set_action_enabled(action, enabled, reason=''):
    saved = action.property('_mirivue_action_help')
    if not isinstance(saved, (list, tuple)) or len(saved) != 3:
        saved = [action.toolTip() if action.toolTip() != action.text() else '',
                 action.statusTip(), action.whatsThis()]
        action.setProperty('_mirivue_action_help', saved)
    action.setEnabled(bool(enabled))
    if enabled or not reason:
        tooltip, status, whats_this = saved
    else:
        tooltip = status = whats_this = reason
    action.setToolTip(tooltip)
    action.setStatusTip(status)
    action.setWhatsThis(whats_this)
