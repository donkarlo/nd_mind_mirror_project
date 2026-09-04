from __future__ import annotations

from contextlib import contextmanager

from PySide6.QtCore import QPoint, QSignalBlocker, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)
from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class LargeLatexEditor(LatexEditor):
    """Edit large LaTeX sources with incremental canonical-source updates.

    Moderate large files remain fully materialized in QPlainTextEdit.  Only
    genuinely multi-megabyte sources use a bounded source window.  In either
    case QTextDocument.contentsChange is converted into a small chunk edit;
    normal typing never serializes the whole editor window or whole document.
    """

    _DEFAULT_SOURCE_WINDOW_CHARS = 40_000
    _DEFAULT_VIRTUALIZATION_THRESHOLD_CHARS = 5_000_000
    _FULL_DOCUMENT_IDLE_MS = 1_200

    def __init__(self, *args, app_settings, **kwargs) -> None:
        super().__init__(*args, app_settings=app_settings, **kwargs)
        virtualization_threshold = int(
            getattr(
                app_settings,
                "editor_source_virtualization_threshold_chars",
                self._DEFAULT_VIRTUALIZATION_THRESHOLD_CHARS,
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
            max(virtualization_threshold, 120_000),
            window_chars,
        )
        self._source_window_loading = False
        self._source_window_shifting = False
        self._pending_source_window_shift = 0
        self._canonical_modified = False
        self._force_visible_plain_text = False
        self._change_generation = 0

        self.set_large_document_mode(True)
        if hasattr(self, "_highlighter"):
            self._highlighter.set_large_document_mode(True)

        self._source_window_shift_timer = QTimer(self)
        self._source_window_shift_timer.setSingleShot(True)
        self._source_window_shift_timer.setInterval(0)
        self._source_window_shift_timer.timeout.connect(
            self._apply_pending_source_window_shift
        )

        self.document().contentsChange.connect(
            self._synchronize_visible_change
        )
        self.verticalScrollBar().valueChanged.connect(
            self._maybe_shift_source_window
        )

    @property
    def source_is_windowed(self) -> bool:
        return bool(
            hasattr(self, "_source_buffer")
            and self._source_buffer.is_windowed
        )

    @property
    def source_window_start(self) -> int:
        if not hasattr(self, "_source_buffer"):
            return 0
        return self._source_buffer.window_start

    @property
    def visible_line_number_offset(self) -> int:
        if not self.source_is_windowed:
            return 0
        line, _column = self._source_buffer.window_start_location()
        return max(int(line) - 1, 0)

    def canonical_source(self) -> str:
        return self.toPlainText()

    def visible_source_text(self) -> str:
        return super().toPlainText()

    def autosave_snapshot(self) -> tuple[int, tuple[str, ...]]:
        return (
            int(self._change_generation),
            self._source_buffer.snapshot_pieces(),
        )

    def autosave_revision(self) -> int:
        return int(self._change_generation)

    def toPlainText(self) -> str:
        if self._force_visible_plain_text or not hasattr(self, "_source_buffer"):
            return super().toPlainText()
        return self._source_buffer.source

    def set_content(self, content: str) -> None:
        value = str(content)
        if not hasattr(self, "_source_buffer"):
            super().set_content(value)
            return

        self._source_buffer.set_source(value, focus_position=0)
        self._canonical_modified = False
        self._change_generation = 0
        if self._source_buffer.is_windowed:
            self._load_visible_window(canonical_modified=False)
        else:
            self._load_complete_source(canonical_modified=False)

        self._visual_dirty = True
        self.content_changed.emit(value)
        self.modification_changed.emit(False)

    def mark_saved(self) -> None:
        self._canonical_modified = False
        self.document().setModified(False)

    def _emit_content(self) -> None:
        """Materialize the complete source only after typing has gone idle."""
        if not self._syncing_from_visual:
            self._visual_dirty = True
        self._content_emit_timer.setInterval(
            max(
                int(self._source_large_document_debounce_ms),
                self._FULL_DOCUMENT_IDLE_MS,
            )
        )
        self._content_emit_timer.start()

    def _schedule_bookmark_relocation(self) -> None:
        if not self._bookmarks:
            return
        self._bookmark_relocation_timer.setInterval(
            max(
                int(self._source_large_document_debounce_ms),
                self._FULL_DOCUMENT_IDLE_MS,
            )
        )
        self._bookmark_relocation_timer.start()

    def _synchronize_visible_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        if not hasattr(self, "_source_buffer") or self._source_window_loading:
            return
        if int(chars_removed) == 0 and int(chars_added) == 0:
            return

        inserted = self._inserted_document_text(position, chars_added)
        self._source_buffer.apply_edit(
            int(position),
            int(chars_removed),
            inserted,
        )
        self._change_generation += 1
        self._canonical_modified = True
        self._visual_dirty = True

    def _inserted_document_text(self, position: int, chars_added: int) -> str:
        count = max(int(chars_added), 0)
        if count <= 0:
            return ""
        document = self.document()
        limit = max(document.characterCount() - 1, 0)
        start = max(0, min(int(position), limit))
        end = max(start, min(start + count, limit))
        cursor = QTextCursor(document)
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        return (
            cursor.selectedText()
            .replace("\u2029", "\n")
            .replace("\u2028", "\n")
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
        self._source_window_loading = True
        editor_blocker = QSignalBlocker(self)
        document_blocker = QSignalBlocker(self.document())
        try:
            QPlainTextEdit.setPlainText(self, self._source_buffer.source)
            self.apply_line_height(self._line_height_percent)
            self.document().setModified(modified)
        finally:
            del document_blocker
            del editor_blocker
            self._source_window_loading = False
        self._canonical_modified = modified
        if hasattr(self, "_highlighter"):
            self._highlighter.rehighlight()
        self.viewport().update()

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
        self._source_window_loading = True
        editor_blocker = QSignalBlocker(self)
        document_blocker = QSignalBlocker(self.document())
        try:
            QPlainTextEdit.setPlainText(self, self._source_buffer.window_text)
            self.apply_line_height(self._line_height_percent)
            self.document().setModified(modified)
        finally:
            del document_blocker
            del editor_blocker
            self._source_window_loading = False
        self._canonical_modified = modified
        self._visual_dirty = True
        if hasattr(self, "_highlighter"):
            self._highlighter.rehighlight()
        self.viewport().update()

    def _rewindow_around_full_position(self, full_position: int) -> None:
        if not self._source_buffer.is_windowed:
            return
        old_start = self._source_buffer.window_start
        old_end = self._source_buffer.window_end
        self._source_buffer.select_around_position(full_position)
        if (
            old_start != self._source_buffer.window_start
            or old_end != self._source_buffer.window_end
        ):
            self._load_visible_window()

    def _maybe_shift_source_window(self, value: int) -> None:
        if (
            not self.source_is_windowed
            or self._source_window_loading
            or self._source_window_shifting
            or self._edit_mode != "source"
        ):
            return

        scrollbar = self.verticalScrollBar()
        maximum = max(int(scrollbar.maximum()), 0)
        if maximum <= 0:
            return
        edge = max(
            24,
            min(
                int(scrollbar.pageStep()) // 2,
                max(maximum // 8, 24),
            ),
        )

        direction = 0
        if (
            int(value) >= maximum - edge
            and self._source_buffer.has_content_after_window
        ):
            direction = 1
        elif (
            int(value) <= edge
            and self._source_buffer.has_content_before_window
        ):
            direction = -1

        if direction == 0:
            return
        self._pending_source_window_shift = direction
        if not self._source_window_shift_timer.isActive():
            self._source_window_shift_timer.start()

    def _apply_pending_source_window_shift(self) -> None:
        direction = int(self._pending_source_window_shift)
        self._pending_source_window_shift = 0
        if (
            direction == 0
            or not self.source_is_windowed
            or self._edit_mode != "source"
        ):
            return

        self._source_window_shifting = True
        try:
            if not self._source_buffer.shift_window(direction):
                return
            self._load_visible_window()
            scrollbar = self.verticalScrollBar()
            maximum = max(int(scrollbar.maximum()), 0)
            if direction > 0:
                scrollbar.setValue(maximum // 4)
            else:
                scrollbar.setValue((maximum * 3) // 4)
        finally:
            self._source_window_shifting = False

        self.active_view_changed.emit()

    def _source_location_for_position(self, position: int) -> tuple[int, int]:
        if not self.source_is_windowed:
            return super()._source_location_for_position(position)
        full = self._source_buffer.full_position_for_local_position(position)
        return self._source_buffer.location_for_full_position(full)

    def _source_position_for_location(self, location: tuple[int, int]) -> int:
        if not self.source_is_windowed:
            return super()._source_position_for_location(location)
        return self._source_buffer.full_position_for_location(
            int(location[0]),
            int(location[1]),
        )

    def _local_position_for_location(
        self,
        location: tuple[int, int],
    ) -> int | None:
        full = self._source_buffer.full_position_for_location(
            int(location[0]),
            int(location[1]),
        )
        return self._source_buffer.local_position_for_full_position(full)

    def _set_source_selection_from_locations(
        self,
        anchor: tuple[int, int],
        position: tuple[int, int],
    ) -> None:
        if not self.source_is_windowed:
            super()._set_source_selection_from_locations(anchor, position)
            return

        anchor_full = self._source_buffer.full_position_for_location(*anchor)
        position_full = self._source_buffer.full_position_for_location(*position)
        if (
            self._source_buffer.local_position_for_full_position(anchor_full)
            is None
            or self._source_buffer.local_position_for_full_position(position_full)
            is None
        ):
            self._rewindow_around_full_position(position_full)

        local_anchor = self._source_buffer.local_position_for_full_position(
            anchor_full
        )
        local_position = self._source_buffer.local_position_for_full_position(
            position_full
        )
        if local_position is None:
            return
        if local_anchor is None:
            local_anchor = local_position
        cursor = QTextCursor(self.document())
        cursor.setPosition(local_anchor)
        cursor.setPosition(
            local_position,
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.setTextCursor(cursor)

    def go_to_line(self, line_number: int, align_top: bool = True) -> None:
        if not self.source_is_windowed:
            super().go_to_line(line_number, align_top=align_top)
            return
        self.go_to_source_location(line_number, 1, align_top=align_top)

    def go_to_source_location(
        self,
        line_number: int,
        column: int = 1,
        align_top: bool = True,
    ) -> None:
        if self._edit_mode == "visual":
            self._visual_editor.go_to_source_location(
                line_number,
                column,
                align_top=align_top,
            )
            return
        if not self.source_is_windowed:
            super().go_to_source_location(
                line_number,
                column,
                align_top=align_top,
            )
            return

        full = self._source_buffer.full_position_for_location(
            line_number,
            column,
        )
        self._rewindow_around_full_position(full)
        local = self._source_buffer.local_position_for_full_position(full)
        if local is None:
            return
        cursor = QTextCursor(self.document())
        cursor.setPosition(local)
        self.setTextCursor(cursor)
        if align_top:
            self.verticalScrollBar().setValue(
                max(int(cursor.block().firstLineNumber()), 0)
            )
        else:
            self.ensureCursorVisible()
        self.setFocus()
        self.active_cursor_changed.emit()
        self.active_view_changed.emit()

    def first_visible_source_position(self) -> tuple[int, int]:
        if self._edit_mode == "visual":
            return self._visual_editor.first_visible_source_position()
        if not self.source_is_windowed:
            return super().first_visible_source_position()
        block = self.firstVisibleBlock()
        if block.isValid():
            return self._source_location_for_position(block.position())
        cursor = self.cursorForPosition(QPoint(2, 2))
        return self._source_location_for_position(cursor.position())

    def _source_location_at_y(self, y: int) -> tuple[int, int]:
        cursor = self.cursorForPosition(QPoint(24, int(y)))
        line, _column = self._source_location_for_position(cursor.position())
        return max(int(line), 1), 1

    def _source_marker_y_for_location(
        self,
        line_number: int,
        column: int = 1,
    ) -> float | None:
        if not self.source_is_windowed:
            return super()._source_marker_y_for_location(line_number, column)
        local = self._local_position_for_location((line_number, column))
        if local is None:
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(local)
        return float(self.cursorRect(cursor).center().y())

    def view_state(self) -> dict[str, int]:
        if not self.source_is_windowed:
            return super().view_state()
        cursor = self.textCursor()
        full_cursor = self._source_buffer.full_position_for_local_position(
            cursor.position()
        )
        return {
            "cursor": int(full_cursor),
            "vertical": int(self.verticalScrollBar().value()),
            "horizontal": int(self.horizontalScrollBar().value()),
        }

    def restore_view_state(self, state: dict | None) -> None:
        if not self.source_is_windowed:
            super().restore_view_state(state)
            return
        if not isinstance(state, dict):
            return
        try:
            full_cursor = int(state.get("cursor", 0))
            horizontal = int(state.get("horizontal", 0))
        except (TypeError, ValueError):
            return
        self._rewindow_around_full_position(full_cursor)
        local = self._source_buffer.local_position_for_full_position(full_cursor)
        if local is None:
            local = 0
        cursor = QTextCursor(self.document())
        cursor.setPosition(local)
        self.setTextCursor(cursor)
        self.horizontalScrollBar().setValue(horizontal)
        self.ensureCursorVisible()

    def _apply_visual_source(self, source: str) -> None:
        value = str(source)
        if self._syncing_from_visual or value == self._source_buffer.source:
            return

        anchor, position = self._visual_editor.source_selection_locations()
        focus = self._source_buffer.full_position_for_location(*position)
        self._syncing_from_visual = True
        self._syncing_cursor_views = True
        try:
            self._source_buffer.replace_source(value, focus_position=focus)
            self._change_generation += 1
            self._canonical_modified = True
            if self._source_buffer.is_windowed:
                self._load_visible_window(canonical_modified=True)
            else:
                self._load_complete_source(canonical_modified=True)
            self._set_source_selection_from_locations(anchor, position)
            self._visual_dirty = False
        finally:
            self._syncing_cursor_views = False
            self._syncing_from_visual = False
        self.content_changed.emit(self._source_buffer.source)
        self.modification_changed.emit(True)
        if self._edit_mode == "visual":
            self.active_cursor_changed.emit()

    def format_document(self) -> None:
        source = self._source_buffer.source
        formatted = self._formatter.format(source)
        if formatted == source:
            return
        location = self.active_source_location()
        focus = self._source_buffer.full_position_for_location(*location)
        self._source_buffer.replace_source(formatted, focus_position=focus)
        self._change_generation += 1
        self._canonical_modified = True
        if self._source_buffer.is_windowed:
            self._load_visible_window(canonical_modified=True)
        else:
            self._load_complete_source(canonical_modified=True)
        self.content_changed.emit(self._source_buffer.source)
        self.modification_changed.emit(True)

    @contextmanager
    def _visible_plain_text_scope(self):
        previous = self._force_visible_plain_text
        self._force_visible_plain_text = True
        try:
            yield
        finally:
            self._force_visible_plain_text = previous

    def _insert_smart_new_line(self) -> None:
        if not self.source_is_windowed:
            super()._insert_smart_new_line()
            return
        with self._visible_plain_text_scope():
            super()._insert_smart_new_line()

    def _insert_figure(self, relative_image_path: str) -> None:
        if not self.source_is_windowed:
            super()._insert_figure(relative_image_path)
            return
        with self._visible_plain_text_scope():
            super()._insert_figure(relative_image_path)

    def contextMenuEvent(self, event) -> None:
        if not self.source_is_windowed:
            super().contextMenuEvent(event)
            return
        with self._visible_plain_text_scope():
            super().contextMenuEvent(event)
