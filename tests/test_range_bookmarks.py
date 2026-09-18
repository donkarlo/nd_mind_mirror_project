from nd_mind_mirror.core.bookmark.range.range_bookmark_migrator import (
    RangeBookmarkMigrator,
)
from nd_mind_mirror.core.bookmark.range.range_bookmark_tracker import (
    RangeBookmarkTracker,
)


def test_add_and_shift_range_bookmark():
    tracker = RangeBookmarkTracker("hello world")
    item = tracker.collection.add(6, 11, tracker.source)
    assert item is not None
    assert tracker.serialize()[0]["text"] == "world"

    tracker.apply_edit(0, 0, 4, "say hello world")
    saved = tracker.serialize()[0]
    assert saved["start_char"] == 10
    assert saved["end_char"] == 15
    assert saved["text"] == "world"


def test_typing_inside_range_expands_bookmark():
    tracker = RangeBookmarkTracker("abc def")
    tracker.collection.add(4, 7, tracker.source)
    tracker.apply_edit(5, 0, 1, "abc dXef")
    saved = tracker.serialize()[0]
    assert saved["start_char"] == 4
    assert saved["end_char"] == 8
    assert saved["text"] == "dXef"


def test_legacy_selection_is_migrated_and_line_only_is_dropped():
    source = "first line\nsecond line\n"
    raw = [
        {
            "line": 2,
            "column": 1,
            "selection": {
                "anchor": [2, 1],
                "position": [2, 7],
                "text": "second",
            },
        },
        {"line": 1, "column": 1, "anchor": "first line"},
    ]
    migrated = RangeBookmarkMigrator().migrate(raw, source)
    assert len(migrated) == 1
    assert migrated[0].text == "second"
    assert source[migrated[0].start_char:migrated[0].end_char] == "second"


def test_replace_source_uses_one_unified_tracker():
    tracker = RangeBookmarkTracker("0123456789")
    tracker.collection.add(4, 7, tracker.source)
    tracker.replace_source("AA0123456789")
    saved = tracker.serialize()[0]
    assert (saved["start_char"], saved["end_char"]) == (6, 9)
    assert saved["text"] == "456"
