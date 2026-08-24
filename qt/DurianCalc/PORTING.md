# Porting DurianCalc from SwiftUI to Qt (PySide6)

A plan for rewriting the macOS DurianCalc (`../../mac/DurianCalc`) as a Python +
Qt application for Linux, packaged as an AppImage.

The goal is a port, not a reimagining: same behaviour, same feel, same README.
Where the platforms genuinely differ, this document says so explicitly rather
than quietly changing the app.

---

## 1. Target layout

```
qt/DurianCalc/
├── README.md                  # mirrors the mac README (see §7)
├── PORTING.md                 # this file
├── pyproject.toml             # Poetry project + dependencies
├── poetry.lock                # committed, for reproducible builds
├── duriancalc/
│   ├── __init__.py
│   ├── __main__.py            # `python -m duriancalc`
│   ├── app.py                 # ← DurianCalcApp.swift  (QApplication, window chrome)
│   ├── main_window.py         # ← ContentView.swift    (field, live result, Esc)
│   ├── evaluator.py           # ← ExpressionEvaluator.swift
│   ├── shortcuts.py           # ← ShortcutStore.swift
│   ├── shortcuts_dialog.py    # ← ShortcutsView.swift
│   └── resources/
│       └── duriancalc.svg
├── tests/
│   └── test_evaluator.py      # ← ExpressionEvaluatorTests.swift
└── packaging/
    ├── duriancalc.desktop
    ├── duriancalc.png         # 256×256, required by appimagetool
    └── build-appimage.sh
```

### Source file mapping

| macOS (Swift)              | Linux (Python)              | Difficulty | Notes                                        |
| -------------------------- | --------------------------- | ---------- | -------------------------------------------- |
| `ExpressionEvaluator.swift`| `evaluator.py`              | Easy       | Pure logic; watch the numeric traps in §3    |
| `ExpressionEvaluatorTests` | `tests/test_evaluator.py`   | Easy       | Port every case verbatim                     |
| `ShortcutStore.swift`      | `shortcuts.py`              | Easy       | `UserDefaults` → `QSettings`                 |
| `ShortcutsView.swift`      | `shortcuts_dialog.py`       | Medium     | SwiftUI `Table` → `QTableView` + model       |
| `ContentView.swift`        | `main_window.py`            | Medium     | Live-resize behaviour needs care             |
| `DurianCalcApp.swift`      | `app.py`                    | **Hard**   | `NSPanel` utility chrome has no Linux twin   |

---

## 2. Recommended sequence

Each phase leaves the tree in a working state.

| Phase | Work | Why this order |
| ----- | ---- | -------------- |
| **0** | Poetry scaffold, package skeleton, pytest wired up | Cheap; everything else builds on it |
| **1** | `evaluator.py` + the full test port | Pure logic, no GUI, no packaging. Highest value, lowest risk — and it is where the real bugs live |
| **2** | `shortcuts.py` + persistence | Small, testable without a GUI |
| **3** | `main_window.py` — field, live result, Esc, Return, copy | The app becomes usable here |
| **4** | `shortcuts_dialog.py` + `Ctrl+,` | Feature parity reached |
| **5** | Window chrome fidelity (§5) | Cosmetic, and the most platform-dependent — do it once behaviour is settled |
| **6** | AppImage packaging (§6) | Needs a finished app to bundle |

Phase 1 is the bulk of the correctness risk. Do not start the GUI until the
ported test suite is green.

---

## 3. The evaluator — a direct port with five real traps

The grammar, the recursive-descent structure, the `lastWasPercent` flag, and the
error cases all translate one-to-one. Keep the same function names and the same
docstring describing the grammar, so the two files stay diffable.

These five differences will silently produce wrong answers if missed. Each one
is covered by an existing test, which is why Phase 1 ports the tests first.

### 3.1 `mod` — floored, sign follows the divisor

Swift's `truncatingRemainder(dividingBy:)` is C `fmod`: the sign follows the
**dividend**. Python's `%` operator is floored: the sign follows the
**divisor**, which is what most people mean by "mod" unqualified (`-10 mod 3`
lands on the residue class `2`, the same way 2 hours before 12 o'clock reads
as 10, not -2).

