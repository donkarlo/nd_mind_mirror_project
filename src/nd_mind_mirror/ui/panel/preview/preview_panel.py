from pathlib import Path
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
)

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic import (
    LatexDiagnostic,
)
from nd_mind_mirror.ui.panel.base.panel import Panel
from nd_mind_mirror.ui.preview.latex.error.latex_error_panel import LatexErrorPanel
from nd_mind_mirror.ui.preview.latex.latex_preview import LatexPreview
from nd_mind_mirror.ui.preview.markdown.markdown_preview import MarkdownPreview


class PreviewPanel(Panel):
    export_requested = Signal()
    close_requested = Signal()
    source_location_requested = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__("Rendered LaTeX", parent)

        self.setMinimumWidth(120)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self._label = QLabel("Live LaTeX Preview", self)
        # Kept only as a compatibility attribute for older controllers. The
        # top-right Preview button is now the single visible open/close toggle.
        self._close_button = QPushButton("", self)
        self._close_button.hide()

        self._export_button = QPushButton("Export PDF", self)
        self._export_button.setToolTip(
            "Save the PDF currently shown in Preview. The existing rendered PDF "
            "is copied immediately, so Export does not compile LaTeX again."
        )
        self._export_button.clicked.connect(self._export_current_pdf_directly)

        self._fit_button = QPushButton("Fit", self)
        self._fit_button.setToolTip(
            "Fit the widest rendered PDF content to 95% of the preview panel "
            "while cropping unused white page margins horizontally. The Zoom "
            "field shows the resulting render scale."
        )

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
        self._markdown_preview = MarkdownPreview(self)
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._preview)
        self._stack.addWidget(self._markdown_preview)
        self._stack.setCurrentWidget(self._preview)

        self._latex_error_panel = LatexErrorPanel(self)
        self._latex_error_panel.hide()
        self._latex_error_panel.source_location_requested.connect(
            self.source_location_requested.emit
        )

        self._preview_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self,
        )
        self._preview_splitter.setChildrenCollapsible(False)
        self._preview_splitter.setOpaqueResize(True)
        self._preview_splitter.addWidget(self._stack)
        self._preview_splitter.addWidget(self._latex_error_panel)
        self._preview_splitter.setStretchFactor(0, 3)
        self._preview_splitter.setStretchFactor(1, 2)

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

        self._controls_layout = controls
        self._latex_controls = [
            self._export_button,
            self._fit_button,
            self._zoom_label,
            self._zoom_edit,
            self._page_label,
        ]

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self._label, 1)

        self.panel_layout.addLayout(header)
        self.panel_layout.addLayout(controls)
        self.panel_layout.addWidget(self._preview_splitter, 1)

    def show_latex_mode(self) -> None:
        self._stack.setCurrentWidget(self._preview)
        self._label.setText("Live LaTeX Preview")
        for widget in self._latex_controls:
            widget.setVisible(True)

    def show_pdf(self, pdf_path) -> None:
        self.show_latex_mode()
        self._latex_error_panel.hide()
        self._preview.show_pdf(pdf_path)

    def show_latex_error(self, diagnostic: LatexDiagnostic) -> None:
        """Show a structured error trace while preserving the last valid PDF."""
        self.show_latex_mode()
        self._latex_error_panel.show_diagnostic(diagnostic)
        self._latex_error_panel.show()
        self._preview_splitter.setSizes(
            [
                max(self.height() - 270, 180),
                270,
            ]
        )
        self._preview.show_error(
            "LaTeX compilation failed. See the diagnostic tree below."
        )

    def show_markdown(self, source: str, source_path: str | Path) -> None:
        self._latex_error_panel.hide()
        self._markdown_preview.show_markdown(source, source_path)
        self._stack.setCurrentWidget(self._markdown_preview)
        self._label.setText(f"Rendered Markdown — {Path(source_path).name}")
        for widget in self._latex_controls:
            widget.setVisible(False)

    def show_message(self, message: str) -> None:
        self.show_latex_mode()
        self._latex_error_panel.hide()
        self._preview.show_message(message)

    @property
    def preview(self) -> LatexPreview:
        return self._preview

    def apply_settings(
        self,
        default_zoom_percent: int | float,
        auto_fit_on_open: bool = True,
        fit_width_percent: int | float = 95,
    ) -> None:
        self._preview.set_default_zoom_percent(default_zoom_percent)
        self._preview.configure_initial_view(
            auto_fit_on_open=auto_fit_on_open,
            fit_width_percent=fit_width_percent,
        )
        fit_value = max(50, min(int(round(float(fit_width_percent))), 100))
        self._fit_button.setText("Fit")
        self._fit_button.setToolTip(
            f"Fit the widest rendered PDF content to {fit_value}% of the "
            "preview panel, ignoring unused white page margins horizontally. "
            "The Zoom field shows the resulting render scale."
        )

    def _export_current_pdf_directly(self) -> None:
        """Save the already-rendered Preview PDF without starting another LaTeX compile."""
        rendered_pdf = self._preview.current_pdf_path
        if rendered_pdf is None:
            QMessageBox.information(
                self,
                "Export PDF",
                "There is no rendered PDF to export yet.",
            )
            return

        rendered_pdf = Path(rendered_pdf).expanduser().resolve()
        if not rendered_pdf.is_file():
            QMessageBox.critical(
                self,
                "Export PDF",
                f"Rendered PDF does not exist:\n{rendered_pdf}",
            )
            return

        window = self.window()
        editor_panel = getattr(window, "_editor_panel", None)
        source_path = editor_panel.current_path() if editor_panel is not None else None
        if source_path is not None:
            default_path = Path(source_path).expanduser().resolve().with_suffix(".pdf")
        else:
            default_path = Path.home() / rendered_pdf.name

        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            str(default_path),
            "PDF files (*.pdf)",
        )
        if not destination:
            return

        destination_path = Path(destination).expanduser()
        if destination_path.suffix.lower() != ".pdf":
            destination_path = destination_path.with_suffix(".pdf")
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rendered_pdf, destination_path)
        except OSError as exc:
            QMessageBox.critical(self, "Export PDF", str(exc))
            return
        status_bar = getattr(window, "statusBar", None)
        if callable(status_bar):
            status_bar().showMessage(
                f"Exported PDF to {destination_path}",
                5000,
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
