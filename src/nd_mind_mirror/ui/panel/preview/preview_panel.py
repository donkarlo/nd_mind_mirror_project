from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

        self._label = QLabel("Live LaTeX Preview", self)

        self._export_button = QPushButton("Export PDF", self)
        self._export_button.clicked.connect(self.export_requested.emit)

        self._fit_button = QPushButton("Fit", self)
        self._fit_button.setToolTip("Fit the whole PDF page in the preview panel")

        self._zoom_label = QLabel("Zoom:", self)
        self._zoom_edit = QLineEdit("100%", self)
        self._zoom_edit.setFixedWidth(68)
        self._zoom_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_edit.setToolTip("PDF zoom percentage (20% to 800%)")

        self._page_label = QLabel("Page – / –", self)
        self._page_label.setMinimumWidth(90)
        self._page_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
            | Qt.AlignmentFlag.AlignVCenter
        )

        self._preview = LatexPreview(self)

        self._fit_button.clicked.connect(self._preview.fit_to_panel)
        self._zoom_edit.editingFinished.connect(self._apply_zoom_edit)
        self._preview.view_status_changed.connect(self._on_view_status_changed)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addWidget(self._export_button, 1)
        controls.addWidget(self._fit_button)
        controls.addWidget(self._zoom_label)
        controls.addWidget(self._zoom_edit)
        controls.addWidget(self._page_label)

        self.panel_layout.addWidget(self._label)
        self.panel_layout.addLayout(controls)
        self.panel_layout.addWidget(self._preview, 1)

    @property
    def preview(self) -> LatexPreview:
        return self._preview

    def apply_settings(
        self,
        default_zoom_percent: int | float,
        auto_fit_on_open: bool = True,
        fit_width_percent: int | float = 95,
    ) -> None:
        self._preview.set_default_zoom_percent(
            default_zoom_percent
        )
        self._preview.configure_initial_view(
            auto_fit_on_open=auto_fit_on_open,
            fit_width_percent=fit_width_percent,
        )

    def _apply_zoom_edit(self) -> None:
        text = self._zoom_edit.text().strip().rstrip("%").strip()
        try:
            percent = int(round(float(text)))
        except ValueError:
            percent = 100
        percent = max(20, min(percent, 800))
        self._zoom_edit.setText(f"{percent}%")
        self._preview.set_zoom_percent(percent)

    def _on_view_status_changed(
        self,
        zoom_percent: float,
        page_number: int,
        page_count: int,
    ) -> None:
        if not self._zoom_edit.hasFocus():
            self._zoom_edit.setText(f"{int(round(zoom_percent))}%")
        if page_count <= 0 or page_number <= 0:
            self._page_label.setText("Page – / –")
        else:
            self._page_label.setText(f"Page {page_number} / {page_count}")
