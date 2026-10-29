# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
"""Load the public-API KDE desktop adapters in the existing native bridge."""
import ctypes
import os
from .platform_services import services


def load():
    path = os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY') or services.tool_path('libmirivue-kio-places-widget.so')
    if not path: raise OSError('Composants natifs KDE indisponibles.')
    return ctypes.CDLL(path)
