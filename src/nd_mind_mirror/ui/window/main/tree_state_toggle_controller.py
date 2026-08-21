"""Add explicit Collapse and Restore Previous State controls to Navigator and Structure trees."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QTreeWidgetItem, QWidget


class TreeStateToggleController:
    """Remember the exact expansion state before collapse and restore only that state, never Expand All."""

    def __init__(self, panel, tree, label, parent=None) -> None:
        """Attach separate collapse and restore buttons to an existing panel header."""
        self._panel = panel
        self._tree = tree
        self._label = label
        self._saved_state: list[str] | set[int] = []
        self._has_saved_state = False
        self._header = QWidget(parent or panel)

        self._collapse_button = QToolButton(self._header)
        self._collapse_button.setText("−")
        self._collapse_button.setFixedWidth(24)
        self._collapse_button.setToolTip(
            "Collapse all and remember the tree exactly as it is now"
        )
        self._collapse_button.clicked.connect(self.collapse)

        self._restore_button = QToolButton(self._header)
        self._restore_button.setText("↶")
        self._restore_button.setFixedWidth(24)
        self._restore_button.setEnabled(False)
        self._restore_button.setToolTip(
            "Restore the exact tree state from immediately before the last collapse"
        )
        self._restore_button.clicked.connect(self.restore)
        self._install_header()

    def toggle(self) -> None:
        """Preserve backward compatibility by collapsing first and restoring when a state already exists."""
        if self._has_saved_state:
            self.restore()
        else:
            self.collapse()

    def collapse(self) -> None:
        """Capture the current expansion state and collapse all nodes without ever expanding unrelated nodes."""
        if hasattr(self._panel, "expanded_paths"):
            self._saved_state = list(self._panel.expanded_paths())
        else:
            self._saved_state = self._expanded_structure_lines()
        self._tree.collapseAll()
        self._has_saved_state = True
        self._restore_button.setEnabled(True)

    def restore(self) -> None:
        """Restore only the paths or structure nodes that were expanded before the last collapse."""
        if not self._has_saved_state:
            return
        if hasattr(self._panel, "restore_state"):
            selected = self._panel.selected_path() if hasattr(self._panel, "selected_path") else ""
            self._panel.restore_state(list(self._saved_state), selected)
        else:
            saved = set(self._saved_state)
            for item in self._structure_items():
                line = int(item.data(0, Qt.ItemDataRole.UserRole) or 0)
                item.setExpanded(line in saved)

    def _install_header(self) -> None:
        """Replace the panel's standalone label row with a label-plus-collapse-plus-restore header."""
        layout = QHBoxLayout(self._header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._panel.panel_layout.removeWidget(self._label)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._collapse_button)
        layout.addWidget(self._restore_button)
        self._panel.panel_layout.insertWidget(0, self._header)

    def _expanded_structure_lines(self) -> set[int]:
        """Return source-line identifiers for all currently expanded Structure nodes."""
        result: set[int] = set()
        for item in self._structure_items():
            if item.isExpanded():
                result.add(int(item.data(0, Qt.ItemDataRole.UserRole) or 0))
        return result

    def _structure_items(self) -> list[QTreeWidgetItem]:
        """Return every Structure tree item in display-tree order."""
        items: list[QTreeWidgetItem] = []

        def walk(item: QTreeWidgetItem) -> None:
            """Append one structure item and recursively append its descendants."""
            items.append(item)
            for child_index in range(item.childCount()):
                walk(item.child(child_index))

        for top_index in range(self._tree.topLevelItemCount()):
            walk(self._tree.topLevelItem(top_index))
        return items
