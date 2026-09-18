"""Persistent exact-text highlighting for selection-only range bookmarks."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_highlighter import (
    RangeBookmarkHighlighter,
)


class SelectionRangeBookmarkHighlighter(RangeBookmarkHighlighter):
    """Prefer the bookmarked text itself over approximate line/column projection."""

    _SEARCH_MARGIN_CHARS = 4096

    def _apply_visual(self, visual, source: str, bookmarks) -> None:
        selections = self._without_own(visual)
        mapper = RangeBookmarkPositionMapper(source)
        visual_text = visual.toPlainText()
        source_window = getattr(visual, "_source_window", None)

        for item in bookmarks:
            start_location = mapper.location_for_offset(item.start_char)
            end_location = mapper.location_for_offset(item.end_char)

            if source_window is not None and bool(
                getattr(source_window, "virtualized", False)
            ):
                first_line = int(getattr(source_window, "window_start_line", 1))
                last_line = int(
                    getattr(source_window, "window_end_line", first_line)
                )
                if end_location[0] < first_line or start_location[0] > last_line:
                    continue

            try:
                approximate_start = visual.visual_position_for_source_location(
                    *start_location
                )
                approximate_end = visual.visual_position_for_source_location(
                    *end_location
                )
            except (AttributeError, RuntimeError, TypeError, ValueError):
                continue

            exact = self._exact_visual_range(
                visual,
                visual_text,
                str(item.text),
                approximate_start,
                approximate_end,
            )
            if exact is not None:
                start, end = exact
            else:
                start, end = sorted(
                    (int(approximate_start), int(approximate_end))
                )

            if end <= start:
                continue
            selections.append(self._selection(visual, start, end))

        visual.setExtraSelections(selections)
        visual.viewport().update()

    def _exact_visual_range(
        self,
        visual,
        visual_text: str,
        source_text: str,
        approximate_start: int,
        approximate_end: int,
    ) -> tuple[int, int] | None:
        if not source_text:
            return None

        display_mapper = getattr(visual, "_mapping_display_text", None)
        candidates: list[str] = []
        if callable(display_mapper):
            try:
                display = str(display_mapper(source_text))
            except (AttributeError, RuntimeError, TypeError, ValueError):
                display = ""
            if display.strip():
                candidates.append(display)

        if source_text.strip() and source_text not in candidates:
            candidates.append(source_text)

        rough_start, rough_end = sorted(
            (int(approximate_start), int(approximate_end))
        )
        for candidate in candidates:
            match = self._nearest_occurrence(
                visual_text,
                candidate,
                rough_start,
                rough_end,
            )
            if match is not None:
                return match
        return None

    def _nearest_occurrence(
        self,
        text: str,
        needle: str,
        rough_start: int,
        rough_end: int,
    ) -> tuple[int, int] | None:
        if not needle or not needle.strip():
            return None

        left = max(0, rough_start - self._SEARCH_MARGIN_CHARS)
        right = min(
            len(text),
            max(rough_start, rough_end) + self._SEARCH_MARGIN_CHARS,
        )
        best_start: int | None = None
        best_score: tuple[int, int] | None = None

        position = text.find(needle, left, right)
        while position >= 0:
            end = position + len(needle)
            overlap_penalty = 0 if position < rough_end and rough_start < end else 1
            score = (overlap_penalty, abs(position - rough_start))
            if best_score is None or score < best_score:
                best_score = score
                best_start = position
            position = text.find(needle, position + 1, right)

        if best_start is None:
            return None
        return best_start, best_start + len(needle)
