"""Guarantee that the Structure panel paints exactly one active-section highlight."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView


class StructureHighlightController:
    """Replace ambiguous selection painting with one deterministic source-position highlight."""

    def __init__(self, structure_panel) -> None:
        """Install deterministic highlighting on the supplied Structure panel instance."""
        self._panel = structure_panel
        self._panel._tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._panel._apply_current_line_highlight = self.apply_highlight
        self.apply_highlight()

    def apply_highlight(self) -> None:
        """Clear every background first and then paint only the deepest preceding structure item."""
        items = self._panel._all_items_in_source_order()
        target = None
        current_line = max(int(self._panel._current_line), 1)
        for item in items:
            item.setData(0, Qt.ItemDataRole.BackgroundRole, None)
            try:
                item_line = int(item.data(0, Qt.ItemDataRole.UserRole))
            except (TypeError, ValueError):
                continue
            if item_line <= current_line:
                target = item
            else:
                break
        self._panel._tree.clearSelection()
        if target is not None:
            target.setBackground(0, self._panel._highlight_brush)
