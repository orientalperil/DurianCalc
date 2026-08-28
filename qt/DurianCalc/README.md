# DurianCalc

A minimal, expression-based calculator for Linux, built with Qt (PySide6) —
inspired by [pearCalc](https://www.pearworks.com/pages/pearcalc.html) by
Walter Ritter.

Instead of a grid of buttons, you get a single compact field: type a whole
mathematical expression and the result appears live as you type. It uses small
utility-window chrome and takes up almost no screen space.

This is a port of the macOS version in [`../../mac/DurianCalc`](../../mac/DurianCalc).
See [PORTING.md](PORTING.md) for how the two relate.

## Run it

1. Install [Poetry](https://python-poetry.org/docs/#installation).
2. Install the dependencies:

   ```bash
   poetry install
   ```

3. Run it:

   ```bash
   poetry run duriancalc
   ```

Requires Python 3.10 or later. On Qt 6.5+ you may also need your distribution's
`libxcb-cursor0` package if the app fails to start with a platform-plugin error.

## How to use

Just type. The result updates as you go. Press **Return** to carry the result
forward into a new calculation, and **Esc** to clear the field. There's a copy
button next to the result.

Examples you can type:

```
2 + 3 * 4
(2 + 3) * 4
sin(pi/2) + sqrt(16)
log(1000)
2 ^ 10
17 mod 5
200 * 15%
100 * usd
```

## Supported syntax

- **Operators:** `+  -  *  /  ^  mod  %` (× and ÷ also accepted)
- **Parentheses:** full nesting, correct precedence
- **`^` is right-associative** (`2^3^2` = 512) and unary minus binds looser
  than `^` (`-2^2` = -4), matching standard math convention
- **Trailing `%`** divides by 100 (`50%` = 0.5, `200 * 10%` = 20)
- **Functions:** `sin cos tan asin acos atan sinh cosh tanh ln log log10 log2
  sqrt cbrt abs exp floor ceil round rad deg`
  (`rad`/`deg` convert between degrees and radians)
- **Constants:** `pi`, `e`, `tau`
- **Scientific notation:** `1e3`, `2.5e-4`

## Shortcuts & constants

Open **Preferences** (Ctrl+,) to define your own named values — handy for
currency conversion (`usd`, `eur`, …) or personal constants. Use them by name in
any expression. They're saved between launches, in
`~/.config/DurianCalc/DurianCalc.conf`.

## Always-on-top on Wayland

The window opens pinned above other windows on X11 — KDE's "Keep Above
Others" toggle. Under Wayland (the default in modern Plasma), this doesn't
work: xdg-shell, the protocol Wayland windows use, deliberately gives clients
no way to request always-on-top for themselves, so only the compositor (or
you, manually) can set it.

To get the same effect automatically on Wayland, add a one-time KWin Window
Rule:

1. **System Settings → Window Management → Window Rules → Add New…**
2. **Window class (application):** `duriancalc` — **Match whole window
   class**
3. Add property **Keep above** → **Force** → **Yes**

The app explicitly sets its Wayland app ID / X11 WM_CLASS to `duriancalc`
(`QApplication.setDesktopFileName`), so this rule matches regardless of how
it's launched. Without that call the app_id falls back to the Python
interpreter's own name (e.g. `python3.14`) — far too general to build a
window rule on, since it'd match every Python/Qt app on the system.

That call also makes Qt attempt to register with `xdg-desktop-portal`, which
logs a harmless warning —
`App info not found for 'duriancalc'` — until `packaging/duriancalc.desktop`
is installed somewhere on `$XDG_DATA_DIRS/applications`. It doesn't affect
the app_id or anything else; to silence it in development, symlink the
desktop file in:

```bash
ln -s "$PWD/packaging/duriancalc.desktop" ~/.local/share/applications/duriancalc.desktop
```

(A real AppImage or system install resolves this on its own.)

## Files

- `duriancalc/app.py` — app entry; creates the QApplication and the utility
  window, and opens the Preferences dialog. Follows the system light/dark
  appearance.
- `duriancalc/main_window.py` — the single expression field, live result,
  Esc-to-clear
- `duriancalc/evaluator.py` — tokenizer + recursive-descent parser/evaluator
- `duriancalc/shortcuts.py` — user-defined shortcuts, persisted to QSettings
- `duriancalc/shortcuts_dialog.py` — the preferences pane for editing shortcuts
- `duriancalc/desktop_integration.py` — registers the running AppImage in the
  application menu (no-op outside an AppImage)

## Building an AppImage

The release artifact for Linux is a single self-contained AppImage.

```bash
./packaging/build-appimage.sh
```

This produces `dist/DurianCalc-x86_64.AppImage`, which needs no Python or Qt
installed on the target machine:

```bash
chmod +x dist/DurianCalc-x86_64.AppImage
./dist/DurianCalc-x86_64.AppImage
```

**Build it on the oldest distribution you intend to support** (an Ubuntu 22.04
container works well). AppImages are forward-compatible but not backward-
compatible — one built on a rolling release will only run on a rolling release.

### Application-menu registration

Running the AppImage is all it takes to make DurianCalc appear in the desktop's
app list and search — on launch it installs its own entry and icon:

- `~/.local/share/applications/duriancalc.desktop`
- `~/.local/share/icons/hicolor/256x256/apps/duriancalc.png`

The entry's `Exec` is an absolute path to the `.AppImage`, so it is rechecked
and rewritten on every launch: move the file (or swap in a new version under a
different name) and starting it once repairs the menu entry, rather than
leaving a launcher pointing at a path that no longer exists. When nothing has
changed the launch touches no files.

The app also sets its own window icon from the copy of the PNG inside the
bundle, which is what the task bar draws. This is deliberately independent of
the icon installed above: a desktop session caches the icon theme at login, so
a panel that was already running when the icon was installed draws a blank
square for the window until the next login. An icon carried on the window
itself (Wayland's `xdg-toplevel-icon`, `_NET_WM_ICON` under X11) sidesteps that
cache, so the task bar is correct on the very first launch.

The *menu* icon has no such escape hatch — it is resolved from the theme by the
desktop shell — so on a brand-new install the application-menu entry may appear
without its icon until the next login, even while the task bar shows it.

Registration is skipped when a system-wide `duriancalc.desktop` already exists
on `$XDG_DATA_DIRS` (a packaged install wins, so the menu never shows two
entries), and when a `duriancalc.desktop` is present that the app did not
generate — hand-edited entries are never overwritten. Files it does generate
are tagged with `X-DurianCalc-Generated=true`; delete yours to hand control
back to the app. To opt out entirely, e.g. for a portable copy:

```bash
DURIANCALC_NO_DESKTOP_INTEGRATION=1 ./DurianCalc-x86_64.AppImage
```

## Development

Run the test suite:

```bash
poetry run pytest
```

The evaluator is pure Python with no Qt dependency, so the tests run headlessly
and fast. Run the app straight from the source tree with `poetry run duriancalc`
— no build step is needed during development.

## Not included (from the original)

The original pearCalc is also an app-launcher, a global-hotkey overlay, and a
text-replacement Service. This clone focuses on the calculator core. On Linux
those features would map to freedesktop `.desktop` lookup, a compositor-level
global shortcut, and a clipboard/portal integration respectively — none of which
have a single portable implementation across X11 and Wayland.

## A note on testing

The parser's precedence and associativity were verified against a set of
tricky cases (right-associative `^`, unary-minus interaction, `mod`, trailing
`%`, nested parentheses, function application), ported case-for-case from the
macOS test suite. If you extend the grammar, it's worth adding to that set.

Python's numeric defaults differ from Swift's in ways that silently change
answers — `%` versus `fmod`, banker's rounding in `round()`, `math.pow` raising
where Swift returns infinity. Those cases are covered by their own tests; see
[PORTING.md](PORTING.md) §3 before touching the evaluator.
