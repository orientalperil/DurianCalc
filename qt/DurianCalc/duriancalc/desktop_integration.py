"""Registers the running AppImage with the desktop's application menu.

An AppImage is just a file: nothing about running one tells the desktop
environment that an app named "DurianCalc" exists, so it never appears in
the KDE/GNOME launcher or in search. The XDG convention is that an app
becomes visible by dropping a .desktop entry into
$XDG_DATA_HOME/applications and an icon into the hicolor theme -- which,
for a single-file distribution, means the app has to install those for
itself on first launch. That is what this module does.

Two properties matter more than they look:

1. Self-healing. The generated Exec line has to be an absolute path to the
   .AppImage, and an AppImage is a file users move around (Downloads ->
   ~/Apps) or replace with a newer version under a different name. A
   write-once-on-first-run install would leave a menu entry pointing at a
   path that no longer exists -- a dead launcher, which is worse than no
   launcher at all. So install() re-checks the file on EVERY launch and
   rewrites it whenever the desired content differs from what is on disk.
   Moving the AppImage and starting it once is all it takes to repair the
   entry.

2. Not clobbering hand-written entries. Every file we generate carries an
   X-DurianCalc-Generated key. If an entry exists WITHOUT that marker, a
   human (or a distro package) put it there deliberately and we leave it
   strictly alone -- an app that silently overwrites the user's own
   customization is a worse citizen than one that skips an update.

The whole thing is best-effort: install() is called for its side effect
during startup and must never prevent the app from running (see app.py).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Must stay in sync with QApplication.setDesktopFileName() in app.py: the
# desktop file's BASENAME is what Wayland matches a window's app_id
# against to find its icon and menu entry. duriancalc.desktop <-> app_id
# "duriancalc". Renaming one without the other silently degrades the
# taskbar to a generic placeholder icon.
APP_ID = "duriancalc"

# Presence of this key is how a later run recognizes a file as ours and
# therefore safe to overwrite. Custom X- keys are explicitly permitted by
# the Desktop Entry spec and ignored by every implementation, so this is
# invisible to the desktop environment.
MARKER_KEY = "X-DurianCalc-Generated"

# The bundled icon is a 256x256 PNG, so it installs into that fixed-size
# hicolor directory. A "scalable" install would be a lie for a raster
# image and makes desktops upscale it badly.
ICON_SIZE = "256x256"


def _data_home() -> Path:
    """$XDG_DATA_HOME, honoring the spec's ~/.local/share fallback."""
    xdg = os.environ.get("XDG_DATA_HOME")
    # An empty or relative XDG_DATA_HOME is invalid per the base-directory
    # spec and must be treated as unset, not joined onto blindly.
    if xdg and os.path.isabs(xdg):
        return Path(xdg)
    return Path.home() / ".local" / "share"


def _quote_exec(path: Path) -> str:
    """Render `path` for a desktop entry's Exec key.

    Exec is not a shell command but it does have its own quoting rules,
    and a path containing a space (~/My Apps/DurianCalc.AppImage) would
    otherwise be parsed as a program plus an argument. The spec calls for
    double quotes around such a value, with backslash, double quote,
    backtick and dollar escaped inside them. Values are additionally
    subject to the desktop-entry string escape, where a literal backslash
    is written as two -- hence the doubling before the quote-escaping.
    """
    text = str(path)
    escaped = text.replace("\\", "\\\\")
    if not any(ch in escaped for ch in ' \t"\'\\><~|&;$*?#()`'):
        return escaped
    for ch in ('"', "`", "$"):
        escaped = escaped.replace(ch, "\\" + ch)
    return f'"{escaped}"'


def desktop_entry(appimage: Path) -> str:
    """The full .desktop file text pointing at `appimage`."""
    # Keywords is what makes the app findable by what it DOES rather than
    # only by its name -- typing "calculator" into KRunner or GNOME
    # search finds nothing for an app called "DurianCalc" without it.
    #
    # StartupWMClass must be the lowercase app_id set by
    # setDesktopFileName(), NOT the mixed-case applicationName: it is
    # matched against the window's actual class, and a case mismatch
    # leaves the running window unassociated with this entry (generic
    # icon in the taskbar, no "pin to taskbar" that works).
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=DurianCalc\n"
        "Comment=A minimal, expression-based calculator\n"
        f"Exec={_quote_exec(appimage)}\n"
        f"Icon={APP_ID}\n"
        "Categories=Utility;Calculator;Qt;\n"
        "Keywords=calculator;calc;math;expression;arithmetic;durian;\n"
        "Terminal=false\n"
        "StartupNotify=true\n"
        f"StartupWMClass={APP_ID}\n"
        f"{MARKER_KEY}=true\n"
    )