Both evaluators deliberately use the floored convention, so they agree with
each other and with Python's own `%`:

| Expression   | Floored (both evaluators) | C `fmod` (not used) |
| ------------ | -------------------------- | -------------------- |
| `-10 mod 3`  | `2`                        | `-1`                 |
| `10 mod -3`  | `-2`                       | `1`                  |

In Python, `%` already does this — use it directly, no `math.fmod`. In
Swift, `Double` has no built-in floored-mod, so it's implemented as
`value - rhs * (value / rhs).rounded(.down)`. Keep the divide-by-zero guard
ahead of it in both.

### 3.2 `round()` — Python rounds half-to-even

Swift's `.rounded()` rounds half **away from zero**. Python's built-in `round()`
does banker's rounding.

`round(2.5)` is `3` in Swift and `2` in Python — and `assertEval("round(2.5)", 3)`
is already in the test suite. Implement half-away-from-zero explicitly
(`copysign(floor(abs(x) + 0.5), x)`), do not call the builtin.

### 3.3 `pow` — Python raises where Swift returns a float

| Case                  | Swift `pow`  | Python `math.pow`  | Port should do                        |
| --------------------- | ------------ | ------------------ | ------------------------------------- |
| `(-8) ^ 0.5`          | `nan`        | `ValueError`       | Raise a domain error (better UX)      |
| `10 ^ 400`            | `inf`        | `OverflowError`    | Return `inf` — the UI renders it `∞`  |

The overflow case matters: `ContentView` formats infinity as `∞`, so turning
`OverflowError` into a hard error would regress behaviour. Catch it and return
`math.inf` with the sign of the base.

### 3.4 Character classes are Unicode-wide in Swift

`Character.isNumber` and `.isLetter` accept far more than ASCII (Arabic-Indic
digits, accented letters, superscripts). Python's `str.isdigit()` / `isalpha()`
have similar but not identical coverage.

Restrict the lexer to ASCII explicitly (`"0" <= c <= "9"`, `c.isascii() and
c.isalpha()`). This is a deliberate, documented narrowing — it makes the lexer
predictable and matches every case anyone actually types.

### 3.5 Locale-dependent output formatting

`NumberFormatter` uses the **user's locale** decimal separator, so a German mac
shows `3,5`. Python f-strings always emit `.`.

Decide and document one of:

- **Force `.` always** (recommended) — matches the README's examples and keeps
  copied results pasteable into code.
- **Use `QLocale`** for true parity with the mac behaviour.

The rest of the format logic ports directly: `nan` → `"not a number"`, `±inf` →
`"∞"` / `"-∞"`, integral values under `1e15` → no decimal point, otherwise up to
10 fraction digits with trailing zeros stripped and no thousands separator.

### 3.6 Bugs worth fixing during the port

Carried over from reading the Swift source. Fix these in the Python version and
note them here rather than faithfully reproducing them:

- **Malformed numbers evaluate to zero.** The lexer consumes digits and dots
  greedily, so `1.2.3` reaches `Double("1.2.3")`, which is `nil`, and the `?? 0`
  turns it into `0` — a silently wrong answer. Python's `float()` raises; let it,
  and surface a proper "malformed number" error.
- **`,` can never parse.** The lexer emits a comma token that no production
  accepts, so `max(1,2)` fails with a confusing "unexpected" message. Either drop
  the token or keep it as the hook for multi-argument functions later.
- **Unbalanced parens report "Incomplete expression"** via `unexpectedEnd` even
  when tokens remain. A clearer message is a one-line improvement.
- **`log10` is an undocumented alias** for `log`. Keep it, and add it to the
  README's function list.
- **`history` in `ContentView` is written but never read.** Either drop it, or
  implement the recall UI it was clearly intended for. Do not port it as-is.

---

## 4. Shortcut storage

`UserDefaults` + `Codable` becomes `QSettings`.

- Store the list as a **JSON string under one key** (`duriancalc/shortcuts`),
  mirroring how the Swift version stores one `Data` blob. This keeps the
  serialisation explicit and avoids `QSettings`' lossy round-tripping of Python
  lists and its type coercion on the INI backend.
