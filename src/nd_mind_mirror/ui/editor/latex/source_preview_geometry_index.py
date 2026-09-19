"""Index Source preview overlays by cached document-space geometry."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence


class SourcePreviewGeometryIndex:
    """Return preview indices intersecting a viewport without querying QTextDocument."""

    def __init__(self) -> None:
        """Initialize an empty geometry index."""
        self.clear()

    def clear(self) -> None:
        """Discard all cached preview geometry."""
        self._tops: list[int] = []
        self._indices: list[int] = []
        self._max_height = 0

    def rebuild(
        self,
        geometry: Sequence[tuple[int, int, int]],
    ) -> None:
        """Index ``(item_index, document_top, height)`` tuples by document top."""
        ordered = sorted(
            (
                (int(document_top), int(item_index), max(int(height), 1))
                for item_index, document_top, height in geometry
            ),
            key=lambda item: item[0],
        )
        self._tops = [item[0] for item in ordered]
        self._indices = [item[1] for item in ordered]
        self._max_height = max((item[2] for item in ordered), default=0)

    def candidate_indices(
        self,
        scroll_value: int,
        viewport_height: int,
    ) -> tuple[int, ...]:
        """Return only overlays that can intersect the current vertical viewport."""
        if not self._tops:
            return ()

        top = int(scroll_value)
        bottom = top + max(int(viewport_height), 0)
        lower = top - self._max_height
        start = bisect_left(self._tops, lower)
        stop = bisect_right(self._tops, bottom)
        return tuple(self._indices[start:stop])
