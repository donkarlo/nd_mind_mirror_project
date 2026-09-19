"""Mutable collection of canonical range bookmarks."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark import RangeBookmark


class RangeBookmarkCollection:
    """Own ordered, non-empty character-range bookmarks for one document."""

    def __init__(self) -> None:
        self._items: list[RangeBookmark] = []

    @property
    def items(self) -> tuple[RangeBookmark, ...]:
        return tuple(self._items)

    def replace(self, items: list[RangeBookmark]) -> None:
        self._items = sorted(
            [item for item in items if item.end_char > item.start_char],
            key=lambda item: (item.start_char, item.end_char, item.id),
        )

    def add(self, start: int, end: int, source: str) -> RangeBookmark | None:
        first, second = sorted((int(start), int(end)))
        first = max(0, min(first, len(source)))
        second = max(first, min(second, len(source)))
        if second <= first:
            return None
        exact = self.for_exact_range(first, second)
        if exact is not None:
            return exact
        item = RangeBookmark.create(first, second, source[first:second])
        self._items.append(item)
        self._items.sort(key=lambda value: (value.start_char, value.end_char, value.id))
        return item

    def remove(self, bookmark_id: str) -> bool:
        before = len(self._items)
        self._items = [item for item in self._items if item.id != str(bookmark_id)]
        return len(self._items) != before

    def clear(self) -> bool:
        changed = bool(self._items)
        self._items.clear()
        return changed

    def by_id(self, bookmark_id: str) -> RangeBookmark | None:
        for item in self._items:
            if item.id == str(bookmark_id):
                return item
        return None

    def at_position(self, position: int) -> RangeBookmark | None:
        point = int(position)
        candidates = [
            item for item in self._items
            if item.start_char <= point < item.end_char
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (item.end_char - item.start_char, item.start_char),
        )

    def overlapping(self, start: int, end: int) -> RangeBookmark | None:
        first, second = sorted((int(start), int(end)))
        candidates = [
            item for item in self._items
            if item.start_char < second and first < item.end_char
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda item: (item.end_char - item.start_char, item.start_char),
        )

    def for_exact_range(self, start: int, end: int) -> RangeBookmark | None:
        first, second = sorted((int(start), int(end)))
        for item in self._items:
            if item.start_char == first and item.end_char == second:
                return item
        return None

    def apply_source_edit(
        self,
        position: int,
        chars_removed: int,
        inserted_text: str,
    ) -> bool:
        changed = False
        updated: list[RangeBookmark] = []
        for item in self._items:
            transformed = item.after_source_edit(
                position,
                chars_removed,
                inserted_text,
            )
            if transformed is None:
                changed = True
                continue
            if transformed != item:
                changed = True
            updated.append(transformed)
        if changed:
            self.replace(updated)
        return changed

    def apply_edit(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
        source_after: str,
    ) -> bool:
        point = max(int(position), 0)
        removed = max(int(chars_removed), 0)
        added = max(int(chars_added), 0)
        source = str(source_after)
        changed = False
        updated: list[RangeBookmark] = []

        for item in self._items:
            reanchored = self._reanchor_surviving_text_in_replacement(
                item,
                point,
                removed,
                added,
                source,
            )
            if reanchored is not None:
                if reanchored != item:
                    changed = True
                updated.append(reanchored)
                continue

            start, end = self._transform(
                item.start_char,
                item.end_char,
                point,
                removed,
                added,
            )
            refreshed = item.with_range(start, end, source)
            if refreshed is None:
                changed = True
                continue
            if refreshed != item:
                changed = True
            updated.append(refreshed)

        self.replace(updated)
        return changed

    @staticmethod
    def _reanchor_surviving_text_in_replacement(
        item: RangeBookmark,
        point: int,
        removed: int,
        added: int,
        source_after: str,
    ) -> RangeBookmark | None:
        if removed <= 0 or added <= 0 or not item.text:
            return None
        cut_end = point + removed
        if not (point <= item.start_char and item.end_char <= cut_end):
            return None

        replacement_start = max(0, min(point, len(source_after)))
        replacement_end = max(
            replacement_start,
            min(point + added, len(source_after)),
        )
        if replacement_end <= replacement_start:
            return None

        expected = replacement_start + max(
            0,
            min(item.start_char - point, replacement_end - replacement_start),
        )
        candidates: list[int] = []
        found = source_after.find(item.text, replacement_start, replacement_end)
        while found >= 0:
            candidates.append(found)
            found = source_after.find(
                item.text,
                found + 1,
                replacement_end,
            )
        if not candidates:
            return None

        start = min(candidates, key=lambda value: abs(value - expected))
        return item.with_range(start, start + len(item.text), source_after)

    @staticmethod
    def _transform(
        start: int,
        end: int,
        point: int,
        removed: int,
        added: int,
    ) -> tuple[int, int]:
        if removed == 0:
            if point < start:
                return start + added, end + added
            if start <= point <= end:
                return start, end + added
            return start, end

        cut_end = point + removed
        delta = added - removed
        if cut_end <= start:
            return start + delta, end + delta
        if point >= end:
            return start, end

        if start < point:
            new_start = start
        elif start >= cut_end:
            new_start = start + delta
        else:
            new_start = point

        if end <= point:
            new_end = end
        elif end >= cut_end:
            new_end = end + delta
        else:
            new_end = point + added

        return max(new_start, 0), max(new_end, max(new_start, 0))
