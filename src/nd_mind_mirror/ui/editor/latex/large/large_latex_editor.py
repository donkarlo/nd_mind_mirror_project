"""Large LaTeX editor with canonical-buffer-safe structural source replacement."""

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
    """Edit a large Source document through one canonical chunk buffer."""

    _DEFAULT_SOURCE_WINDOW_CHARS = 40_000
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
            max(threshold, 10_000),
            window_chars,
        )
        self._source_materialization_stale = False

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

    def set_edit_mode(self, mode: str) -> None:
        """Materialize canonical Source only when Visual is actually left."""
        requested = "visual" if str(mode).strip().lower() == "visual" else "source"
        if requested == "source" and self._edit_mode == "visual":
            self._visual_editor.flush_pending_source_change()
            if self._source_materialization_stale:
                if self._source_buffer.is_windowed:
                    self._load_visible_window(canonical_modified=True)
                else:
                    self._load_complete_source(canonical_modified=True)

        super().set_edit_mode(requested)

    def apply_structural_source(self, source: str, line_number: int) -> None:
        """Apply a Structure drag/drop rewrite to the complete canonical buffer."""
        canonical_source = str(source)
        if canonical_source == self.toPlainText():
            return

        target_line = max(int(line_number), 1)
        self._source_buffer.set_source(canonical_source, focus_position=0)
        target_position = self._source_buffer.full_position_for_location(
            target_line,
            1,
        )
        self._source_buffer.select_around_position(target_position)
        self._change_generation += 1
        self._canonical_modified = True
        if self._source_buffer.is_windowed:
            self._load_visible_window(canonical_modified=True)
        else:
            self._load_complete_source(canonical_modified=True)

        self._visual_dirty = True
        if self._edit_mode == "visual":
            self._refresh_visual_projection()
        self.content_changed.emit(canonical_source)
        self.modification_changed.emit(True)
        self.go_to_source_location(target_line, 1, align_top=True)

    def _apply_visual_source(self, source: str) -> None:
        """Commit Visual output without rebuilding the full canonical buffer."""
        if self._syncing_from_visual:
            return

        canonical_source = str(source)
        _visual_anchor, visual_position = (
            self._visual_editor.source_selection_locations()
        )
        self._syncing_from_visual = True
        self._syncing_cursor_views = True
        try:
            changed = self._source_buffer.replace_source_incrementally(
                canonical_source
            )
            if not changed:
                return
            focus_position = self._source_buffer.full_position_for_location(
                *visual_position
            )
            self._source_buffer.select_around_position(focus_position)
            self._change_generation += 1
            self._canonical_modified = True
            self._source_materialization_stale = True
            self.document().setModified(True)
            self._visual_dirty = False
        finally:
            self._syncing_cursor_views = False
            self._syncing_from_visual = False

        self._schedule_canonical_content_emit()
        self.modification_changed.emit(True)
        if self._edit_mode == "visual":
            self.active_cursor_changed.emit()

    def _schedule_canonical_content_emit(self) -> None:
        """Delay full-document consumers until large-document editing is idle."""
        self._content_emit_timer.setInterval(
            max(
                int(self._source_large_document_debounce_ms),
                self._FULL_DOCUMENT_IDLE_MS,
            )
        )
        self._content_emit_timer.start()

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
        self._source_materialization_stale = False
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
