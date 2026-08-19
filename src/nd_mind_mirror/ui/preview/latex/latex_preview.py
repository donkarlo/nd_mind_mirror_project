from pathlib import Path

from PySide6.QtCore import Qt
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
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setMinimumWidth(0)
        self._current_pdf_path: Path | None = None
        self._source_document_path: Path | None = None
        self._reset_position_on_next_pdf = True

        self._pdf_view = SelectablePdfView(self)
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

    def set_source_document(
        self,
        path: str | Path,
    ) -> None:
        source_path = Path(path).expanduser().resolve()
        if source_path == self._source_document_path:
            return

        self._source_document_path = source_path
        self._reset_position_on_next_pdf = True

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

        self._reset_position_on_next_pdf = False
        self._current_pdf_path = pdf_path
        self._stack.setCurrentWidget(
            self._pdf_view
        )

    def show_error(self, message: str) -> None:
        self._message.setText(message)
        self._stack.setCurrentWidget(
            self._message
        )

    def show_message(self, message: str) -> None:
        self._message.setText(message)
        self._stack.setCurrentWidget(
            self._message
        )
