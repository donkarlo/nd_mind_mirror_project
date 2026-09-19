"""Incremental text buffer for range-bookmark source tracking."""

from __future__ import annotations

from bisect import bisect_right


class RangeBookmarkSourceBuffer:
    """Keep bookmark source synchronized without rebuilding the full string per edit."""

    _CHUNK_CHARS = 16_384

    def __init__(self, source: str = "") -> None:
        self._chunks: list[str] = [""]
        self._offsets: list[int] = [0, 0]
        self._materialized: str | None = ""
        self.set_source(source)

    @property
    def source(self) -> str:
        if self._materialized is None:
            self._materialized = "".join(self._chunks)
        return self._materialized

    @property
    def length(self) -> int:
        return int(self._offsets[-1])

    def set_source(self, source: str) -> None:
        value = str(source)
        self._chunks = self._split(value)
        self._rebuild_offsets()
        self._materialized = value

    def apply_edit(self, position: int, chars_removed: int, inserted_text: str) -> None:
        start = max(0, min(int(position), self.length))
        removed = max(int(chars_removed), 0)
        end = max(start, min(start + removed, self.length))

        start_chunk = self._chunk_index(start)
        end_chunk = self._chunk_index(end - 1) if end > start else start_chunk

        segment_start = self._offsets[start_chunk]
        segment = "".join(self._chunks[start_chunk:end_chunk + 1])
        relative_start = start - segment_start
        relative_end = relative_start + (end - start)
        replacement = (
            segment[:relative_start]
            + str(inserted_text)
            + segment[relative_end:]
        )

        self._chunks[start_chunk:end_chunk + 1] = self._split(replacement)
        if not self._chunks:
            self._chunks = [""]
        self._rebuild_offsets()
        self._materialized = None

    def _chunk_index(self, position: int) -> int:
        if len(self._chunks) == 1:
            return 0
        point = max(0, min(int(position), self.length))
        if point >= self.length:
            return len(self._chunks) - 1
        return max(
            0,
            min(
                bisect_right(self._offsets, point) - 1,
                len(self._chunks) - 1,
            ),
        )

    @classmethod
    def _split(cls, text: str) -> list[str]:
        if not text:
            return [""]
        return [
            text[start:start + cls._CHUNK_CHARS]
            for start in range(0, len(text), cls._CHUNK_CHARS)
        ] or [""]

    def _rebuild_offsets(self) -> None:
        offsets = [0]
        total = 0
        for chunk in self._chunks:
            total += len(chunk)
            offsets.append(total)
        self._offsets = offsets
