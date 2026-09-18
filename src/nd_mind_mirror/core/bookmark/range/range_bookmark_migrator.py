"""Normalize persisted bookmarks into canonical character ranges."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark import RangeBookmark
from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)


class RangeBookmarkMigrator:
    """Load new range bookmarks and migrate old selection bookmarks once."""

    def migrate(
        self,
        raw_bookmarks: list[dict[str, object]] | None,
        source: str,
    ) -> list[RangeBookmark]:
        mapper = RangeBookmarkPositionMapper(source)
        result: list[RangeBookmark] = []
        for raw in raw_bookmarks or []:
            if not isinstance(raw, dict):
                continue
            bookmark = self._from_range_dict(raw, source)
            if bookmark is None:
                bookmark = self._from_legacy_selection(raw, source, mapper)
            if bookmark is not None:
                result.append(self._reanchor(bookmark, source))
        result = [item for item in result if item.end_char > item.start_char]
        result.sort(key=lambda item: (item.start_char, item.end_char, item.id))
        return result

    @staticmethod
    def _from_range_dict(
        raw: dict[str, object],
        source: str,
    ) -> RangeBookmark | None:
        if "start_char" not in raw or "end_char" not in raw:
            return None
        try:
            start = max(int(raw["start_char"]), 0)
            end = max(int(raw["end_char"]), start)
        except (TypeError, ValueError):
            return None
        start = min(start, len(source))
        end = min(end, len(source))
        if end <= start:
            return None
        identifier = str(raw.get("id", "")).strip()
        if not identifier:
            return RangeBookmark.create(
                start,
                end,
                source[start:end],
                name=str(raw.get("name", "")),
            )
        return RangeBookmark(
            id=identifier,
            start_char=start,
            end_char=end,
            text=str(raw.get("text", source[start:end])),
            name=str(raw.get("name", "")).strip(),
        )

    @staticmethod
    def _from_legacy_selection(
        raw: dict[str, object],
        source: str,
        mapper: RangeBookmarkPositionMapper,
    ) -> RangeBookmark | None:
        selection = raw.get("selection")
        if not isinstance(selection, dict):
            return None

        anchor = RangeBookmarkMigrator._legacy_location(selection.get("anchor"))
        position = RangeBookmarkMigrator._legacy_location(selection.get("position"))
        if anchor is None or position is None:
            return None

        first = mapper.offset_for_location(anchor)
        second = mapper.offset_for_location(position)
        start, end = sorted((first, second))
        if end <= start:
            return None
        return RangeBookmark.create(
            start,
            end,
            source[start:end],
            name=str(raw.get("name", "")),
        )

    @staticmethod
    def _legacy_location(raw: object) -> tuple[int, int] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return None
        try:
            return max(int(raw[0]), 1), max(int(raw[1]), 1)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _reanchor(bookmark: RangeBookmark, source: str) -> RangeBookmark:
        if source[bookmark.start_char:bookmark.end_char] == bookmark.text:
            return bookmark

        needle = bookmark.text
        if not needle:
            refreshed = bookmark.with_range(
                bookmark.start_char,
                bookmark.end_char,
                source,
            )
            return refreshed or bookmark

        candidates: list[int] = []
        index = source.find(needle)
        while index >= 0:
            candidates.append(index)
            index = source.find(needle, index + 1)

        if not candidates:
            refreshed = bookmark.with_range(
                bookmark.start_char,
                bookmark.end_char,
                source,
            )
            return refreshed or bookmark

        start = min(candidates, key=lambda value: abs(value - bookmark.start_char))
        refreshed = bookmark.with_range(start, start + len(needle), source)
        return refreshed or bookmark