def bundled_icon() -> Path | None:
    """Locate the app's own PNG icon, whatever form the app is running in.

    This is what lets the app hand its icon straight to the compositor via
    QApplication.setWindowIcon() instead of relying on the icon theme.
    That distinction matters more than it sounds: a desktop environment
    caches the contents of the icon theme at session start, so an icon
    this app installs into hicolor is invisible to the already-running
    panel until the user logs out and back in -- the first launch of a
    freshly downloaded AppImage would otherwise show a blank square in
    the task bar, which is exactly the symptom the theme install is
    meant to prevent. An icon carried on the window itself (Wayland's
    xdg-toplevel-icon, or the X11 _NET_WM_ICON property) is drawn from
    the app's own pixels and owes nothing to any cache.

    Returns None rather than raising when the icon is missing: a
    stripped-down build without it should still launch.
    """
    candidates: list[Path] = []

    # Frozen by PyInstaller: --add-data puts the PNG in the unpacked
    # bundle directory that _MEIPASS points at.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / f"{APP_ID}.png")

    # Running from an AppImage: the icon sits at the AppDir root, where
    # build-appimage.sh puts it for appimagetool's benefit.
    appdir = os.environ.get("APPDIR")
    if appdir:
        candidates.append(Path(appdir) / f"{APP_ID}.png")

    # A plain dev checkout: duriancalc/ and packaging/ are siblings.
    candidates.append(Path(__file__).resolve().parent.parent / "packaging" / f"{APP_ID}.png")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _is_ours(path: Path) -> bool:
    """True if `path` is absent, or present and generated by us."""
    try:
        return MARKER_KEY in path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    except OSError:
        # Unreadable means we cannot prove it is ours, so treat it as
        # someone else's and keep our hands off it.
        return False


def _system_entry_exists() -> bool:
    """True if a system-wide entry already advertises this app.

    When DurianCalc has been installed properly (a distro package, or a
    manual copy into /usr/share/applications), adding a per-user entry on
    top of it would show the user two identical menu items that launch
    different builds. The packaged install wins.
    """
    dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return any(
        (Path(d) / "applications" / f"{APP_ID}.desktop").exists()
        for d in dirs.split(":")
        if d and os.path.isabs(d)
    )


def _refresh_caches(applications_dir: Path, icons_root: Path) -> None:
    """Nudge the desktop's caches after a change.

    Only called when something actually changed, because these processes
    cost real time (order of 100ms each) and would otherwise be paid on
    every single launch for nothing. Both are optional helpers that many
    systems do not ship, and modern KDE/GNOME shells also watch these
    directories directly, so failure here is not an error -- at worst the
    new entry shows up a beat later.
    """
    for tool, args in (
        ("update-desktop-database", [str(applications_dir)]),
        ("gtk-update-icon-cache", ["-f", "-t", str(icons_root)]),
    ):
        exe = shutil.which(tool)
        if not exe:
            continue
        try:
            subprocess.run(
                [exe, *args],
                check=False,
                timeout=20,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            pass


def install(appimage: Path, appdir: Path, data_home: Path | None = None) -> bool:
    """Install/refresh the menu entry and icon. True if anything changed.

    `appimage` is the .AppImage the Exec line should point at and
    `appdir` is the mounted bundle the icon is copied out of.
    """
    if _system_entry_exists():
        return False

    home = data_home if data_home is not None else _data_home()
    applications_dir = home / "applications"
    icons_root = home / "icons" / "hicolor"
    icon_dir = icons_root / ICON_SIZE / "apps"
    entry_path = applications_dir / f"{APP_ID}.desktop"
    icon_path = icon_dir / f"{APP_ID}.png"
    icon_source = appdir / f"{APP_ID}.png"
    if not icon_source.is_file():
        fallback = bundled_icon()
        if fallback is not None:
            icon_source = fallback

    changed = False

    if _is_ours(entry_path):
        wanted = desktop_entry(appimage)
        # Compare before writing so the overwhelmingly common case -- an
        # unmoved AppImage on its hundredth launch -- touches nothing and
        # skips the cache refresh below.
        try:
            current = entry_path.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != wanted:
            applications_dir.mkdir(parents=True, exist_ok=True)
            _write_atomic(entry_path, wanted.encode("utf-8"))
            changed = True
    else:
        print(
            f"duriancalc: leaving hand-written {entry_path} untouched "
            f"(delete it to let the app manage its own menu entry)",
            file=sys.stderr,
        )

    if icon_source.is_file():
        source_bytes = icon_source.read_bytes()
        try:
            current_icon = icon_path.read_bytes()
        except OSError:
            current_icon = None
        if current_icon != source_bytes:
            icon_dir.mkdir(parents=True, exist_ok=True)
            _write_atomic(icon_path, source_bytes)
            changed = True

    if changed:
        _refresh_caches(applications_dir, icons_root)
    return changed


def _write_atomic(path: Path, payload: bytes) -> None:
    """Write via a temp file + rename so a crash cannot leave a partial
    entry behind -- a truncated .desktop file is a broken menu item that
    the user then has to find and delete by hand."""
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_bytes(payload)
        tmp.replace(path)
    finally:
        # replace() consumed tmp on success; this only fires on failure.
        tmp.unlink(missing_ok=True)


def install_if_appimage() -> bool:
    """Entry point for startup: register, but only when run as an AppImage.

    Outside an AppImage -- a dev checkout, a pip install, a distro
    package -- writing into the user's applications directory would be
    both wrong (there is no stable single file to point Exec at) and
    presumptuous, so the whole thing is a no-op.

    Setting DURIANCALC_NO_DESKTOP_INTEGRATION opts out entirely, for
    users who keep a deliberately unregistered portable copy.
    """
    if os.environ.get("DURIANCALC_NO_DESKTOP_INTEGRATION"):
        return False

    # Both variables are set by the AppImage runtime (APPDIR is also set
    # defensively by our own AppRun); their presence together is the
    # signal that we are running from a bundle.
    appimage = os.environ.get("APPIMAGE")
    appdir = os.environ.get("APPDIR")
    if not appimage or not appdir:
        return False

    appimage_path = Path(appimage)
    if not appimage_path.is_file():
        return False

    return install(appimage_path, Path(appdir))