- `QSettings` on Linux writes `~/.config/DurianCalc/DurianCalc.conf`. Set
  `organizationName` and `applicationName` **before** any `QSettings` is
  constructed, or the path silently changes.
- Keep the starter defaults: `usd = 1.08`, `golden = 1.618`.
- Keep the per-row `id` (a `uuid4` string). It is not decorative — `QTableView`
  needs stable row identity, the same reason SwiftUI needed `Identifiable`.
- `@Published … didSet { save() }` becomes a `Signal` emitted on mutation, with
  the save call in the same place. The main window subscribes and re-evaluates
  so an edited rate updates the visible result immediately.

`ShortcutsView`'s SwiftUI `Table` maps to a `QTableView` backed by a small
`QAbstractTableModel` (two editable columns, name and value). Use a
`QDoubleSpinBox` or a validated delegate for the value column so a typo cannot
write a non-numeric rate into settings.

---

## 5. Window chrome — the one genuine fidelity gap

The mac app deliberately uses an `NSPanel` with `.utilityWindow` to get the thin
title bar, and comments say a plain `WindowGroup` could not produce it. **There
is no portable Linux equivalent**, because window decorations belong to the
window manager, not the app.

Three options, in order of recommendation:

1. **`Qt.Tool` window flag** *(recommended default)*. One line. Many X11 window
   managers give tool windows lighter decoration; GNOME and most Wayland
   compositors render them identically to normal windows. Degrades gracefully.
2. **Frameless + custom title bar** (`Qt.FramelessWindowHint`). Full control and
   the closest visual match, but you must reimplement drag-to-move (via
   `windowHandle().startSystemMove()`), the close button, and you forfeit WM
   snapping, keyboard move/resize, and tiling-WM cooperation.
3. **Plain window.** Honest and boring.

Start with option 1 and revisit only if the look matters more than WM
integration. Record the choice in the README so it is not re-litigated.

### Other chrome details

| macOS behaviour | Qt approach | Watch out for |
| --------------- | ----------- | ------------- |
| Esc clears the field | `QShortcut` on `Qt.Key_Escape`, or `keyPressEvent` | Use a plain `QWidget` top level, **not** `QDialog` — `QDialog` swallows Esc as reject. This is the exact trap the Swift `EscKeyHandler` was working around, in a different costume |
| Height locked, width resizable | Recompute height in `resizeEvent` / after toggling the result row | Do not `setFixedHeight` once — the natural height changes as the result row appears and disappears |
| `minWidth: 320` | `setMinimumWidth(320)` | — |
| Light/dark appearance | No forced `QPalette`, no forced style | Both apps follow the system setting rather than forcing light mode, so widget code must stick to palette-relative colors (`palette(base)`, `palette(text)`, `palette(mid)`) instead of hardcoded hex, or dark mode renders borders/dividers invisible. Known gap: QSS `palette(...)` references resolve once, at stylesheet-apply time, and don't stay live-bound -- switching the system theme while the app is already running leaves colors stale until relaunch. The mac version doesn't have this problem, since SwiftUI's dynamic colors update live on an appearance change. Accent `Color(0.36, 0.62, 0.20)` is `#5C9E33` and is one of the few values still fixed, since it reads fine in both modes |
| SF Rounded font | Family fallback list | SF Rounded does not exist on Linux. Try a rounded face, fall back to the default UI font. Bundling a font adds a licence to track |
| Settings via `⌘,` | `QShortcut` for `Ctrl+,` | There is no always-present app menu on Linux — also expose Preferences from a context menu or a small button, or it is undiscoverable |
| Quit when the panel closes | Default `quitOnLastWindowClosed` | Make the preferences dialog a **child** of the main window so it does not keep the app alive |
| Copy button | `QGuiApplication.clipboard().setText()` | On X11 the clipboard is owned by the process — copied text vanishes on quit unless a clipboard manager is running. Worth a line in the README |
| Custom clear "✕" button | `QLineEdit.setClearButtonEnabled(True)` | Built in, and better than hand-rolling it |

---

## 6. Packaging

### Dependencies (Poetry)

| Dependency | Scope | Note |
| ---------- | ----- | ---- |
| `PySide6-Essentials` | main | **Not** plain `PySide6`. The full wheel pulls WebEngine, Qt3D, Charts, Designer and more — hundreds of megabytes this app never touches |
| `pytest` | dev | — |
| `ruff` | dev | Optional, but cheap to add now |
| `pyinstaller` | dev | Build-time only; must not land in the runtime env |

