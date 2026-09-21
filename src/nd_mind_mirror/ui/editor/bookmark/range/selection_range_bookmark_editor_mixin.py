"""Selection-only bookmark semantics over the canonical range bookmark engine."""

from __future__ import annotations

from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_editor_mixin import (
    RangeBookmarkEditorMixin,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_selection_resolver import (
    RangeBookmarkSelectionResolver,
)
from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_highlighter import (
    SelectionRangeBookmarkHighlighter,
)


class SelectionRangeBookmarkEditorMixin(RangeBookmarkEditorMixin):
    """Allow bookmarks only for explicit text selections, never lines or blocks."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._range_bookmark_selection_resolver = RangeBookmarkSelectionResolver()
        self._install_selection_highlighter()

    def toggle_bookmark_at_cursor(self) -> None:
        self.toggle_bookmark_selection()

    def range_bookmark_menu_context(self) -> dict[str, object]:
        selection = self._active_canonical_selection()
        if selection is None:
            return self._none_state()
        start, end = selection
        existing = self._range_bookmark_tracker.collection.for_exact_range(
            start,
            end,
        )
        if existing is not None:
            return {
                "action": "remove",
                "label": "Remove Bookmark",
                "bookmark_id": existing.id,
            }
        return {
            "action": "add",
            "label": "Add Bookmark",
            "bookmark_id": "",
        }

    def range_bookmark_context_at(self, click_position: int) -> dict[str, object]:
        selection = self._active_canonical_selection()
        if selection is None:
            return self._none_state()
        start, end = selection
        point = int(click_position)
        if not (start <= point <= end):
            return self._none_state()
        existing = self._range_bookmark_tracker.collection.for_exact_range(
            start,
            end,
        )
        if existing is not None:
            return {
                "action": "remove",
                "label": "Remove Bookmark",
                "bookmark_id": existing.id,
            }
        return {
            "action": "add",
            "label": "Add Bookmark",
            "bookmark_id": "",
        }

    def execute_range_bookmark_state(self, state: dict[str, object]) -> None:
        """Apply only the exact current selection and retire stale broad containers.

        Older builds could persist a paragraph/section-sized range for a short
        Visual selection.  When the user explicitly bookmarks a smaller exact
        selection inside such a stale range, replace the containing stale range
        so the visible bookmark becomes exactly what is highlighted now.
        """
        action = str(state.get("action", "none"))
        changed = False
        collection = self._range_bookmark_tracker.collection

        if action == "remove":
            changed = collection.remove(str(state.get("bookmark_id", "")))
        elif action == "add":
            selection = self._active_canonical_selection()
            if selection is not None:
                start, end = selection
                stale_ids = [
                    item.id
                    for item in collection.items
                    if item.start_char <= start
                    and end <= item.end_char
                    and (item.start_char, item.end_char) != (start, end)
                ]
                for bookmark_id in stale_ids:
                    changed = collection.remove(bookmark_id) or changed
                added = collection.add(start, end, self.toPlainText())
                changed = added is not None or changed

        if changed:
            self._range_bookmark_model_changed()

    def _active_canonical_selection(self) -> tuple[int, int] | None:
        resolver = getattr(self, "_range_bookmark_selection_resolver", None)
        if resolver is None:
            resolver = RangeBookmarkSelectionResolver()
            self._range_bookmark_selection_resolver = resolver
        return resolver.resolve(self)

    def _install_selection_highlighter(self) -> None:
        self._range_bookmark_highlighter = SelectionRangeBookmarkHighlighter(self)
        self._refresh_active_range_bookmarks()

    @staticmethod
    def _none_state() -> dict[str, object]:
        return {
            "action": "none",
            "label": "Add Bookmark",
            "bookmark_id": "",
        }
