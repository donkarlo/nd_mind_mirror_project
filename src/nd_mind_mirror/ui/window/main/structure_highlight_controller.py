"""Guarantee that every hierarchical Structure tree paints exactly one semantic highlight."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush
from PySide6.QtWidgets import QAbstractItemView


class StructureHighlightController:
    """Replace selection/current-item painting with one deterministic source-position highlight."""

    def __init__(self, structure_panel) -> None:
        """Install deterministic single-row highlighting on the supplied Structure panel."""
        self._panel = structure_panel
        tree = self._panel._tree
        tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tree.clearSelection()
        tree.setCurrentItem(None)
        self._panel._apply_current_line_highlight = self.apply_highlight
        self.apply_highlight()

    def apply_highlight(self) -> None:
        """Clear every visual selection/background and paint only the deepest preceding item."""
        tree = self._panel._tree
        items = self._panel._all_items_in_source_order()
        target = None
        current_line = max(int(self._panel._current_line), 1)

        tree.setUpdatesEnabled(False)
        try:
            tree.clearSelection()
            tree.setCurrentItem(None)
            for item in items:
                item.setSelected(False)
                item.setBackground(0, QBrush())
                try:
                    item_line = int(item.data(0, Qt.ItemDataRole.UserRole))
                except (TypeError, ValueError):
                    continue
                if item_line <= current_line:
                    target = item
                else:
                    break
            if target is not None:
                target.setBackground(0, self._panel._highlight_brush)
        finally:
            tree.setUpdatesEnabled(True)
            tree.viewport().update()
