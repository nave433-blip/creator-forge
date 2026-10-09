"""Small shared widgets/helpers for the CreatorForge GUI."""

from __future__ import annotations

from typing import Any


def _qt():
    from PySide6 import QtWidgets
    return QtWidgets


def show_error(parent: Any, title: str, message: str) -> None:
    QtWidgets = _qt()
    QtWidgets.QMessageBox.warning(parent, title, str(message))


def show_info(parent: Any, title: str, message: str) -> None:
    QtWidgets = _qt()
    QtWidgets.QMessageBox.information(parent, title, str(message))


def confirm(parent: Any, title: str, message: str) -> bool:
    QtWidgets = _qt()
    return QtWidgets.QMessageBox.question(
        parent, title, str(message),
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
    ) == QtWidgets.QMessageBox.Yes


def ask_password(parent: Any, title: str, prompt: str) -> str | None:
    QtWidgets = _qt()
    from PySide6.QtWidgets import QInputDialog, QLineEdit
    text, ok = QInputDialog.getText(parent, title, prompt, QLineEdit.Password)
    return text if ok and text else None


def make_table(headers: list[str], rows: list[list[Any]],
               stretch_last: bool = True):
    """Read-only table with alternating rows, sized to content."""
    from PySide6 import QtWidgets
    table = QtWidgets.QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            table.setItem(r, c, QtWidgets.QTableWidgetItem(str(val)))
    table.resizeColumnsToContents()
    if stretch_last:
        table.horizontalHeader().setStretchLastSection(True)
    return table


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
