"""Self-refreshing Manage Bookmarks dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class RangeBookmarkManagerDialog(QDialog):
    """Manage all persisted range bookmarks through callbacks owned by the menu."""

    def __init__(
        self,
        entries_provider,
        go_to_callback,
        remove_callback,
        remove_all_callback,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Bookmarks")
        self.resize(820, 420)
        self._entries_provider = entries_provider
        self._go_to_callback = go_to_callback
        self._remove_callback = remove_callback
        self._remove_all_callback = remove_all_callback

        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(
            ["File", "Bookmarked text", "Start", "End"]
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self._table.doubleClicked.connect(self._go_to_selected)
        layout.addWidget(self._table)

        controls = QHBoxLayout()
        self._go_to = QPushButton("Go to Bookmark", self)
        self._remove = QPushButton("Remove Bookmark", self)
        self._remove_all = QPushButton("Remove All Bookmarks", self)
        controls.addWidget(self._go_to)
        controls.addWidget(self._remove)
        controls.addWidget(self._remove_all)
        controls.addStretch(1)
        layout.addLayout(controls)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._go_to.clicked.connect(self._go_to_selected)
        self._remove.clicked.connect(self._remove_selected)
        self._remove_all.clicked.connect(self._remove_all_bookmarks)
        self._table.itemSelectionChanged.connect(self._sync_buttons)
        self._refresh()

    def _refresh(self) -> None:
        entries = list(self._entries_provider())
        self._table.setRowCount(0)
        for entry in entries:
            row = self._table.rowCount()
            self._table.insertRow(row)
            path = str(entry["path"])
            identifier = str(entry["id"])
            text = " ".join(str(entry.get("text", "")).split())
            if len(text) > 120:
                text = text[:117] + "…"

            file_item = QTableWidgetItem(Path(path).name)
            file_item.setToolTip(path)
            file_item.setData(Qt.ItemDataRole.UserRole, (path, identifier))
            self._table.setItem(row, 0, file_item)
            self._table.setItem(row, 1, QTableWidgetItem(text))
            self._table.setItem(row, 2, QTableWidgetItem(str(entry["start_char"])))
            self._table.setItem(row, 3, QTableWidgetItem(str(entry["end_char"])))

        self._table.resizeColumnsToContents()
        self._sync_buttons()

    def _selected_identity(self) -> tuple[str, str] | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            return None
        return str(value[0]), str(value[1])

    def _go_to_selected(self, *_args) -> None:
        identity = self._selected_identity()
        if identity is not None:
            self._go_to_callback(*identity)

    def _remove_selected(self) -> None:
        identity = self._selected_identity()
        if identity is None:
            return
        self._remove_callback(*identity)
        self._refresh()

    def _remove_all_bookmarks(self) -> None:
        self._remove_all_callback()
        self._refresh()

    def _sync_buttons(self) -> None:
        enabled = self._selected_identity() is not None
        self._go_to.setEnabled(enabled)
        self._remove.setEnabled(enabled)
        self._remove_all.setEnabled(self._table.rowCount() > 0)
