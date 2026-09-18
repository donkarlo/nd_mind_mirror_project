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
        """Compatibility entry point: a cursor without selection does nothing."""
        self.toggle_bookmark_selection()

    def range_bookmark_menu_context(self) -> dict[str, object]:
        """Toggle only the exact selected range; overlap is not equivalence."""
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
        """Context menus expose bookmark actions only inside the active selection."""
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

    def _active_canonical_selection(self) -> tuple[int, int] | None:
        resolver = getattr(self, "_range_bookmark_selection_resolver", None)
        if resolver is None:
            resolver = RangeBookmarkSelectionResolver()
            self._range_bookmark_selection_resolver = resolver
        return resolver.resolve(self)

    def _install_selection_highlighter(self) -> None:
        """Replace the approximate Visual projector with exact-text presentation."""
        previous = self._range_bookmark_highlighter
        signals = (
            self.cursorPositionChanged,
            self._visual_editor.cursorPositionChanged,
            self.active_view_changed,
        )
        for signal in signals:
            try:
                signal.disconnect(previous.refresh)
            except (RuntimeError, TypeError):
                pass

        self._range_bookmark_highlighter = SelectionRangeBookmarkHighlighter(self)
        for signal in signals:
            signal.connect(self._range_bookmark_highlighter.refresh)

        self._range_bookmark_highlighter.refresh()

    @staticmethod
    def _none_state() -> dict[str, object]:
        return {
            "action": "none",
            "label": "Add Bookmark",
            "bookmark_id": "",
        }
