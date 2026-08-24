# DurianCalc

A minimal, expression-based calculator for macOS, built with SwiftUI —
inspired by [pearCalc](https://www.pearworks.com/pages/pearcalc.html) by
Walter Ritter.

Instead of a grid of buttons, you get a single compact field: type a whole
mathematical expression and the result appears live as you type. It uses the
small utility-window chrome (the thin title bar) and takes up almost no screen
space.

## Run it

1. Unzip the folder.
2. Open `DurianCalc.xcodeproj` in Xcode 15 or later.
3. Select the **DurianCalc** scheme and press **Run** (⌘R).

Requires macOS 13 or later.

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
- **Functions:** `sin cos tan asin acos atan sinh cosh tanh ln log log2 sqrt
  cbrt abs exp floor ceil round rad deg`
  (`rad`/`deg` convert between degrees and radians)
- **Constants:** `pi`, `e`, `tau`
- **Scientific notation:** `1e3`, `2.5e-4`

## Shortcuts & constants

Open **Settings** (⌘,) to define your own named values — handy for currency
conversion (`usd`, `eur`, …) or personal constants. Use them by name in any
expression. They're saved between launches.

## Files

- `DurianCalcApp.swift` — app entry; hosts the UI in an NSPanel utility window
  (thin title bar) and provides the Settings scene. Follows the system
  light/dark appearance.
- `ContentView.swift` — the single expression field, live result, Esc-to-clear
- `ExpressionEvaluator.swift` — tokenizer + recursive-descent parser/evaluator
- `ShortcutStore.swift` — user-defined shortcuts, persisted to UserDefaults
- `ShortcutsView.swift` — the preferences pane for editing shortcuts

## Not included (from the original)

The original pearCalc is also an app-launcher, a global-hotkey overlay, and a
text-replacement Service. This clone focuses on the calculator core. Those
features could be added with `NSWorkspace`, a global event monitor, and a
Services provider respectively.

## A note on testing

The parser's precedence and associativity were verified against a set of
tricky cases (right-associative `^`, unary-minus interaction, `mod`, trailing
`%`, nested parentheses, function application). If you extend the grammar,
it's worth adding to that set.