Target Python 3.10+ (the floor `PySide6-Essentials` itself requires). Commit
`poetry.lock`. Declare a `duriancalc` console entry
point so `poetry run duriancalc` works from Phase 0 onward.

### AppImage strategy

**Recommended: PyInstaller → AppDir → `appimagetool`.**

PyInstaller's PySide6 hook already knows how to collect the Qt libraries and
platform plugins; wrapping its `dist/` output in an AppDir is then mechanical.
The alternative — a `python-appimage` base with pip installed into it — is
simpler to start but harder to slim down. `linuxdeploy-plugin-qt` is aimed at
C++ Qt builds and fights with PyInstaller; skip it.

The AppDir needs, at its root: `AppRun` (executable), `duriancalc.desktop`, and
`duriancalc.png` — the icon name must match the desktop file's `Icon=` key,
which must have **no** file extension.

### AppImage pitfalls to plan for

These are the ones that cost an afternoon each:

- **Build on the oldest glibc you intend to support** (e.g. an Ubuntu 22.04
  container). AppImages are forward-compatible, never backward. Building on a
  rolling distro produces a binary that runs only on rolling distros.
- **`libxcb-cursor0` is required by Qt 6.5+.** Missing it fails at startup with
  the notoriously unhelpful *"could not load the Qt platform plugin xcb"*. Bundle
  it, and test on a clean container, not your dev machine.
- **Prune Qt aggressively.** Even with `PySide6-Essentials`, excluding unused
  modules and Qt translations is the difference between a ~300 MB and a ~80 MB
  AppImage. Add excludes deliberately, then re-test — an over-eager exclude that
  removes a platform plugin only fails at runtime.
- **Build from `poetry install --only main`** so dev dependencies (PyInstaller
  itself, pytest) are not swept into the bundle.
- **`appimagetool` needs FUSE 2**, which newer distros and CI images do not ship.
  Use `--appimage-extract-and-run` in CI.
- **Ship both X11 and Wayland platform plugins** and smoke-test under each;
  `QT_QPA_PLATFORM=wayland` should work, not just fall back to XWayland.

Verification before calling a release good: run the AppImage on a clean
container of the oldest supported distro, under both X11 and Wayland, with the
settings file absent (first run) and present (upgrade).

---

## 7. Keeping the README similar

The README is the user-facing contract, and most of it is platform-neutral.
Change as little as possible.

| Section | Treatment |
| ------- | --------- |
| Title, intro, pearCalc credit | **Unchanged** except "for macOS, built with SwiftUI" → "for Linux, built with Qt" |
| *How to use* | **Unchanged** — Return carries forward, Esc clears, copy button |
| *Supported syntax* | **Unchanged** — this is the evaluator's contract, and the port must not alter it (add the `log10` alias) |
| *Shortcuts & constants* | Unchanged but for `⌘,` → `Ctrl+,` |
| *Not included* | Reword the macOS API name-drops (`NSWorkspace`, Services) to their freedesktop counterparts |
| *A note on testing* | Unchanged in substance; mention `pytest` |
| *Run it* | **Rewritten** — Poetry instead of Xcode |
| *Building an AppImage* | **New** — the release path has no mac equivalent |
| *Files* | **Rewritten** — same annotated-list format, Python modules |

If the two READMEs drift apart in any section other than *Run it*, *Building an
AppImage*, and *Files*, something has been ported wrong.

---

## 8. Definition of done

- [ ] Every case in `ExpressionEvaluatorTests.swift` passes in `pytest`, verbatim
- [ ] Added tests cover the §3 traps: negative `mod`, `round(2.5)`, `10^400`,
      malformed numbers
- [ ] Typing gives a live result; Return carries it forward; Esc clears
- [ ] Shortcuts persist across restarts and take effect immediately when edited
- [ ] Window opens near 440×80, resizes horizontally only, minimum width 320
- [ ] AppImage runs on a clean oldest-supported-distro container, X11 and Wayland
- [ ] README differs from the mac README only in the three sections named in §7
