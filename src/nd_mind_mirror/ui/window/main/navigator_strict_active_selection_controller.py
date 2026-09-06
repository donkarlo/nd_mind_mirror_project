"""Keep the active editor file centered with an explicit Navigator selection palette."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPalette

from nd_mind_mirror.ui.window.main.navigator_active_selection_controller import (
    NavigatorActiveSelectionController,
)


class NavigatorStrictActiveSelectionController(
    NavigatorActiveSelectionController
):
    """Guarantee centered blue/white Navigator selection for the active editor tab."""

    def __init__(self, editor_panel, file_system_panel, parent=None) -> None:
        """Install active/inactive selection colors and reveal the initial active file."""
        self._editor_panel = editor_panel
        super().__init__(editor_panel, file_system_panel, parent)
        self._tree = file_system_panel._tree
        self._configure_selection_palette()

        current = editor_panel.current_path()
        if current is not None:
            QTimer.singleShot(
                0,
                lambda path=str(current): file_system_panel.select_path(
                    path,
                    force_reveal=True,
                ),
            )

    def _configure_selection_palette(self) -> None:
        """Keep selection blue with white text even while keyboard focus is in Editor."""
        palette = self._tree.palette()
        blue = QColor("#2f6fdb")
        white = QColor("#ffffff")
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
        ):
            palette.setColor(group, QPalette.ColorRole.Highlight, blue)
            palette.setColor(
                group,
                QPalette.ColorRole.HighlightedText,
                white,
            )
        self._tree.setPalette(palette)
