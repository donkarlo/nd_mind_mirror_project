"""LaTeX Preview diagnostics panel with source navigation and clipboard export."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_serializer import (
    LatexDiagnosticSerializer,
)
from nd_mind_mirror.ui.preview.latex.error.latex_error_tree import LatexErrorTree


class LatexErrorPanel(QWidget):
    """Resizable Preview diagnostics surface with source navigation and export."""

    source_location_requested = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._diagnostic: LatexDiagnostic | None = None
        self._serializer = LatexDiagnosticSerializer()

        self._title = QLabel("LaTeX diagnostics", self)
        title_font = self._title.font()
        title_font.setBold(True)
        self._title.setFont(title_font)

        self._hint = QLabel(
            "Drag the Trace/Location header divider to change the column widths.",
            self,
        )
        self._hint.setWordWrap(True)

        copy_icon = QIcon.fromTheme(
            "edit-copy",
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
        )
        self._copy_text_action = QAction(
            copy_icon,
            "Copy as text",
            self,
        )
        self._copy_yaml_action = QAction(
            "Copy as YAML",
            self,
        )
        self._copy_text_action.triggered.connect(
            lambda: self._copy_diagnostic("text")
        )
        self._copy_yaml_action.triggered.connect(
            lambda: self._copy_diagnostic("yaml")
        )

        copy_menu = QMenu(self)
        copy_menu.addAction(self._copy_text_action)
        copy_menu.addAction(self._copy_yaml_action)

        self._copy_button = QToolButton(self)
        self._copy_button.setDefaultAction(self._copy_text_action)
        self._copy_button.setMenu(copy_menu)
        self._copy_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self._copy_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._copy_button.setToolTip(
            "Copy the complete diagnostic tree and raw compiler output. "
            "Use the arrow to choose plain text or YAML."
        )
        self._copy_button.setEnabled(False)

        self._tree = LatexErrorTree(self)
        self._tree.source_location_requested.connect(
            self.source_location_requested.emit
        )

        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 2, 0)
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        title_row.addWidget(self._copy_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(5)
        layout.addLayout(title_row)
        layout.addWidget(self._hint)
        layout.addWidget(self._tree, 1)

    def show_diagnostic(self, diagnostic: LatexDiagnostic) -> None:
        self._diagnostic = diagnostic
        self._title.setText(f"LaTeX diagnostics — {diagnostic.summary}")
        self._copy_button.setEnabled(True)
        self._tree.show_diagnostic(diagnostic)

    def _copy_diagnostic(self, format_name: str) -> None:
        diagnostic = self._diagnostic
        if diagnostic is None:
            return

        if str(format_name).strip().casefold() == "yaml":
            text = self._serializer.to_yaml(diagnostic)
            label = "YAML"
        else:
            text = self._serializer.to_text(diagnostic)
            label = "text"

        QApplication.clipboard().setText(text)
        self._copy_button.setToolTip(
            f"Complete LaTeX diagnostics copied as {label}. "
            "Use the arrow to copy in the other format."
        )
