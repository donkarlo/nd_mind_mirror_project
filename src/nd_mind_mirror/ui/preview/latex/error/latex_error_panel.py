from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.ui.preview.latex.error.latex_error_tree import LatexErrorTree


class LatexErrorPanel(QWidget):
    """Resizable Preview diagnostics surface with source navigation."""

    source_location_requested = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._title = QLabel("LaTeX diagnostics", self)
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._hint = QLabel(
            "Double-click a file or error row to open the source location.",
            self,
        )
        self._hint.setWordWrap(True)

        self._tree = LatexErrorTree(self)
        self._tree.source_location_requested.connect(
            self.source_location_requested.emit
        )

        header = QHBoxLayout()
        header.setContentsMargins(2, 0, 2, 0)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._hint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(5)
        layout.addLayout(header)
        layout.addWidget(self._tree, 1)

    def show_diagnostic(self, diagnostic: LatexDiagnostic) -> None:
        self._title.setText(f"LaTeX diagnostics — {diagnostic.summary}")
        self._tree.show_diagnostic(diagnostic)
