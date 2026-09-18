"""Unified bookmark tracker for normal, large, Source, and Visual editing."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_collection import (
    RangeBookmarkCollection,
)
from nd_mind_mirror.core.bookmark.range.range_bookmark_migrator import (
    RangeBookmarkMigrator,
)


class RangeBookmarkTracker:
    """Keep one character-range model regardless of editor virtualization."""

    def __init__(self, source: str = "") -> None:
        self._source = str(source)
        self._collection = RangeBookmarkCollection()
        self._migrator = RangeBookmarkMigrator()

    @property
    def source(self) -> str:
        return self._source

    @property
    def collection(self) -> RangeBookmarkCollection:
        return self._collection

    def load(self, raw_bookmarks: list[dict[str, object]] | None, source: str) -> None:
        self._source = str(source)
        self._collection.replace(
            self._migrator.migrate(raw_bookmarks, self._source)
        )

    def serialize(self) -> list[dict[str, object]]:
        return [item.to_dict() for item in self._collection.items]

    def apply_edit(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
        source_after: str,
    ) -> bool:
        source = str(source_after)
        changed = self._collection.apply_edit(
            position,
            chars_removed,
            chars_added,
            source,
        )
        self._source = source
        return changed

    def replace_source(self, source_after: str) -> bool:
        new_source = str(source_after)
        old_source = self._source
        if new_source == old_source:
            return False

        prefix = 0
        prefix_limit = min(len(old_source), len(new_source))
        while prefix < prefix_limit and old_source[prefix] == new_source[prefix]:
            prefix += 1

        old_tail = len(old_source)
        new_tail = len(new_source)
        while (
            old_tail > prefix
            and new_tail > prefix
            and old_source[old_tail - 1] == new_source[new_tail - 1]
        ):
            old_tail -= 1
            new_tail -= 1

        return self.apply_edit(
            prefix,
            old_tail - prefix,
            new_tail - prefix,
            new_source,
        )
