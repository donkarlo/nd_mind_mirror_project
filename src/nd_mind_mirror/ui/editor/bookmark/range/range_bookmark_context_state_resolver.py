"""Resolve Add/Remove Bookmark state from selection and click positions."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_collection import (
    RangeBookmarkCollection,
)


class RangeBookmarkContextStateResolver:
    """Return one deterministic context action for a range bookmark interaction."""

    def resolve(
        self,
        collection: RangeBookmarkCollection,
        *,
        click_position: int,
        selection_start: int | None,
        selection_end: int | None,
    ) -> dict[str, object]:
        existing = collection.at_position(click_position)
        if existing is not None:
            return {
                "action": "remove",
                "label": "Remove Bookmark",
                "bookmark_id": existing.id,
            }

        if selection_start is None or selection_end is None:
            return {"action": "none", "label": "Add Bookmark", "bookmark_id": ""}

        start, end = sorted((int(selection_start), int(selection_end)))
        if end <= start or not (start <= int(click_position) <= end):
            return {"action": "none", "label": "Add Bookmark", "bookmark_id": ""}

        overlap = collection.overlapping(start, end)
        if overlap is not None:
            return {
                "action": "remove",
                "label": "Remove Bookmark",
                "bookmark_id": overlap.id,
            }

        return {"action": "add", "label": "Add Bookmark", "bookmark_id": ""}
