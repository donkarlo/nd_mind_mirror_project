"""Regression: an exact selection replaces a stale containing bookmark range."""

from nd_mind_mirror.core.bookmark.range.range_bookmark_tracker import RangeBookmarkTracker
from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_editor_mixin import (
    SelectionRangeBookmarkEditorMixin,
)


class _FixedResolver:
    def resolve(self, _editor):
        return (6, 10)


class _Harness(SelectionRangeBookmarkEditorMixin):
    def toPlainText(self) -> str:
        return "alpha beta gamma"

    def _range_bookmark_model_changed(self) -> None:
        self.changed = True


def test_exact_selection_replaces_stale_containing_range() -> None:
    harness = object.__new__(_Harness)
    harness._range_bookmark_tracker = RangeBookmarkTracker("alpha beta gamma")
    harness._range_bookmark_selection_resolver = _FixedResolver()
    harness.changed = False
    harness._range_bookmark_tracker.collection.add(0, 16, "alpha beta gamma")

    harness.execute_range_bookmark_state(
        {"action": "add", "label": "Add Bookmark", "bookmark_id": ""}
    )

    items = harness._range_bookmark_tracker.collection.items
    assert len(items) == 1
    assert items[0].start_char == 6
    assert items[0].end_char == 10
    assert items[0].text == "beta"
    assert harness.changed is True
