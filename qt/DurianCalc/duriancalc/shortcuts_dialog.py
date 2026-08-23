"""Preferences dialog for defining shortcuts/constants, mirroring pearCalc's
shortcut list used for currency conversion and named constants.

Port of ../../mac/DurianCalc/DurianCalc/ShortcutsView.swift. SwiftUI's
`Table` becomes a QTableView backed by a small QAbstractTableModel; see
PORTING.md section 4.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from duriancalc.shortcuts import ShortcutStore

_NAME_COL, _VALUE_COL = 0, 1

_HELP_TEXT = (
    "Built-in constants: pi, e, tau. Functions: sin, cos, tan, asin, acos, "
    "atan, ln, log, log10, log2, sqrt, cbrt, abs, exp, floor, ceil, round, "
    "rad, deg. Operators: + − × ÷ ^ mod %."
)


class _ShortcutTableModel(QAbstractTableModel):
    def __init__(self, store: ShortcutStore, parent: QWidget | None = None):
        super().__init__(parent)
        self._store = store
        self._store.changed.connect(self._on_store_changed)

    def _on_store_changed(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._store.shortcuts)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "Name" if section == _NAME_COL else "Value"
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            item = self._store.shortcuts[index.row()]
            return item.name if index.column() == _NAME_COL else item.value
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:  # noqa: N802
        if not index.isValid() or role != Qt.EditRole:
            return False
        if index.column() == _NAME_COL:
            self._store.update(index.row(), name=str(value))
        else:
            try:
                self._store.update(index.row(), value=float(value))
            except (TypeError, ValueError):
                return False
        self.dataChanged.emit(index, index, [role])
        return True


class _ValueDelegate(QStyledItemDelegate):
    """Restricts the Value column to numeric input, so a typo can't write a
    non-numeric rate into settings.
    """

    def createEditor(self, parent, option, index):  # noqa: N802
        editor = QDoubleSpinBox(parent)
        editor.setDecimals(6)
        editor.setRange(-1e15, 1e15)
        return editor

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setValue(float(index.data(Qt.EditRole) or 0))

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.value(), Qt.EditRole)


class ShortcutsDialog(QDialog):
    def __init__(self, store: ShortcutStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setModal(False)
        self.resize(460, 320)
        self._store = store

        layout = QVBoxLayout(self)

        title = QLabel("Shortcuts & Constants")
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        subtitle = QLabel(
            "Use these names inside any expression — for example a "
            "currency rate or a constant of your own."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: palette(mid);")
        layout.addWidget(subtitle)

        self._model = _ShortcutTableModel(store, self)
        self._table = QTableView(self)
        self._table.setModel(self._model)
        self._table.setItemDelegateForColumn(_VALUE_COL, _ValueDelegate(self))
        self._table.horizontalHeader().setSectionResizeMode(_NAME_COL, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(_VALUE_COL, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setMinimumHeight(180)
        layout.addWidget(self._table)

        buttons = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._store.add)
        remove_button = QPushButton("Remove Last")
        remove_button.clicked.connect(self._store.remove_last)
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        help_label = QLabel(_HELP_TEXT)
        help_label.setWordWrap(True)
        small_font = help_label.font()
        small_font.setPointSize(max(small_font.pointSize() - 2, 8))
        help_label.setFont(small_font)
        help_label.setStyleSheet("color: palette(mid);")
        layout.addWidget(help_label)
