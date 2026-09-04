from PySide6.QtCore import QPoint, QSignalBlocker
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)
from nd_mind_mirror.ui.editor.latex.large.large_latex_editor_incremental_core import (
    LargeLatexEditor as IncrementalLargeLatexEditor,
)


class LargeLatexEditor(IncrementalLargeLatexEditor):
    """Window large LaTeX sources in QTextEdit with incremental canonical edits.

    QTextEdit provides native paragraph geometry for RTL prose and Source figure
    reservations. The canonical source remains chunked, and only a bounded Source
    window is materialized once the configured large-document threshold is met.
    """

    _DEFAULT_SOURCE_WINDOW_CHARS = 40_000

    def __init__(self, *args, app_settings, **kwargs) -> None:
        super().__init__(*args, app_settings=app_settings, **kwargs)

        threshold = int(
            getattr(
                app_settings,
                "editor_source_large_document_threshold_chars",
                120_000,
            )
        )
        window_chars = int(
            getattr(
                app_settings,
                "editor_source_window_max_chars",
                self._DEFAULT_SOURCE_WINDOW_CHARS,
            )
        )
        self._source_buffer = LatexSourceBuffer(
            max(threshold, 1),
            window_chars,
        )

    def _load_complete_source(
        self,
        canonical_modified: bool | None = None,
    ) -> None:
        modified = (
            self._canonical_modified
            if canonical_modified is None
            else bool(canonical_modified)
        )
        self._replace_materialized_source(
            self._source_buffer.source,
            modified,
        )

    def _load_visible_window(
        self,
        canonical_modified: bool | None = None,
    ) -> None:
        if not self._source_buffer.is_windowed:
            return
        modified = (
            self._canonical_modified
            if canonical_modified is None
            else bool(canonical_modified)
        )
        self._replace_materialized_source(
            self._source_buffer.window_text,
            modified,
        )
        self._visual_dirty = True

    def _replace_materialized_source(
        self,
        source: str,
        modified: bool,
    ) -> None:
        self._source_window_loading = True
        editor_blocker = QSignalBlocker(self)
        document_blocker = QSignalBlocker(self.document())
        try:
            QTextEdit.setPlainText(self, str(source))
            self.apply_line_height(self._line_height_percent)
            self.document().setModified(bool(modified))
        finally:
            del document_blocker
            del editor_blocker
            self._source_window_loading = False

        self._canonical_modified = bool(modified)
        if hasattr(self, "_highlighter"):
            self._highlighter.rehighlight()
        self.viewport().update()

    def go_to_source_location(
        self,
        line_number: int,
        column: int = 1,
        align_top: bool = True,
    ) -> None:
        if self._edit_mode == "visual" or not self.source_is_windowed:
            super().go_to_source_location(
                line_number,
                column,
                align_top=align_top,
            )
            return

        super().go_to_source_location(
            line_number,
            column,
            align_top=False,
        )
        if not align_top:
            return

        self.ensureCursorVisible()
        rectangle = self.cursorRect(self.textCursor())
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + rectangle.top())

    def first_visible_source_position(self) -> tuple[int, int]:
        if self._edit_mode == "visual":
            return self._visual_editor.first_visible_source_position()
        if not self.source_is_windowed:
            return super().first_visible_source_position()

        cursor = self.cursorForPosition(QPoint(2, 2))
        return self._source_location_for_position(cursor.position())
