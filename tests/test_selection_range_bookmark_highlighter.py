from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_highlighter import (
    SelectionRangeBookmarkHighlighter,
)


def test_selection_highlighter_finds_exact_bookmarked_text_near_projection():
    highlighter = object.__new__(SelectionRangeBookmarkHighlighter)
    assert highlighter._nearest_occurrence(
        "alpha beta gamma",
        "beta",
        0,
        len("alpha beta gamma"),
    ) == (6, 10)


def test_selection_highlighter_does_not_invent_a_block_range():
    highlighter = object.__new__(SelectionRangeBookmarkHighlighter)
    assert highlighter._nearest_occurrence(
        "alpha gamma",
        "beta",
        0,
        len("alpha gamma"),
    ) is None
