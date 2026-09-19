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


def test_containing_paragraph_rewrite_preserves_exact_selected_bookmark():
    phrase = "die normal Schlafstunde "
    paragraph = (
        "Matt der mögte nicht seit Kinderheit zu viel reden "
        "und sein liebliegs Teil in die sie spatzieren nach "
        + phrase
    )
    source = "before\n" + paragraph + "\nafter\n"
    tracker = RangeBookmarkTracker(source)
    start = source.index(phrase)
    tracker.collection.add(start, start + len(phrase), source)

    paragraph_start = source.index(paragraph)
    tracker.apply_edit(
        paragraph_start,
        len(paragraph),
        len(paragraph),
        source,
    )

    saved = tracker.serialize()[0]
    assert saved["start_char"] == start
    assert saved["end_char"] == start + len(phrase)
    assert saved["text"] == phrase


def test_changed_containing_paragraph_reanchors_same_selected_text():
    phrase = "die normal Schlafstunde "
    old_paragraph = "Matt old words " + phrase
    new_paragraph = "Matt several newly inserted words before it " + phrase
    source_before = "before\n" + old_paragraph + "\nafter\n"
    source_after = "before\n" + new_paragraph + "\nafter\n"
    tracker = RangeBookmarkTracker(source_before)
    start = source_before.index(phrase)
    tracker.collection.add(start, start + len(phrase), source_before)

    paragraph_start = source_before.index(old_paragraph)
    tracker.apply_edit(
        paragraph_start,
        len(old_paragraph),
        len(new_paragraph),
        source_after,
    )

    saved = tracker.serialize()[0]
    expected_start = source_after.index(phrase)
    assert saved["start_char"] == expected_start
    assert saved["end_char"] == expected_start + len(phrase)
    assert saved["text"] == phrase


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
