"""Window large generic text files so Qt never lays out the whole source at once."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QTextCursor

if TYPE_CHECKING:
    from nd_mind_mirror.core.settings.yaml.yaml_settings import YamlSettings
    from nd_mind_mirror.ui.editor.generic.generic_text_editor import GenericTextEditor


class LargeTextDocumentController(QObject):
    """Keep canonical text complete while exposing only a bounded editor window."""

    def __init__(
        self,
        editor: "GenericTextEditor",
        app_settings: "YamlSettings",
    ) -> None:
        super().__init__(editor)
        self._editor = editor
        self._full_source = ""
        self._active = False
        self._loading_window = False
        self._window_start_line = 1
        self._window_end_line = 1
        self._window_start_offset = 0
        self._window_end_offset = 0
        self._visible_text = ""
        self._total_lines = 1

        self._threshold_chars = 120_000
        self._pages_above = 4
        self._pages_below = 4
        self._estimated_chars_per_page = 2_400
        self._max_lines_per_page = 45
        self._rewindow_delay_ms = 90
        self._scroll_edge_ratio = 0.14

        self._rewindow_timer = QTimer(self)
        self._rewindow_timer.setSingleShot(True)
        self._rewindow_timer.timeout.connect(self._rewindow_from_scroll)

        self.apply_settings(app_settings)
        self._editor.textChanged.connect(self._synchronize_visible_text)
        self._editor.verticalScrollBar().valueChanged.connect(
            self._schedule_rewindow
        )

    @property
    def active(self) -> bool:
        return self._active

    @property
    def full_source(self) -> str:
        return self._full_source

    def apply_settings(self, app_settings: "YamlSettings") -> None:
        self._threshold_chars = self._setting_int(
            app_settings,
            "source_large_document_threshold_chars",
            120_000,
            1_000,
            100_000_000,
        )
        self._pages_above = self._setting_int(
            app_settings,
            "visual_window_pages_above",
            4,
            0,
            100,
        )
        self._pages_below = self._setting_int(
            app_settings,
            "visual_window_pages_below",
            4,
            0,
            100,
        )
        self._estimated_chars_per_page = self._setting_int(
            app_settings,
            "visual_window_estimated_chars_per_page",
            2_400,
            200,
            20_000,
        )
        self._max_lines_per_page = self._setting_int(
            app_settings,
            "visual_window_max_lines_per_page",
            45,
            1,
            2_000,
        )
        self._rewindow_delay_ms = self._setting_int(
            app_settings,
            "visual_window_rewindow_delay_ms",
            90,
            10,
            2_000,
        )
        self._scroll_edge_ratio = self._setting_float(
            app_settings,
            "visual_window_scroll_edge_ratio",
            0.14,
            0.01,
            0.45,
        )
        self._rewindow_timer.setInterval(self._rewindow_delay_ms)

    def set_content(self, content: str) -> bool:
        """Adopt content and return True when the editor should stay virtualized."""
        source = str(content)
        if len(source) < self._threshold_chars:
            self._deactivate()
            return False

        focus_line = self.current_global_line() if self._active else 1
        cursor_global_offset = (
            self._window_start_offset + int(self._editor.textCursor().position())
            if self._active
            else 0
        )
        self._full_source = source
        self._total_lines = max(source.count("\n") + 1, 1)
        self._active = True
        self._load_window(
            focus_line=focus_line,
            preserve_modified=False,
            cursor_global_offset=cursor_global_offset,
        )
        return True

    def view_state(self) -> dict[str, int]:
        if not self._active:
            return {}
        cursor = self._editor.textCursor()
        return {
            "cursor": max(
                self._window_start_offset + int(cursor.position()),
                0,
            ),
            "vertical": int(self._editor.verticalScrollBar().value()),
            "horizontal": int(self._editor.horizontalScrollBar().value()),
        }

    def restore_view_state(self, state: dict | None) -> bool:
        if not self._active or not isinstance(state, dict):
            return False
        try:
            position = max(int(state.get("cursor", 0)), 0)
            horizontal = int(state.get("horizontal", 0))
        except (TypeError, ValueError):
            return True

        line, _column = self._location_for_offset(position)
        self._load_window(
            focus_line=line,
            preserve_modified=True,
            cursor_global_offset=position,
        )
        self._editor.horizontalScrollBar().setValue(horizontal)
        return True

    def go_to_line(self, line_number: int, align_top: bool = True) -> bool:
        if not self._active:
            return False
        line = max(1, min(int(line_number), self._total_lines))
        if not self._line_is_loaded(line):
            self._load_window(
                focus_line=line,
                preserve_modified=True,
            )
        local_line = max(line - self._window_start_line, 0)
        block = self._editor.document().findBlockByNumber(local_line)
        if not block.isValid():
            return True
        cursor = QTextCursor(block)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()
        if align_top:
            rectangle = self._editor.cursorRect(cursor)
            scrollbar = self._editor.verticalScrollBar()
            scrollbar.setValue(scrollbar.value() + rectangle.top())
        self._editor.setFocus()
        return True

    def first_visible_source_position(self) -> tuple[int, int] | None:
        if not self._active:
            return None
        cursor = self._editor.cursorForPosition(QPoint(2, 2))
        return (
            self._window_start_line + max(cursor.blockNumber(), 0),
            max(cursor.positionInBlock() + 1, 1),
        )

    def current_global_line(self) -> int:
        if not self._active:
            return max(self._editor.textCursor().blockNumber() + 1, 1)
        return self._window_start_line + max(
            self._editor.textCursor().blockNumber(),
            0,
        )

    def visible_search_ranges(
        self,
        ranges: list[tuple[int, int]],
        current_index: int,
    ) -> tuple[list[tuple[int, int]], int]:
        if not self._active:
            return ranges, int(current_index)
        visible: list[tuple[int, int]] = []
        visible_current_index = -1
        for index, (start, end) in enumerate(ranges):
            clipped_start = max(int(start), self._window_start_offset)
            clipped_end = min(int(end), self._window_end_offset)
            if clipped_end <= clipped_start:
                continue
            if index == int(current_index):
                visible_current_index = len(visible)
            visible.append(
                (
                    clipped_start - self._window_start_offset,
                    clipped_end - self._window_start_offset,
                )
            )
        return visible, visible_current_index

    def _deactivate(self) -> None:
        self._rewindow_timer.stop()
        self._active = False
        self._loading_window = False
        self._full_source = ""
        self._window_start_line = 1
        self._window_end_line = 1
        self._window_start_offset = 0
        self._window_end_offset = 0
        self._visible_text = ""
        self._total_lines = 1

    def _synchronize_visible_text(self) -> None:
        if not self._active or self._loading_window:
            return
        visible = self._editor.document().toPlainText()
        old_visible = self._visible_text
        self._full_source = (
            self._full_source[: self._window_start_offset]
            + visible
            + self._full_source[self._window_end_offset :]
        )
        newline_delta = visible.count("\n") - old_visible.count("\n")
        self._total_lines = max(self._total_lines + newline_delta, 1)
        self._visible_text = visible
        self._window_end_offset = self._window_start_offset + len(visible)
        self._window_end_line = (
            self._window_start_line + visible.count("\n")
        )

    def _schedule_rewindow(self, _value: int) -> None:
        if not self._active or self._loading_window:
            return
        scrollbar = self._editor.verticalScrollBar()
        maximum = max(int(scrollbar.maximum()), 0)
        if maximum <= 0:
            return
        ratio = float(scrollbar.value()) / float(maximum)
        if (
            ratio <= self._scroll_edge_ratio
            and self._window_start_line > 1
        ) or (
            ratio >= 1.0 - self._scroll_edge_ratio
            and self._window_end_line < self._total_lines
        ):
            self._rewindow_timer.start()

    def _rewindow_from_scroll(self) -> None:
        if not self._active or self._loading_window:
            return
        scrollbar = self._editor.verticalScrollBar()
        maximum = max(int(scrollbar.maximum()), 0)
        if maximum <= 0:
            return
        ratio = float(scrollbar.value()) / float(maximum)
        window_span = max(
            self._window_end_line - self._window_start_line + 1,
            1,
        )
        step = max(window_span // 2, 1)
        if (
            ratio >= 1.0 - self._scroll_edge_ratio
            and self._window_end_line < self._total_lines
        ):
            focus_line = min(self._window_end_line + step, self._total_lines)
        elif (
            ratio <= self._scroll_edge_ratio
            and self._window_start_line > 1
        ):
            focus_line = max(self._window_start_line - step, 1)
        else:
            return

        cursor = self._editor.textCursor()
        global_cursor = self._window_start_offset + int(cursor.position())
        self._load_window(
            focus_line=focus_line,
            preserve_modified=True,
            cursor_global_offset=global_cursor,
        )

    def _load_window(
        self,
        *,
        focus_line: int,
        preserve_modified: bool,
        cursor_global_offset: int | None = None,
    ) -> None:
        lines = self._logical_lines(self._full_source)
        focus_index = max(0, min(int(focus_line) - 1, len(lines) - 1))
        start, end = self._window_bounds(lines, focus_index)
        before = "".join(lines[:start])
        visible = "".join(lines[start:end])

        modified = (
            self._editor.document().isModified()
            if preserve_modified
            else False
        )
        if cursor_global_offset is None:
            cursor_global_offset = len(before)

        self._loading_window = True
        signals_were_blocked = self._editor.signalsBlocked()
        self._editor.blockSignals(True)
        try:
            self._window_start_line = start + 1
            self._window_end_line = max(end, start + 1)
            self._window_start_offset = len(before)
            self._window_end_offset = self._window_start_offset + len(visible)
            self._visible_text = visible
            self._total_lines = max(len(lines), 1)

            self._editor.setPlainText(visible)
            self._editor.apply_line_height(self._editor._line_height_percent)
            self._editor.document().setModified(modified)

            local_cursor = max(
                0,
                min(
                    int(cursor_global_offset) - self._window_start_offset,
                    max(self._editor.document().characterCount() - 1, 0),
                ),
            )
            cursor = self._editor.textCursor()
            cursor.setPosition(local_cursor)
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()
        finally:
            self._editor.blockSignals(signals_were_blocked)
            self._loading_window = False

    def _window_bounds(
        self,
        lines: list[str],
        focus_index: int,
    ) -> tuple[int, int]:
        count = len(lines)
        if count <= 0:
            return 0, 0
        focus = max(0, min(int(focus_index), count - 1))
        start = focus
        end = min(focus + 1, count)

        target_above_chars = self._pages_above * self._estimated_chars_per_page
        target_above_lines = self._pages_above * self._max_lines_per_page
        consumed_chars = 0
        consumed_lines = 0
        while (
            start > 0
            and consumed_chars < target_above_chars
            and consumed_lines < target_above_lines
        ):
            start -= 1
            consumed_chars += len(lines[start])
            consumed_lines += 1

        target_below_chars = self._pages_below * self._estimated_chars_per_page
        target_below_lines = self._pages_below * self._max_lines_per_page
        consumed_chars = 0
        consumed_lines = 0
        while (
            end < count
            and consumed_chars < target_below_chars
            and consumed_lines < target_below_lines
        ):
            consumed_chars += len(lines[end])
            consumed_lines += 1
            end += 1

        return max(start, 0), min(max(end, start + 1), count)

    def _line_is_loaded(self, line_number: int) -> bool:
        return self._window_start_line <= line_number <= self._window_end_line

    def _location_for_offset(self, offset: int) -> tuple[int, int]:
        position = max(0, min(int(offset), len(self._full_source)))
        prefix = self._full_source[:position]
        line = prefix.count("\n") + 1
        last_newline = prefix.rfind("\n")
        column = position + 1 if last_newline < 0 else position - last_newline
        return line, max(column, 1)

    @staticmethod
    def _logical_lines(source: str) -> list[str]:
        lines = source.splitlines(keepends=True)
        if not lines:
            return [""]
        if source.endswith(("\n", "\r")):
            lines.append("")
        return lines

    @staticmethod
    def _setting_int(
        app_settings: "YamlSettings",
        key: str,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            value = int(app_settings._get("editor", key, default=default))
        except (AttributeError, TypeError, ValueError):
            value = default
        return max(minimum, min(value, maximum))

    @staticmethod
    def _setting_float(
        app_settings: "YamlSettings",
        key: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        try:
            value = float(app_settings._get("editor", key, default=default))
        except (AttributeError, TypeError, ValueError):
            value = default
        return max(minimum, min(value, maximum))
