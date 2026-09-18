"""Resolve only explicit text selections to canonical bookmark ranges."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)


class RangeBookmarkSelectionResolver:
    """Map an explicit Source/Visual text selection to one canonical range."""

    _SEARCH_MARGIN_CHARS = 4096
    _MAX_ROUGH_EXPANSION_CHARS = 96

    def resolve(self, editor) -> tuple[int, int] | None:
        """Return the selected canonical half-open range, never a line/block range."""
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
            match = self._nearest_occurrence(
                source,
                candidate,
                rough_start,
                rough_end,
            )
            if match is not None:
                return match

        rough = self._clamp_range(rough_start, rough_end, len(source))
        if rough is None:
            return None

        if self._rough_range_is_safe(
            rough,
            selected_visual,
            candidates,
        ):
            return rough

        # A short Visual selection must never silently become a paragraph,
        # section, or other broad structural bookmark.
        return None

    @staticmethod
    def _selection_candidates(visual, cursor, selected_visual: str) -> tuple[str, ...]:
        values: list[str] = []

        serializer = getattr(visual, "_selected_latex_source", None)
        if callable(serializer):
            try:
                serialized = str(serializer(cursor))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                serialized = ""
            if serialized.strip():
                values.append(serialized)

        if selected_visual.strip():
            values.append(selected_visual)
            collapsed = selected_visual.replace("\n", " ")
            if collapsed != selected_visual:
                values.append(collapsed)

        unique: list[str] = []
        for value in values:
            if value and value not in unique:
                unique.append(value)
        return tuple(unique)

    def _nearest_occurrence(
        self,
        source: str,
        needle: str,
        rough_start: int,
        rough_end: int,
    ) -> tuple[int, int] | None:
        if not needle or not needle.strip():
            return None

        left = max(0, int(rough_start) - self._SEARCH_MARGIN_CHARS)
        right = min(
            len(source),
            max(int(rough_end), int(rough_start)) + self._SEARCH_MARGIN_CHARS,
        )
        if right <= left:
            return None

        best_start: int | None = None
        best_score: tuple[int, int] | None = None
        position = source.find(needle, left, right)
        while position >= 0:
            end = position + len(needle)
            overlap_penalty = 0 if position < rough_end and rough_start < end else 1
            score = (overlap_penalty, abs(position - rough_start))
            if best_score is None or score < best_score:
                best_score = score
                best_start = position
            position = source.find(needle, position + 1, right)

        if best_start is None:
            return None
        return best_start, best_start + len(needle)

    def _rough_range_is_safe(
        self,
        rough: tuple[int, int],
        selected_visual: str,
        candidates: tuple[str, ...],
    ) -> bool:
        start, end = rough
        rough_length = end - start
        expected = max(
            [len(selected_visual)] + [len(value) for value in candidates] + [1]
        )

        # Multi-block selections are allowed to be naturally larger because
        # Visual block separators and canonical newlines are not one-to-one.
        if "\n" in selected_visual:
            return rough_length <= max(expected * 4, expected + 256)

        return rough_length <= max(
            expected * 4,
            self._MAX_ROUGH_EXPANSION_CHARS,
        )

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
