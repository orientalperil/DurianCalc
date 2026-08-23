"""App entry point: creates the QApplication and the utility window, forces
light mode, and wires up Ctrl+, for Preferences.

Port of ../../mac/DurianCalc/DurianCalc/DurianCalcApp.swift. There the
AppDelegate builds an NSPanel and owns the ShortcutStore; here QApplication
plays that role, with the equivalent lifecycle decision (quit only when the
main panel closes -- see MainWindow.closeEvent) made explicit by disabling
quitOnLastWindowClosed.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QShortcut
from PySide6.QtWidgets import QApplication

from duriancalc.main_window import MainWindow
from duriancalc.shortcuts import ShortcutStore
from duriancalc.shortcuts_dialog import ShortcutsDialog


def _force_light_palette(app: QApplication) -> None:
    """The mac version forces .preferredColorScheme(.light) on every scene.
    Qt has no single global light-mode switch, so this pins the palette
    roles a dark desktop theme would otherwise override.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F5F5F5"))
    palette.setColor(QPalette.WindowText, QColor("#1A1A1A"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.Text, QColor("#1A1A1A"))
    palette.setColor(QPalette.Button, QColor("#F0F0F0"))
    palette.setColor(QPalette.ButtonText, QColor("#1A1A1A"))
    palette.setColor(QPalette.Highlight, QColor("#5C9E33"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    app.setStyle("Fusion")


def main() -> int:
    QApplication.setOrganizationName("DurianCalc")
    QApplication.setApplicationName("DurianCalc")
    # Sets the Wayland app_id / X11 WM_CLASS to "duriancalc" -- without
    # this, QtWaylandClient falls back to the interpreter's own binary
    # name ("python3.14"), since a Poetry console-script entry point is
    # just a Python script run BY python3.14, not a distinctly-named
    # executable. A generic interpreter-wide app_id makes window matching
    # (e.g. a KWin Window Rule -- see README's "Always-on-top on Wayland")
    # unusable, since every Python/Qt app sharing that interpreter would
    # match the same rule.
    #
    # Trade-off: this also makes Qt attempt xdg-desktop-portal
    # registration, which logs a harmless "App info not found for
    # 'duriancalc'" warning until packaging/duriancalc.desktop is
    # installed somewhere on $XDG_DATA_DIRS/applications (true for any
    # dev checkout; resolved by the AppImage or a real install). The
    # warning is cosmetic -- the app_id is still set correctly regardless
    # of whether portal registration succeeds.
    QApplication.setDesktopFileName("duriancalc")

    app = QApplication(sys.argv)
    # We decide when to quit ourselves (see MainWindow.closeEvent), the same
    # deliberate choice DurianCalcApp.swift documents for the same reason:
    # a transient window (there, SwiftUI's hidden Settings backing window;
    # here, the Preferences dialog) closing first must not end the app.
    app.setQuitOnLastWindowClosed(False)
    _force_light_palette(app)

    shortcuts = ShortcutStore()
    window = MainWindow(shortcuts)

    preferences = ShortcutsDialog(shortcuts, window)

    def open_preferences() -> None:
        preferences.show()
        preferences.raise_()
        preferences.activateWindow()

    QShortcut(Qt.CTRL | Qt.Key_Comma, window, activated=open_preferences)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
