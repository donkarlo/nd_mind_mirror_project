from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
)

from nd_mind_mirror.ui.panel.base.panel import Panel
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview


class PreviewPanel(Panel):
    export_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Rendered LaTeX", parent)

        self.setMinimumWidth(120)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel(
            "Live LaTeX Preview",
            self,
        )

        self._export_button = QPushButton(
            "Export PDF",
            self,
        )
        self._export_button.clicked.connect(
            self.export_requested.emit
        )

        self._preview = LatexPreview(self)

        self.panel_layout.addWidget(
            self._label
        )
        self.panel_layout.addWidget(
            self._export_button
        )
        self.panel_layout.addWidget(
            self._preview,
            1,
        )

    @property
    def preview(self) -> LatexPreview:
        return self._preview
