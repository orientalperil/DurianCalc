"""Live light/dark color resolution.

Queries QStyleHints.colorScheme() directly and returns explicit hex colors,
rather than going through QApplication.palette() / QSS `palette(...)`
references. In testing, the latter proved unreliable at staying in sync on
a live system theme switch (KWin Wayland + a PyPI-bundled, not
system-integrated, Qt): QStyleHints.colorSchemeChanged fires correctly, but
QApplication's actual palette wasn't reliably updated by the time it did,
so QSS `palette(...)` re-resolved against a stale or mismatched value --
symptomatically, the field's background would invert (show the *previous*
scheme's color) on every switch rather than tracking the current one.
Reading colorScheme() and picking colors ourselves sidesteps that
indirection entirely.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

_LIGHT = {"base": "#FFFFFF", "text": "#1A1A1A", "mid": "#C7C7C7"}
_DARK = {"base": "#232323", "text": "#E0E0E0", "mid": "#555555"}


def colors() -> dict[str, str]:
    """{"base": ..., "text": ..., "mid": ...} for the current system scheme.

    Falls back to light for Qt.ColorScheme.Unknown (no platform signal
    available), matching this app's original default before it respected
    the system setting at all.
    """
    scheme = QGuiApplication.styleHints().colorScheme()
    return _DARK if scheme == Qt.ColorScheme.Dark else _LIGHT
