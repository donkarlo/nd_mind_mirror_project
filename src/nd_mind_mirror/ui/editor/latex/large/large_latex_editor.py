from PySide6.QtCore import QPoint, QSignalBlocker
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)
from nd_mind_mirror.ui.editor.latex.large.large_latex_editor_incremental_core import (
    LargeLatexEditor as IncrementalLargeLatexEditor,
)
from nd_mind_mirror.ui.editor.latex.large.source_typing_burst_controller import (
    SourceTypingBurstController,
)


class LargeLatexEditor(IncrementalLargeLatexEditor):
    """Edit a bounded rich Source window backed by the complete source buffer.

    QTextEdit is retained only for the small visible Persian/Arabic layout
    window. LatexSourceBuffer remains the canonical complete document and normal
    typing splices edits incrementally without materializing the complete file.
    """

    _DEFAULT_SOURCE_WINDOW_CHARS = 8_000
    _FULL_DOCUMENT_IDLE_MS = 2_000

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

        self._deferred_window_shift_value: int | None = None
        self._typing_burst_controller = SourceTypingBurstController(
            idle_ms=max(
                120,
                min(
                    int(self._source_large_document_debounce_ms),
                    240,
                ),
            ),
            parent=self,
        )
        self._typing_burst_controller.became_idle.connect(
            self._resume_deferred_source_window_shift
        )

    def _synchronize_visible_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        """Update the canonical buffer and mark real character edits as typing."""
        is_character_edit = (
            not self._source_window_loading
            and (
                int(chars_removed) != 0
                or int(chars_added) != 0
            )
        )
        super()._synchronize_visible_change(
            position,
            chars_removed,
            chars_added,
        )
        if is_character_edit:
            self._typing_burst_controller.note_activity()

    def _maybe_shift_source_window(self, value: int) -> None:
        """Never replace the materialized QTextDocument inside a typing burst."""
        if self._typing_burst_controller.is_active:
            self._deferred_window_shift_value = int(value)
            return
        super()._maybe_shift_source_window(value)

    def _apply_pending_source_window_shift(self) -> None:
        """Keep a queued edge shift pending until all ordered key events settle."""
        if self._typing_burst_controller.is_active:
            self._deferred_window_shift_value = int(
                self.verticalScrollBar().value()
            )
            return
        super()._apply_pending_source_window_shift()

    def _resume_deferred_source_window_shift(self) -> None:
        """Resume one pending edge re-window after Source input becomes idle."""
        if self._edit_mode != "source" or not self.source_is_windowed:
            self._deferred_window_shift_value = None
            return

        if int(self._pending_source_window_shift) != 0:
            self._deferred_window_shift_value = None
            super()._apply_pending_source_window_shift()
            return

        value = self._deferred_window_shift_value
        self._deferred_window_shift_value = None
        if value is None:
            value = int(self.verticalScrollBar().value())
        super()._maybe_shift_source_window(int(value))

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
