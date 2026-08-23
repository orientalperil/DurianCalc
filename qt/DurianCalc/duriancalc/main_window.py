"""The single expression field, live result, Esc-to-clear.

Port of ../../mac/DurianCalc/DurianCalc/ContentView.swift.

Window-chrome fidelity notes (see PORTING.md section 5):
- The mac version hosts this in an NSPanel with .utilityWindow styling for
  the thin title bar; there is no portable Linux equivalent, since window
  decoration is the window manager's job, not the app's. This window uses
  the Qt.Tool flag, which nudges some window managers toward lighter
  decoration and degrades gracefully everywhere else.
- Esc-to-clear needs a plain QWidget top level, not QDialog -- QDialog
  swallows Escape as a reject-and-close, which is the exact trap the
  Swift EscKeyHandler exists to work around, in a different costume.
- Height is locked and recomputed whenever the result row's visibility
  changes (via setFixedHeight against the layout's own size hint), so only
  the width is user-resizable -- mirroring windowWillResize(_:to:) in
  DurianCalcApp.swift without needing to intercept every resize event.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeyEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from duriancalc.evaluator import EvalError, ExpressionEvaluator
from duriancalc.shortcuts import ShortcutStore

_ERROR_COLOR = "#D9822B"  # matches SwiftUI's .orange in this context


class _ExpressionLineEdit(QLineEdit):
    """A QLineEdit that reports Escape instead of letting it go to waste --
    plain QLineEdit does nothing with Escape, but we want it to clear the
    field (see module docstring on why the top level can't be a QDialog).
    """

    escape_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def format_value(value: float) -> str:
    """Locale-independent formatting: always uses '.' regardless of system
    locale, unlike Swift's NumberFormatter which follows it. See
    PORTING.md section 3.5.
    """
    if math.isnan(value):
        return "not a number"
    if math.isinf(value):
        return "-∞" if value < 0 else "∞"
    if value == math.floor(value) and abs(value) < 1e15:
        return f"{value:.0f}"
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text if text else "0"


class MainWindow(QWidget):
    def __init__(self, shortcuts: ShortcutStore, parent: QWidget | None = None):
        super().__init__(parent)
        self._shortcuts = shortcuts
        self._result_text = ""
        self._is_error = False

        self.setWindowTitle("DurianCalc")
        # Qt.WindowStaysOnTopHint is what KDE/X11 surfaces as the "Keep
        # Above Others" window-menu toggle. It only works under X11 --
        # Wayland's xdg-shell protocol deliberately has no client-side
        # always-on-top request (only the compositor/user can do that), so
        # this hint is silently ignored under KWin Wayland. Getting the
        # same effect there needs a KWin Window Rule instead; see the
        # README's "Always-on-top on Wayland" section.
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(320)
        self.resize(440, 80)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        self._card = QFrame(self)
        self._card.setObjectName("card")
        self._card.setStyleSheet(
            "#card { background: palette(base); border: 1px solid rgba(0, 0, 0, 0.12);"
            " border-radius: 12px; }"
        )
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        outer.addWidget(self._card)

        card_layout.addWidget(self._build_input_row())

        self._divider = QFrame(self._card)
        self._divider.setFrameShape(QFrame.HLine)
        self._divider.setStyleSheet("color: rgba(0, 0, 0, 0.10);")
        card_layout.addWidget(self._divider)

        card_layout.addWidget(self._build_result_row())

        # Without this, the card (Preferred vertical policy, which still
        # permits growth) would stretch to absorb any leftover height if
        # the window is ever taller than the content needs -- e.g. a
        # window manager applying a size before our own resizeEvent
        # correction runs. The stretch item soaks up that space instead.
        outer.addStretch(1)

        self._set_result_row_visible(False)
        self._field.setFocus()

    # -- UI construction -------------------------------------------------

    def _build_input_row(self) -> QWidget:
        row = QWidget(self._card)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self._field = _ExpressionLineEdit(row)
        self._field.setFrame(False)
        self._field.setClearButtonEnabled(True)
        font = self._field.font()
        font.setPointSize(font.pointSize() + 6)
        self._field.setFont(font)
        self._field.textChanged.connect(self._live_evaluate)
        self._field.returnPressed.connect(self._commit)
        self._field.escape_pressed.connect(self.clear_all)
        layout.addWidget(self._field)

        return row

    def _build_result_row(self) -> QWidget:
        row = QWidget(self._card)
        self._result_row = row
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self._symbol_label = QLabel("=", row)
        symbol_font = self._symbol_label.font()
        symbol_font.setPointSize(symbol_font.pointSize() + 4)
        symbol_font.setBold(True)
        self._symbol_label.setFont(symbol_font)
        layout.addWidget(self._symbol_label)

        self._result_label = QLabel("", row)
        result_font = self._result_label.font()
        result_font.setPointSize(result_font.pointSize() + 6)
        self._result_label.setFont(result_font)
        self._result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._result_label, 1)

        self._copy_button = QToolButton(row)
        self._copy_button.setText("⧉")
        self._copy_button.setToolTip("Copy result")
        self._copy_button.setAutoRaise(True)
        self._copy_button.clicked.connect(self._copy_result)
        layout.addWidget(self._copy_button)

        row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return row

    # -- Actions -----------------------------------------------------------

    def clear_all(self) -> None:
        self._field.clear()
        self._field.setFocus()

    # -- Evaluation --------------------------------------------------------

    def _live_evaluate(self, text: str) -> None:
        trimmed = text.strip()
        if not trimmed:
            self._set_result("", is_error=False)
            return

        evaluator = ExpressionEvaluator(constants=self._shortcuts.as_constants)
        try:
            value = evaluator.evaluate(trimmed)
            self._set_result(format_value(value), is_error=False)
        except EvalError as error:
            # While typing, show a gentle hint rather than a hard error.
            self._set_result(str(error), is_error=True)

    def _commit(self) -> None:
        if self._is_error or not self._result_text:
            return
        # Feed the result back in, so you can keep calculating from it.
        self._field.setText(self._result_text)
        self._field.setFocus()

    def _copy_result(self) -> None:
        QGuiApplication.clipboard().setText(self._result_text)

    def _set_result(self, text: str, *, is_error: bool) -> None:
        self._result_text = text
        self._is_error = is_error

        self._symbol_label.setText("⚠" if is_error else "=")
        self._result_label.setText(text)
        color = _ERROR_COLOR if is_error else "palette(text)"
        self._symbol_label.setStyleSheet(f"color: {color};")
        self._result_label.setStyleSheet(f"color: {color};")
        self._copy_button.setVisible(not is_error and bool(text))

        self._set_result_row_visible(bool(text))

    def _set_result_row_visible(self, visible: bool) -> None:
        self._result_row.setVisible(visible)
        self._divider.setVisible(visible)
        self._sync_height()

    def _sync_height(self) -> None:
        # QLayout applies its own minimumSize() to the widget as a hard
        # floor on every activation (that's how "auto-shrinking" layouts
        # normally work) -- but that floor is stale until the layout is
        # *activated*, not merely invalidated. Without forcing activation
        # here, resize() below would silently clamp back up to the old
        # (pre-hide) minimum height whenever the result row had just been
        # hidden, which is exactly the "field gets taller and stays there"
        # bug this guards against.
        self._card.layout().activate()
        self.layout().activate()
        target = self.layout().sizeHint().height()
        if self.height() != target:
            self.resize(self.width(), target)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        # Allow horizontal resizing only. There's no Qt hook to veto a
        # proposed size before it's applied (unlike NSPanel's
        # windowWillResize), so instead we let the resize happen and
        # immediately correct the height -- this converges in one extra
        # resizeEvent and keeps the top edge anchored.
        super().resizeEvent(event)
        target = self.layout().sizeHint().height()
        if event.size().height() != target:
            self.resize(event.size().width(), target)

    # -- Lifecycle -----------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Quit only when this panel itself closes -- not when some other
        # window (e.g. Preferences) closes first. Mirrors windowWillClose
        # in DurianCalcApp.swift; app.py disables quitOnLastWindowClosed
        # so this is the sole termination path.
        event.accept()
        QApplication.instance().quit()
