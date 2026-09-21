"""Persistent exact-text highlighting for selection-only range bookmarks."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)
from nd_mind_mirror.ui.editor.bookmark.range.exact_selection_range_matcher import (
    ExactSelectionRangeMatcher,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_highlighter import (
    RangeBookmarkHighlighter,
)


class SelectionRangeBookmarkHighlighter(RangeBookmarkHighlighter):
    """Paint only exact bookmarked text, never an approximate structural range."""

    def __init__(self, editor) -> None:
        super().__init__(editor)
        self._matcher = ExactSelectionRangeMatcher()

    def _apply_source(self, source: str, bookmarks) -> None:
        editor = self._editor
        selections = self._without_own(editor)

        window_start = 0
        visible_text = str(source)
        if bool(getattr(editor, "source_is_windowed", False)):
            window_start = max(int(getattr(editor, "source_window_start", 0)), 0)
            visible_provider = getattr(editor, "visible_source_text", None)
            if callable(visible_provider):
                visible_text = str(visible_provider())

        for item in bookmarks:
            exact = self._exact_source_range(
                visible_text,
                str(item.text),
                int(item.start_char),
                int(item.end_char),
                window_start,
            )
            if exact is None:
                continue
            selections.append(self._selection(editor, exact[0], exact[1]))

        editor.setExtraSelections(selections)
        editor.viewport().update()

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
            if exact is None:
                continue

            start, end = exact
            if end <= start:
                continue
            selections.append(self._selection(visual, start, end))

        visual.setExtraSelections(selections)
        visual.viewport().update()

    def _exact_source_range(
        self,
        visible_text: str,
        bookmarked_text: str,
        canonical_start: int,
        canonical_end: int,
        window_start: int,
    ) -> tuple[int, int] | None:
        if not bookmarked_text:
            return None

        window_end = int(window_start) + len(visible_text)
        if canonical_end <= window_start or canonical_start >= window_end:
            return None

        rough_start = max(int(canonical_start) - int(window_start), 0)
        rough_end = min(
            max(int(canonical_end) - int(window_start), rough_start),
            len(visible_text),
        )

        if visible_text[rough_start:rough_end] == bookmarked_text:
            return rough_start, rough_end

        return self._matcher.nearest_occurrence(
            visible_text,
            bookmarked_text,
            rough_start,
            rough_end,
        )

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
            match = self._matcher.nearest_occurrence(
                visual_text,
                candidate,
                rough_start,
                rough_end,
            )
            if match is not None:
                return match

        # Never highlight the approximate source projection as a fallback.
        return None
