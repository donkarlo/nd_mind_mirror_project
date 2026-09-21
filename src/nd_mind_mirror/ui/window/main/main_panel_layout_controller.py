"""Own the resize policy of the three main horizontal editor panes."""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QSplitter


class MainPanelLayoutController(QObject):
    """Keep side-pane widths stable while the editor absorbs window resizing."""

    _NAVIGATOR_INDEX = 0
    _EDITOR_INDEX = 1
    _PREVIEW_INDEX = 2
    _EXPECTED_PANE_COUNT = 3

    def __init__(self, splitter: QSplitter, parent=None) -> None:
        super().__init__(parent)
        self._splitter = splitter
        self.apply()

    def apply(self) -> None:
        """Make only Source/Visual elastic during outer-window resizing."""
        if self._splitter.count() != self._EXPECTED_PANE_COUNT:
            return
        self._splitter.setStretchFactor(self._NAVIGATOR_INDEX, 0)
        self._splitter.setStretchFactor(self._EDITOR_INDEX, 1)
        self._splitter.setStretchFactor(self._PREVIEW_INDEX, 0)
