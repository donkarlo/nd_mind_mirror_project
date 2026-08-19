from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QLabel,
    QStackedWidget,
    QVBoxLayout,
)

from nd_mind_mirror.ui.preview.base.preview import Preview
from nd_mind_mirror.ui.preview.pdf.selectable_pdf_view import (
    SelectablePdfView,
)


class LatexPreview(Preview):
    view_status_changed = Signal(float, int, int)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setMinimumWidth(0)
        self._current_pdf_path: Path | None = None
        self._source_document_path: Path | None = None
        self._reset_position_on_next_pdf = True
        self._has_success_for_current_source = False
        self._last_error = ""
        self._default_zoom_percent = 100.0
        self._auto_fit_on_open = True
        self._fit_width_percent = 95

        self._pdf_view = SelectablePdfView(self)
        self._pdf_view.view_status_changed.connect(
            self.view_status_changed.emit
        )
        self._pdf_view.setMinimumWidth(0)

        self._message = QLabel(
            "Open a .tex file to render its preview.",
            self,
        )
        self._message.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )
        self._message.setWordWrap(True)
        self._message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._message.setMargin(12)

        self._stack = QStackedWidget(self)
        self._stack.setMinimumWidth(0)
        self._stack.addWidget(self._message)
        self._stack.addWidget(self._pdf_view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)

    @property
    def current_pdf_path(self) -> Path | None:
        return self._current_pdf_path

    def set_default_zoom_percent(
        self,
        percent: int | float,
    ) -> None:
        value = max(20.0, min(float(percent), 800.0))
        self._default_zoom_percent = value
        if self._current_pdf_path is not None:
            self._pdf_view.set_zoom_percent(value)

    def configure_initial_view(
        self,
        auto_fit_on_open: bool,
        fit_width_percent: int | float,
    ) -> None:
        self._auto_fit_on_open = bool(auto_fit_on_open)
        self._fit_width_percent = max(50, min(int(fit_width_percent), 100))

    def set_source_document(
        self,
        path: str | Path,
    ) -> None:
        source_path = Path(path).expanduser().resolve()
        if source_path == self._source_document_path:
            return

        self._source_document_path = source_path
        self._reset_position_on_next_pdf = True
        self._has_success_for_current_source = False
        self._current_pdf_path = None
        self._last_error = ""

    def show_pdf(self, path: str) -> None:
        pdf_path = Path(path).resolve()

        if not pdf_path.is_file():
            self._current_pdf_path = None
            self.show_error(
                f"Generated PDF does not exist: {pdf_path}"
            )
            return

        reset_position = self._reset_position_on_next_pdf
        if not self._pdf_view.show_pdf(
            pdf_path,
            reset_position=reset_position,
        ):
            self._current_pdf_path = None
            self.show_error(
                "Could not initialize the selectable Qt Quick PDF preview. "
                "PySide6/Qt 6.8 or newer is required."
            )
            return

        if reset_position:
            if self._auto_fit_on_open:
                # PdfDocument/page geometry becomes available shortly after
                # the source URL is loaded. Fit once the QML view has laid out
                # the first page; subsequent LaTeX passes keep the user's view.
                QTimer.singleShot(120, self.fit_to_panel)
            else:
                self._pdf_view.set_zoom_percent(
                    self._default_zoom_percent
                )

        self._reset_position_on_next_pdf = False
        self._current_pdf_path = pdf_path
        self._has_success_for_current_source = True
        self._last_error = ""
        self._pdf_view.setToolTip("")
        self._stack.setCurrentWidget(
            self._pdf_view
        )

    def fit_to_panel(self) -> None:
        if self._current_pdf_path is None:
            return
        self._pdf_view.fit_to_panel(self._fit_width_percent)

    def set_zoom_percent(self, percent: int | float) -> None:
        if self._current_pdf_path is None:
            return
        self._pdf_view.set_zoom_percent(percent)

    def scroll_to_source_location(
        self,
        page: int,
        x: float,
        y: float,
    ) -> None:
        if self._current_pdf_path is None:
            return
        self._pdf_view.scroll_to_pdf_location(
            page,
            x,
            y,
        )

    def show_error(self, message: str) -> None:
        self._last_error = str(message)
        if (
            self._has_success_for_current_source
            and self._current_pdf_path is not None
        ):
            # A partially typed LaTeX command can make one live compile fail.
            # Do not destroy a useful preview that was rendered successfully
            # moments earlier; the next valid generation will replace it.
            self._pdf_view.setToolTip(self._last_error)
            self._stack.setCurrentWidget(self._pdf_view)
            return

        self._message.setText(self._last_error)
        self._stack.setCurrentWidget(
            self._message
        )

    def show_message(self, message: str) -> None:
        self._message.setText(message)
        self._stack.setCurrentWidget(
            self._message
        )
