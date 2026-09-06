"""Show all known references to a path before the existing delete confirmation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
)


class ReferenceDeleteDialog(QDialog):
    """List usages and let the user inspect them before continuing to delete."""

    def __init__(
        self,
        window,
        target: Path,
        usages: list[ReferenceOccurrence],
        jump_callback,
        parent=None,
    ) -> None:
        """Build the pre-delete occurrence list without changing delete semantics."""
        super().__init__(parent)
        self._window = window
        self._usages = list(usages)
        self._jump_callback = jump_callback
        self.setWindowTitle("Delete — file references")
        self.resize(900, 500)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{target}\n\nThis path is used in {len(usages)} reference(s). "
                "Double-click an item or press Enter to open that source location."
            )
        )

        self._list = QListWidget(self)
        for index, usage in enumerate(self._usages):
            item = QListWidgetItem(
                f"{usage.referring_file}  —  line {usage.line}  —  "
                f"\\{usage.command}{{{usage.raw_target}}}"
            )
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._activate)
        self._list.itemActivated.connect(self._activate)
        layout.addWidget(self._list, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is not None:
            button.setText("Continue to Delete…")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _activate(self, item: QListWidgetItem) -> None:
        """Open the selected occurrence through the controller callback."""
        try:
            usage = self._usages[int(item.data(Qt.ItemDataRole.UserRole))]
        except (TypeError, ValueError, IndexError):
            return
        self._jump_callback(self._window, usage)
