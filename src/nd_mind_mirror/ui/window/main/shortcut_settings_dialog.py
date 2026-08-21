"""Provide an Apply-based GUI editor for the dedicated keyboard shortcut YAML file."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class ShortcutSettingsDialog(QDialog):
    """Edit shortcut sequences in a table and apply them without restarting Mind Mirror."""

    def __init__(self, store, apply_callback, parent=None) -> None:
        """Build the file-backed shortcut table and connect its Apply button."""
        super().__init__(parent)
        self._store = store
        self._apply_callback = apply_callback
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(650, 520)

        self._path_label = QLabel(f"File: {self._store.path}", self)
        self._path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._table = QTableWidget(self)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._populate()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._path_label)
        layout.addWidget(self._table, 1)
        layout.addWidget(buttons)

    def apply(self) -> None:
        """Validate duplicate sequences, save YAML, and apply the new keys to live actions."""
        keys_by_id: dict[str, str] = {}
        seen: dict[str, str] = {}
        for row in range(self._table.rowCount()):
            id_item = self._table.item(row, 0)
            key_item = self._table.item(row, 1)
            action_id = str(id_item.data(Qt.ItemDataRole.UserRole) or "")
            keys = key_item.text().strip() if key_item is not None else ""
            normalized = QKeySequence(keys).toString(QKeySequence.SequenceFormat.PortableText)
            if keys and not normalized:
                QMessageBox.warning(self, "Keyboard Shortcuts", f"Invalid shortcut: {keys}")
                return
            if normalized and normalized in seen:
                QMessageBox.warning(
                    self,
                    "Keyboard Shortcuts",
                    f"{normalized} is assigned to both {seen[normalized]} and {id_item.text()}.",
                )
                return
            if normalized:
                seen[normalized] = id_item.text()
            keys_by_id[action_id] = normalized
        self._store.save_keys(keys_by_id)
        self._apply_callback()

    def _populate(self) -> None:
        """Fill the table from the current shortcut store while keeping stable action ids hidden in row data."""
        entries = self._store.entries()
        self._table.setRowCount(len(entries))
        for row, (action_id, entry) in enumerate(entries.items()):
            label_item = QTableWidgetItem(entry.get("label", action_id))
            label_item.setFlags(label_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            label_item.setData(Qt.ItemDataRole.UserRole, action_id)
            key_item = QTableWidgetItem(entry.get("keys", ""))
            self._table.setItem(row, 0, label_item)
            self._table.setItem(row, 1, key_item)
