"""Keep Structure highlighting deterministic without replacing panel methods."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView

from nd_mind_mirror.ui.panel.structure.latex_structure_panel import (
    LatexStructurePanel,
)


class StructureHighlightController:
    """Configure the Structure tree and delegate highlighting to its panel."""

    def __init__(self, structure_panel: LatexStructurePanel) -> None:
        self._panel = structure_panel
        tree = self._panel._tree
        tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tree.clearSelection()
        tree.setCurrentItem(None)
        self.apply_highlight()

    def apply_highlight(self) -> None:
        """Refresh the panel-owned semantic highlight without instance overrides."""
        LatexStructurePanel._apply_current_line_highlight(self._panel)
