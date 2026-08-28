"""App entry point: creates the QApplication and the utility window, and
connects the window's File > Settings action to the Preferences dialog.

Port of ../../mac/DurianCalc/DurianCalc/DurianCalcApp.swift. There the
AppDelegate builds an NSPanel and owns the ShortcutStore; here QApplication
plays that role, with the equivalent lifecycle decision (quit only when the
main panel closes -- see MainWindow.closeEvent) made explicit by disabling
quitOnLastWindowClosed.

Deliberately does NOT force a light palette (the mac version no longer
forces .preferredColorScheme(.light) either): both apps inherit whatever
light/dark mode the desktop is set to. The widget code accordingly sticks
to palette-relative colors (`palette(base)`, `palette(text)`, ...) instead
of hardcoded hex values -- see main_window.py.

Known gap: main_window.py's QSS `palette(...)` references are resolved once,
when the stylesheet is applied, not kept live-bound -- switching the
system theme while the app is already running leaves those colors stale
until something explicitly reapplies the stylesheet (a relaunch does this
for free, since it resolves fresh at construction). Unlike the mac version,
whose SwiftUI dynamic colors do update live on an appearance change, this
is an actual behavioral gap between the two ports, not yet fixed here.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from duriancalc.desktop_integration import bundled_icon, install_if_appimage
from duriancalc.main_window import MainWindow
from duriancalc.shortcuts import ShortcutStore
from duriancalc.shortcuts_dialog import ShortcutsDialog


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

    # Register this AppImage in the application menu (no-op for a dev
    # checkout or any non-AppImage run -- see desktop_integration). Done
    # BEFORE constructing QApplication so that a first launch installs
    # the entry in time for Qt's own xdg-desktop-portal registration to
    # find it, which is what silences the "App info not found for
    # 'duriancalc'" warning described above from the second run onward.
    #
    # Deliberately swallows everything: a read-only home, an exotic
    # XDG_DATA_HOME or a sandbox that blocks subprocesses are all
    # reasons the menu entry cannot be written, and none of them are a
    # reason to stop the user from doing arithmetic.
    try:
        install_if_appimage()
    except Exception as exc:  # noqa: BLE001 - best-effort side effect
        print(f"duriancalc: skipping desktop integration ({exc})", file=sys.stderr)

    app = QApplication(sys.argv)

    # Carry the icon on the window itself rather than leaving the task
    # bar to look it up by app_id. The desktop entry installed above is
    # what puts DurianCalc in the application menu, but a panel that has
    # been running since before that entry existed has already cached the
    # icon theme and will draw a blank square for this window until the
    # next login -- setting it here fills that gap on the very first
    # launch, and covers X11 and bare-WM sessions that never consult a
    # desktop entry at all. Must follow QApplication construction so the
    # platform plugin is live to forward it (Wayland's
    # xdg-toplevel-icon; _NET_WM_ICON under X11).
    icon_path = bundled_icon()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))

    # We decide when to quit ourselves (see MainWindow.closeEvent), the same
    # deliberate choice DurianCalcApp.swift documents for the same reason:
    # a transient window (there, SwiftUI's hidden Settings backing window;
    # here, the Preferences dialog) closing first must not end the app.
    app.setQuitOnLastWindowClosed(False)

    shortcuts = ShortcutStore()
    window = MainWindow(shortcuts)

    preferences = ShortcutsDialog(shortcuts, window)

    def open_preferences() -> None:
        preferences.show()
        preferences.raise_()
        preferences.activateWindow()

    window.settings_requested.connect(open_preferences)

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
