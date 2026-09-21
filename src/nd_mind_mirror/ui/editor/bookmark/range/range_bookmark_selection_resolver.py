"""Resolve only explicit text selections to canonical bookmark ranges."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)
from nd_mind_mirror.ui.editor.bookmark.range.exact_selection_range_matcher import (
    ExactSelectionRangeMatcher,
)


class RangeBookmarkSelectionResolver:
    """Map an explicit Source/Visual text selection to one exact canonical range."""

    def __init__(self) -> None:
        self._matcher = ExactSelectionRangeMatcher()

    def resolve(self, editor) -> tuple[int, int] | None:
        """Return only the explicitly selected canonical half-open range."""
        if str(getattr(editor, "_edit_mode", "source")) == "visual":
            return self._resolve_visual(editor)
        return self._resolve_source(editor)

    def _resolve_source(self, editor) -> tuple[int, int] | None:
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return None

        start = int(cursor.selectionStart())
        end = int(cursor.selectionEnd())
        if bool(getattr(editor, "source_is_windowed", False)):
            window_start = max(int(getattr(editor, "source_window_start", 0)), 0)
            start += window_start
            end += window_start

        source = str(editor.toPlainText())
        return self._clamp_range(start, end, len(source))

    def _resolve_visual(self, editor) -> tuple[int, int] | None:
        visual = editor._visual_editor
        cursor = visual.textCursor()
        if not cursor.hasSelection():
            return None

        source = str(editor.toPlainText())
        mapper = RangeBookmarkPositionMapper(source)
        anchor, position = visual.source_selection_locations()
        rough_start, rough_end = sorted(
            (
                mapper.offset_for_location(anchor),
                mapper.offset_for_location(position),
            )
        )

        selected_visual = str(cursor.selectedText()).replace("\u2029", "\n")
        candidates = self._selection_candidates(visual, cursor, selected_visual)

        for candidate in candidates:
            match = self._matcher.nearest_occurrence(
                source,
                candidate,
                rough_start,
                rough_end,
            )
            if match is not None:
                return match

        # Selection-only bookmarks are exact by definition. If Visual cannot
        # map the selected text back to canonical source, reject the bookmark
        # rather than expanding it to a line, paragraph, or structural block.
        return None

    @staticmethod
    def _selection_candidates(visual, cursor, selected_visual: str) -> tuple[str, ...]:
        """Prefer the literal visible selection before any structural serializer.

        Visual serializers are allowed to return a complete LaTeX block for a
        selection.  That is useful for editing, but a bookmark must never widen
        a few selected words into a paragraph/section.  The literal selected
        text therefore wins whenever it exists in canonical source; serialized
        LaTeX is only a final exact fallback for selections whose visible text
        is transformed by Visual rendering.
        """
        values: list[str] = []

        if selected_visual.strip():
            values.append(selected_visual)
            collapsed = selected_visual.replace("\n", " ")
            if collapsed != selected_visual:
                values.append(collapsed)

        serializer = getattr(visual, "_selected_latex_source", None)
        if callable(serializer):
            try:
                serialized = str(serializer(cursor))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                serialized = ""
            if serialized.strip():
                selected_length = len(selected_visual.strip())
                serialized_length = len(serialized.strip())
                maximum_serialized_length = max(
                    selected_length * 3,
                    selected_length + 24,
                )
                if selected_length == 0 or serialized_length <= maximum_serialized_length:
                    values.append(serialized)

        unique: list[str] = []
        for value in values:
            if value and value not in unique:
                unique.append(value)
        return tuple(unique)

    @staticmethod
    def _clamp_range(
        start: int,
        end: int,
        source_length: int,
    ) -> tuple[int, int] | None:
        first, second = sorted((int(start), int(end)))
        first = max(0, min(first, int(source_length)))
        second = max(first, min(second, int(source_length)))
        if second <= first:
            return None
        return first, second
