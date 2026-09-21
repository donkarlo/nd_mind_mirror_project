"""Exact range matching utilities for selection-only bookmarks."""

from __future__ import annotations


class ExactSelectionRangeMatcher:
    """Resolve exact text occurrences near an expected canonical range."""

    _SEARCH_MARGIN_CHARS = 4096

    def nearest_occurrence(
        self,
        text: str,
        needle: str,
        rough_start: int,
        rough_end: int,
    ) -> tuple[int, int] | None:
        if not needle or not needle.strip():
            return None

        left = max(0, int(rough_start) - self._SEARCH_MARGIN_CHARS)
        right = min(
            len(text),
            max(int(rough_start), int(rough_end)) + self._SEARCH_MARGIN_CHARS,
        )
        if right <= left:
            return None

        best_start: int | None = None
        best_score: tuple[int, int] | None = None
        position = text.find(needle, left, right)

        while position >= 0:
            end = position + len(needle)
            overlaps_expected = position < rough_end and rough_start < end
            score = (
                0 if overlaps_expected else 1,
                abs(position - int(rough_start)),
            )
            if best_score is None or score < best_score:
                best_score = score
                best_start = position
            position = text.find(needle, position + 1, right)

        if best_start is None:
            return None
        return best_start, best_start + len(needle)
