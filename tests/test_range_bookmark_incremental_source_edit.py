"""Regression coverage for incremental bookmark tracking during Source typing."""

from nd_mind_mirror.core.bookmark.range.range_bookmark_source_buffer import (
    RangeBookmarkSourceBuffer,
)
from nd_mind_mirror.core.bookmark.range.range_bookmark_tracker import (
    RangeBookmarkTracker,
)


def test_source_buffer_applies_adjacent_typing_without_reordering() -> None:
    buffer = RangeBookmarkSourceBuffer("In ")
    for position, text in ((3, "t"), (4, "h"), (5, "i"), (6, "s")):
        buffer.apply_edit(position, 0, text)
    assert buffer.source == "In this"


def test_incremental_typing_before_bookmark_shifts_range() -> None:
    tracker = RangeBookmarkTracker("alpha beta")
    tracker.collection.add(6, 10, tracker.source)
    tracker.apply_source_edit(0, 0, "new ")
    saved = tracker.serialize()[0]
    assert (saved["start_char"], saved["end_char"]) == (10, 14)
    assert saved["text"] == "beta"
    assert tracker.source == "new alpha beta"


def test_incremental_typing_inside_bookmark_updates_exact_text() -> None:
    tracker = RangeBookmarkTracker("abc def")
    tracker.collection.add(4, 7, tracker.source)
    tracker.apply_source_edit(5, 0, "X")
    saved = tracker.serialize()[0]
    assert (saved["start_char"], saved["end_char"]) == (4, 8)
    assert saved["text"] == "dXef"
    assert tracker.source == "abc dXef"


def test_incremental_edit_after_bookmark_leaves_bookmark_unchanged() -> None:
    tracker = RangeBookmarkTracker("alpha beta")
    tracker.collection.add(0, 5, tracker.source)
    changed = tracker.apply_source_edit(len("alpha beta"), 0, "!")
    assert changed is False
    assert tracker.serialize()[0]["text"] == "alpha"
    assert tracker.source == "alpha beta!"
