"""Persists the user-defined shortcut list to QSettings and exposes it as a
constants map for the evaluator.

Port of ../../mac/DurianCalc/DurianCalc/ShortcutStore.swift. Where the Swift
version stored one JSON-encoded blob under a single UserDefaults key, this
stores one JSON string under a single QSettings key -- see PORTING.md
section 4 for why (QSettings' INI backend coerces types and does not
round-trip Python lists cleanly, so an explicit JSON blob keeps the
serialisation predictable).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field

from PySide6.QtCore import QObject, QSettings, Signal

_SETTINGS_KEY = "shortcuts"

_DEFAULT_SHORTCUTS = [
    {"name": "usd", "value": 1.08},
    {"name": "golden", "value": 1.618},
]


@dataclass
class Shortcut:
    """A user-defined shortcut: a name that expands to a value inside
    expressions. In pearCalc these are used for currency conversion (e.g.
    "usd" -> 1.08) or as named constants.
    """

    name: str
    value: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ShortcutStore(QObject):
    """Owns the shortcut list, persisting it to QSettings on every change
    and emitting `changed` so the main window can re-evaluate immediately.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._shortcuts: list[Shortcut] = self._load()

    @property
    def shortcuts(self) -> list[Shortcut]:
        return self._shortcuts

    def set_shortcuts(self, shortcuts: list[Shortcut]) -> None:
        self._shortcuts = shortcuts
        self._save()
        self.changed.emit()

    def add(self) -> None:
        self._shortcuts.append(Shortcut(name="new", value=0))
        self._save()
        self.changed.emit()

    def remove_last(self) -> None:
        if self._shortcuts:
            self._shortcuts.pop()
            self._save()
            self.changed.emit()

    def remove_at(self, index: int) -> None:
        if 0 <= index < len(self._shortcuts):
            del self._shortcuts[index]
            self._save()
            self.changed.emit()

    def update(self, index: int, *, name: str | None = None, value: float | None = None) -> None:
        item = self._shortcuts[index]
        if name is not None:
            item.name = name
        if value is not None:
            item.value = value
        self._save()
        self.changed.emit()

    @property
    def as_constants(self) -> dict[str, float]:
        """Name -> value map for feeding into the evaluator."""
        result: dict[str, float] = {}
        for s in self._shortcuts:
            if s.name:
                result[s.name.lower()] = s.value
        return result

    # -- persistence ---------------------------------------------------

    def _load(self) -> list[Shortcut]:
        settings = QSettings()
        raw = settings.value(_SETTINGS_KEY, None)
        if raw:
            try:
                decoded = json.loads(raw)
                return [Shortcut(name=d["name"], value=d["value"], id=d.get("id", str(uuid.uuid4()))) for d in decoded]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        # A couple of sensible starter examples.
        return [Shortcut(name=d["name"], value=d["value"]) for d in _DEFAULT_SHORTCUTS]

    def _save(self) -> None:
        settings = QSettings()
        settings.setValue(_SETTINGS_KEY, json.dumps([asdict(s) for s in self._shortcuts]))
