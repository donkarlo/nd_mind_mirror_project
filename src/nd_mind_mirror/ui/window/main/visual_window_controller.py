"""Virtualize large LaTeX Visual documents around the active source location."""

from __future__ import annotations

import re
from types import MethodType
import weakref

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import (
    LatexVisualEditor,
    _BlockMeta,
)


class VisualWindowController:
    """Keep large Visual projections bounded while preserving canonical source mapping."""

    _PAGES_ABOVE = 20
    _PAGES_BELOW = 20
    _ESTIMATED_CHARS_PER_PAGE = 2400
    _MIN_LINES_PER_PAGE = 12
    _MAX_LINES_PER_PAGE = 45
    _MIN_VIRTUAL_SOURCE_CHARS = 120_000
    _MIN_VIRTUAL_BODY_LINES = 1_800
    _SCROLL_EDGE_RATIO = 0.14
    _SCROLL_REWINDOW_DELAY_MS = 90

    def __init__(self, editor_panel, parent=None) -> None:
        """Attach virtualization to current and subsequently selected LaTeX editors."""
        self._editor_panel = editor_panel
        self._states: dict[int, dict[str, object]] = {}

        for signal_name in (
            "current_document_changed",
            "current_view_changed",
        ):
            signal = getattr(editor_panel, signal_name, None)
            if signal is not None:
                signal.connect(lambda *_args: self._bind_current_editor())

        QTimer.singleShot(0, self._bind_current_editor)

    def _bind_current_editor(self) -> None:
        """Patch the active LaTeX Visual editor before it next loads source."""
        current_editor = getattr(self._editor_panel, "current_editor", None)
        if not callable(current_editor):
            return
        editor = current_editor()
        if not isinstance(editor, LatexEditor):
            return
        self._bind_visual_editor(editor._visual_editor)

    def _bind_visual_editor(self, visual: LatexVisualEditor) -> None:
        """Wrap one Visual editor once and keep its original methods for delegation."""
        identity = id(visual)
        if identity in self._states:
            return

        scroll_timer = QTimer(visual)
        scroll_timer.setSingleShot(True)
        scroll_timer.setInterval(self._SCROLL_REWINDOW_DELAY_MS)
        visual_ref = weakref.ref(visual)
        scroll_timer.timeout.connect(
            lambda ref=visual_ref: self._shift_window_from_scroll(ref)
        )

        state: dict[str, object] = {
            "visual_ref": visual_ref,
            "original_load_source": visual.load_source,
            "original_serialized_source": visual.serialized_source,
            "original_go_to_source_location": visual.go_to_source_location,
            "original_set_selection": visual.set_selection_from_source_locations,
            "original_marker_y": visual.marker_y_for_source_location,
            "full_source": "",
            "source_path": None,
            "virtualized": False,
            "body_start_line": 1,
            "body_last_line": 1,
            "window_start_line": 1,
            "window_end_line": 1,
            "window_start_index": 0,
            "window_end_index": 0,
            "window_leading_newlines": "",
            "window_trailing_newlines": "",
            "before": "",
            "after": "",
            "rewindowing": False,
            "scroll_timer": scroll_timer,
        }
        self._states[identity] = state

        visual.load_source = MethodType(
            lambda widget, source, source_path=None:
            self._load_source(widget, source, source_path),
            visual,
        )
        visual.serialized_source = MethodType(
            lambda widget: self._serialized_source(widget),
            visual,
        )
        visual.go_to_source_location = MethodType(
            lambda widget, line_number, column=1, align_top=True:
            self._go_to_source_location(widget, line_number, column, align_top),
            visual,
        )
        visual.set_selection_from_source_locations = MethodType(
            lambda widget, anchor, position, ensure_visible=True:
            self._set_selection_from_source_locations(
                widget,
                anchor,
                position,
                ensure_visible=ensure_visible,
            ),
            visual,
        )
        visual.marker_y_for_source_location = MethodType(
            lambda widget, line_number, column=1:
            self._marker_y_for_source_location(widget, line_number, column),
            visual,
        )

        visual.verticalScrollBar().valueChanged.connect(
            lambda _value, ref=visual_ref: self._schedule_scroll_rewindow(ref)
        )
        visual.source_changed.connect(
            lambda source, ref=visual_ref: self._remember_emitted_source(ref, source)
        )
        visual.destroyed.connect(
            lambda _obj=None, value=identity: self._states.pop(value, None)
        )

    def _state(self, visual: LatexVisualEditor) -> dict[str, object] | None:
        """Return the virtualization state associated with one Visual editor."""
        return self._states.get(id(visual))

    def _load_source(
        self,
        visual: LatexVisualEditor,
        source: str,
        source_path=None,
    ) -> None:
        """Load full source normally or a cursor-centered window when it is large."""
        state = self._state(visual)
        if state is None:
            return
        focus_line = self._preferred_focus_line(visual, state)
        self._load_window(
            visual,
            state,
            str(source),
            source_path,
            focus_line=focus_line,
        )

    def _load_window(
        self,
        visual: LatexVisualEditor,
        state: dict[str, object],
        source: str,
        source_path,
        *,
        focus_line: int,
    ) -> None:
        """Render either all source or a safe body slice centered on a source line."""
        original_load = state["original_load_source"]
        assert callable(original_load)

        prefix, body, suffix = visual._split_document(source)
        body_lines = body.splitlines(keepends=True)
        body_start_line = prefix.count("\n") + 1
        body_last_line = body_start_line + max(len(body_lines) - 1, 0)

        state["full_source"] = source
        state["source_path"] = source_path if source_path is not None else state["source_path"]
        state["body_start_line"] = body_start_line
        state["body_last_line"] = body_last_line

        if not self._should_virtualize(source, body_lines):
            state["rewindowing"] = True
            parent = visual.parent()
            previous_cursor_sync = None
            if isinstance(parent, LatexEditor):
                previous_cursor_sync = bool(parent._syncing_cursor_views)
                parent._syncing_cursor_views = True
            try:
                original_load(source, source_path)
            finally:
                if isinstance(parent, LatexEditor) and previous_cursor_sync is not None:
                    parent._syncing_cursor_views = previous_cursor_sync
                state["rewindowing"] = False
            state["virtualized"] = False
            state["window_start_line"] = body_start_line
            state["window_end_line"] = body_last_line
            state["before"] = ""
            state["after"] = ""
            return

        focus_index = max(
            0,
            min(int(focus_line) - body_start_line, max(len(body_lines) - 1, 0)),
        )
        start, end = self._compute_window_bounds(body_lines, focus_index)
        window_body = "".join(body_lines[start:end])

        leading_match = re.match(r"^(?:\r?\n)+", window_body)
        trailing_match = re.search(r"(?:\r?\n)+$", window_body)
        leading_newlines = leading_match.group(0) if leading_match else ""
        trailing_newlines = trailing_match.group(0) if trailing_match else ""

        state["virtualized"] = True
        state["window_start_index"] = start
        state["window_end_index"] = end
        state["window_start_line"] = body_start_line + start
        state["window_end_line"] = body_start_line + max(end - 1, start)
        state["before"] = prefix + "".join(body_lines[:start])
        state["after"] = "".join(body_lines[end:]) + suffix
        state["window_leading_newlines"] = leading_newlines
        state["window_trailing_newlines"] = trailing_newlines

        state["rewindowing"] = True
        parent = visual.parent()
        previous_cursor_sync = None
        if isinstance(parent, LatexEditor):
            previous_cursor_sync = bool(parent._syncing_cursor_views)
            parent._syncing_cursor_views = True
        try:
            original_load(window_body, source_path)
            self._rebase_block_metadata(
                visual,
                int(state["window_start_line"]) - 1,
            )
            visual._source_char_count = len(source)
            visual._update_emit_interval()
            visual.document().setModified(False)
        finally:
            if isinstance(parent, LatexEditor) and previous_cursor_sync is not None:
                parent._syncing_cursor_views = previous_cursor_sync
            state["rewindowing"] = False

    def _serialized_source(self, visual: LatexVisualEditor) -> str:
        """Serialize the loaded Visual window and splice it into untouched full source."""
        state = self._state(visual)
        if state is None:
            return ""
        original_serialized = state["original_serialized_source"]
        assert callable(original_serialized)
        if not bool(state["virtualized"]):
            return str(original_serialized())

        window_source = str(original_serialized())
        leading = str(state["window_leading_newlines"])
        trailing = str(state["window_trailing_newlines"])
        if leading and not window_source.startswith("\n"):
            window_source = leading + window_source
        if trailing and not window_source.endswith("\n"):
            window_source += trailing
        return str(state["before"]) + window_source + str(state["after"])

    def _preferred_focus_line(
        self,
        visual: LatexVisualEditor,
        state: dict[str, object],
    ) -> int:
        """Prefer the active Visual line, otherwise derive focus from canonical Source."""
        if bool(state["virtualized"]) and visual.document().blockCount() > 0:
            try:
                line, _column = visual.current_source_location()
                if self._line_is_loaded(state, line):
                    return int(line)
            except (RuntimeError, AttributeError):
                pass

        parent = visual.parent()
        if isinstance(parent, LatexEditor):
            try:
                line, _column = parent._source_location_for_position(
                    parent.textCursor().position()
                )
                return max(int(line), 1)
            except (RuntimeError, AttributeError):
                pass
        return max(int(state.get("window_start_line", 1)), 1)

    @classmethod
    def _should_virtualize(cls, source: str, body_lines: list[str]) -> bool:
        """Enable bounded rendering only when a source is large enough to benefit."""
        if len(body_lines) <= 1:
            return False
        return (
            len(source) >= cls._MIN_VIRTUAL_SOURCE_CHARS
            and len(body_lines) >= 300
        ) or len(body_lines) >= cls._MIN_VIRTUAL_BODY_LINES

    @classmethod
    def _compute_window_bounds(
        cls,
        body_lines: list[str],
        focus_index: int,
    ) -> tuple[int, int]:
        """Return safe source-line bounds approximating twenty pages on each side."""
        line_count = len(body_lines)
        if line_count == 0:
            return 0, 0
        focus = max(0, min(int(focus_index), line_count - 1))
        average_chars = max(
            sum(len(line) for line in body_lines) / max(line_count, 1),
            1.0,
        )
        lines_per_page = int(cls._ESTIMATED_CHARS_PER_PAGE / average_chars)
        lines_per_page = max(
            cls._MIN_LINES_PER_PAGE,
            min(lines_per_page, cls._MAX_LINES_PER_PAGE),
        )
        start = max(0, focus - cls._PAGES_ABOVE * lines_per_page)
        end = min(
            line_count,
            focus + cls._PAGES_BELOW * lines_per_page + 1,
        )

        start, end = cls._expand_plain_paragraph_bounds(
            body_lines,
            start,
            end,
        )
        start, end = cls._expand_environment_bounds(
            body_lines,
            start,
            end,
        )
        start, end = cls._expand_plain_paragraph_bounds(
            body_lines,
            start,
            end,
        )

        while start < focus and not body_lines[start].strip():
            start += 1
        while end > focus + 1 and not body_lines[end - 1].strip():
            end -= 1
        return max(start, 0), min(max(end, start + 1), line_count)

    @classmethod
    def _expand_plain_paragraph_bounds(
        cls,
        lines: list[str],
        start: int,
        end: int,
    ) -> tuple[int, int]:
        """Avoid slicing through ordinary prose paragraphs."""
        while (
            start > 0
            and start < len(lines)
            and cls._is_plain_prose_line(lines[start])
            and cls._is_plain_prose_line(lines[start - 1])
        ):
            start -= 1
        while (
            end > 0
            and end < len(lines)
            and cls._is_plain_prose_line(lines[end - 1])
            and cls._is_plain_prose_line(lines[end])
        ):
            end += 1
        return start, end

    @staticmethod
    def _is_plain_prose_line(line: str) -> bool:
        """Return whether a line is ordinary prose rather than a LaTeX directive."""
        stripped = str(line).strip()
        return bool(stripped) and not stripped.startswith(("\\", "%"))

    @classmethod
    def _expand_environment_bounds(
        cls,
        lines: list[str],
        start: int,
        end: int,
    ) -> tuple[int, int]:
        """Expand a window so begin/end LaTeX environments are never cut in half."""
        spans = cls._environment_spans(lines)
        changed = True
        while changed:
            changed = False
            for span_start, span_end in spans:
                if span_start < start < span_end:
                    start = span_start
                    changed = True
                if span_start < end < span_end:
                    end = span_end
                    changed = True
        return start, end

    @staticmethod
    def _environment_spans(lines: list[str]) -> list[tuple[int, int]]:
        """Return matched non-document environment spans as half-open line ranges."""
        stack: list[tuple[str, int]] = []
        spans: list[tuple[int, int]] = []
        token_pattern = re.compile(r"\\(begin|end)\s*\{([^}]+)\}")
        for index, line in enumerate(lines):
            if str(line).lstrip().startswith("%"):
                continue
            for match in token_pattern.finditer(str(line)):
                operation, environment = match.group(1), match.group(2).strip()
                if environment == "document":
                    continue
                if operation == "begin":
                    stack.append((environment, index))
                    continue
                for stack_index in range(len(stack) - 1, -1, -1):
                    open_environment, open_index = stack[stack_index]
                    if open_environment != environment:
                        continue
                    del stack[stack_index:]
                    spans.append((open_index, index + 1))
                    break
        return spans

    @staticmethod
    def _rebase_block_metadata(visual: LatexVisualEditor, line_delta: int) -> None:
        """Translate window-relative block metadata back to absolute source lines."""
        delta = max(int(line_delta), 0)
        if delta == 0:
            return
        block = visual.document().firstBlock()
        while block.isValid():
            data = block.userData()
            if isinstance(data, _BlockMeta):
                if data.source_line > 0:
                    data.source_line += delta
                if data.source_segments:
                    data.source_segments = [
                        (int(line) + delta, text)
                        for line, text in data.source_segments
                    ]
            block = block.next()

    def _go_to_source_location(
        self,
        visual: LatexVisualEditor,
        line_number: int,
        column: int,
        align_top: bool,
    ) -> None:
        """Recenter a virtual window before navigating to an unloaded source line."""
        state = self._state(visual)
        if state is None:
            return
        self._ensure_line_loaded(visual, state, int(line_number))
        original = state["original_go_to_source_location"]
        assert callable(original)
        original(line_number, column, align_top=align_top)

    def _set_selection_from_source_locations(
        self,
        visual: LatexVisualEditor,
        anchor: tuple[int, int],
        position: tuple[int, int],
        *,
        ensure_visible: bool,
    ) -> None:
        """Ensure a selection target is loaded before delegating source-to-Visual mapping."""
        state = self._state(visual)
        if state is None:
            return
        target_line = int(position[0])
        self._ensure_line_loaded(visual, state, target_line)
        original = state["original_set_selection"]
        assert callable(original)
        original(anchor, position, ensure_visible=ensure_visible)

    def _marker_y_for_source_location(
        self,
        visual: LatexVisualEditor,
        line_number: int,
        column: int,
    ) -> float | None:
        """Hide bookmark markers whose source line is outside the loaded Visual window."""
        state = self._state(visual)
        if state is None:
            return None
        if bool(state["virtualized"]) and not self._line_is_loaded(state, line_number):
            return None
        original = state["original_marker_y"]
        assert callable(original)
        return original(line_number, column)

    def _ensure_line_loaded(
        self,
        visual: LatexVisualEditor,
        state: dict[str, object],
        line_number: int,
    ) -> None:
        """Synchronously recenter the Visual window when navigation targets unloaded text."""
        if not bool(state["virtualized"]) or self._line_is_loaded(state, line_number):
            return
        source = self._current_full_source(visual, state)
        self._load_window(
            visual,
            state,
            source,
            state["source_path"],
            focus_line=max(int(line_number), 1),
        )

    @staticmethod
    def _line_is_loaded(state: dict[str, object], line_number: int) -> bool:
        """Return whether an absolute source line belongs to the active Visual window."""
        return (
            int(state["window_start_line"])
            <= int(line_number)
            <= int(state["window_end_line"])
        )

    def _schedule_scroll_rewindow(
        self,
        visual_ref: weakref.ReferenceType,
    ) -> None:
        """Debounce window shifting when scrolling approaches either loaded edge."""
        visual = visual_ref()
        if visual is None:
            return
        state = self._state(visual)
        if state is None or not bool(state["virtualized"]) or bool(state["rewindowing"]):
            return

        bar = visual.verticalScrollBar()
        maximum = int(bar.maximum())
        if maximum <= 0:
            return
        ratio = float(bar.value()) / float(maximum)
        can_go_up = int(state["window_start_line"]) > int(state["body_start_line"])
        can_go_down = int(state["window_end_line"]) < int(state["body_last_line"])
        near_edge = (
            (ratio <= self._SCROLL_EDGE_RATIO and can_go_up)
            or (ratio >= 1.0 - self._SCROLL_EDGE_RATIO and can_go_down)
        )
        if not near_edge:
            return
        timer = state["scroll_timer"]
        assert isinstance(timer, QTimer)
        timer.start()

    def _shift_window_from_scroll(
        self,
        visual_ref: weakref.ReferenceType,
    ) -> None:
        """Recenter a large Visual window while keeping the viewport anchor stationary."""
        visual = visual_ref()
        if visual is None:
            return
        state = self._state(visual)
        if state is None or not bool(state["virtualized"]) or bool(state["rewindowing"]):
            return
        if visual._emit_timer.isActive():
            timer = state["scroll_timer"]
            assert isinstance(timer, QTimer)
            timer.start(max(self._SCROLL_REWINDOW_DELAY_MS, visual._emit_timer.interval() + 20))
            return

        anchor_y = max(8, visual.viewport().height() // 2)
        anchor_location = visual.source_location_at_view_y(anchor_y)
        selection = visual.source_selection_locations()
        source = self._current_full_source(visual, state)

        prefix, body, _suffix = visual._split_document(source)
        body_lines = body.splitlines(keepends=True)
        if not body_lines:
            return
        focus_index = max(
            0,
            min(
                int(anchor_location[0]) - (prefix.count("\n") + 1),
                len(body_lines) - 1,
            ),
        )
        start, end = self._compute_window_bounds(body_lines, focus_index)
        if (
            start == int(state["window_start_index"])
            and end == int(state["window_end_index"])
        ):
            return

        self._load_window(
            visual,
            state,
            source,
            state["source_path"],
            focus_line=int(anchor_location[0]),
        )

        anchor_line, anchor_column = anchor_location
        if self._selection_is_loaded(state, selection):
            original_set = state["original_set_selection"]
            assert callable(original_set)
            original_set(selection[0], selection[1], ensure_visible=False)

        self._restore_viewport_anchor(
            visual,
            state,
            anchor_line,
            anchor_column,
            anchor_y,
        )
        visual_ref_again = weakref.ref(visual)
        QTimer.singleShot(
            0,
            lambda ref=visual_ref_again, line=anchor_line, column=anchor_column, y=anchor_y:
            self._restore_viewport_anchor_from_ref(ref, line, column, y),
        )

    def _selection_is_loaded(
        self,
        state: dict[str, object],
        selection: tuple[tuple[int, int], tuple[int, int]],
    ) -> bool:
        """Return whether both endpoints of a source selection remain in the new window."""
        return self._line_is_loaded(state, selection[0][0]) and self._line_is_loaded(
            state,
            selection[1][0],
        )

    def _restore_viewport_anchor_from_ref(
        self,
        visual_ref: weakref.ReferenceType,
        line_number: int,
        column: int,
        anchor_y: int,
    ) -> None:
        """Restore a delayed viewport anchor after QTextDocument finishes layout."""
        visual = visual_ref()
        if visual is None:
            return
        state = self._state(visual)
        if state is None:
            return
        self._restore_viewport_anchor(
            visual,
            state,
            line_number,
            column,
            anchor_y,
        )

    @staticmethod
    def _restore_viewport_anchor(
        visual: LatexVisualEditor,
        state: dict[str, object],
        line_number: int,
        column: int,
        anchor_y: int,
    ) -> None:
        """Keep the same source location at the same viewport Y after recentering."""
        if not (
            int(state["window_start_line"])
            <= int(line_number)
            <= int(state["window_end_line"])
        ):
            return
        position = visual.visual_position_for_source_location(line_number, column)
        cursor = QTextCursor(visual.document())
        cursor.setPosition(max(int(position), 0))
        rectangle = visual.cursorRect(cursor)
        scrollbar = visual.verticalScrollBar()
        scrollbar.setValue(
            scrollbar.value() + rectangle.center().y() - int(anchor_y)
        )

    def _current_full_source(
        self,
        visual: LatexVisualEditor,
        state: dict[str, object],
    ) -> str:
        """Return full source including any already-serialized edits in the loaded window."""
        if bool(state["virtualized"]):
            return self._serialized_source(visual)
        return str(state["full_source"] or visual.serialized_source())

    def _remember_emitted_source(
        self,
        visual_ref: weakref.ReferenceType,
        source: str,
    ) -> None:
        """Remember emitted full source and reconcile it with canonical Source after formatting."""
        visual = visual_ref()
        if visual is None:
            return
        state = self._state(visual)
        if state is None or bool(state["rewindowing"]):
            return
        state["full_source"] = str(source)
        QTimer.singleShot(
            0,
            lambda ref=visual_ref: self._sync_from_parent_source(ref),
        )

    def _sync_from_parent_source(
        self,
        visual_ref: weakref.ReferenceType,
    ) -> None:
        """Refresh cached full source from the canonical LaTeX editor after signal handling."""
        visual = visual_ref()
        if visual is None:
            return
        state = self._state(visual)
        if state is None:
            return
        parent = visual.parent()
        if not isinstance(parent, LatexEditor):
            return
        canonical = parent.toPlainText()
        state["full_source"] = canonical
        if not bool(state["virtualized"]):
            return

        prefix, body, suffix = visual._split_document(canonical)
        body_lines = body.splitlines(keepends=True)
        start = int(state["window_start_index"])
        end = int(state["window_end_index"])
        if 0 <= start < end <= len(body_lines):
            state["before"] = prefix + "".join(body_lines[:start])
            state["after"] = "".join(body_lines[end:]) + suffix
            body_start_line = prefix.count("\n") + 1
            state["body_start_line"] = body_start_line
            state["body_last_line"] = body_start_line + max(len(body_lines) - 1, 0)
            state["window_start_line"] = body_start_line + start
            state["window_end_line"] = body_start_line + end - 1
