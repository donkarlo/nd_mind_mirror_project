"""Convert canonical character offsets to line/column source locations."""

from __future__ import annotations

from bisect import bisect_right


class RangeBookmarkPositionMapper:
    """Map zero-based source character offsets to one-based line/column pairs."""

    def __init__(self, source: str) -> None:
        self._source = str(source)
        self._line_starts = [0]
        for index, char in enumerate(self._source):
            if char == "\n":
                self._line_starts.append(index + 1)

    def location_for_offset(self, offset: int) -> tuple[int, int]:
        value = max(0, min(int(offset), len(self._source)))
        line_index = max(bisect_right(self._line_starts, value) - 1, 0)
        line_start = self._line_starts[line_index]
        return line_index + 1, value - line_start + 1

    def offset_for_location(self, location: tuple[int, int]) -> int:
        line, column = int(location[0]), int(location[1])
        line_index = max(0, min(line - 1, len(self._line_starts) - 1))
        start = self._line_starts[line_index]
        if line_index + 1 < len(self._line_starts):
            line_end = self._line_starts[line_index + 1] - 1
        else:
            line_end = len(self._source)
        return max(start, min(start + max(column - 1, 0), line_end))

    def line_start_offset(self, line_number: int) -> int:
        index = max(0, min(int(line_number) - 1, len(self._line_starts) - 1))
        return self._line_starts[index]

    def line_end_offset(self, line_number: int) -> int:
        index = max(0, min(int(line_number) - 1, len(self._line_starts) - 1))
        if index + 1 < len(self._line_starts):
            return self._line_starts[index + 1] - 1
        return len(self._source)
