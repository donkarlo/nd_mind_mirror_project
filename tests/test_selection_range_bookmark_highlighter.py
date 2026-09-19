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


def test_source_highlight_uses_exact_text_not_broad_paragraph_range():
    highlighter = object.__new__(SelectionRangeBookmarkHighlighter)
    phrase = "die normal Schlafstunde "
    paragraph = (
        "Matt der mögte nicht seit Kinderheit zu viel reden "
        "und sein liebliegs Teil in die sie spatzieren nach "
        + phrase
    )
    expected_start = paragraph.index(phrase)

    assert highlighter._exact_source_range(
        paragraph,
        phrase,
        0,
        len(paragraph),
        0,
    ) == (expected_start, expected_start + len(phrase))


def test_source_highlight_respects_window_offset_for_exact_bookmark():
    highlighter = object.__new__(SelectionRangeBookmarkHighlighter)
    phrase = "selected text"
    visible = "prefix " + phrase + " suffix"
    window_start = 500
    canonical_start = window_start + visible.index(phrase)

    assert highlighter._exact_source_range(
        visible,
        phrase,
        canonical_start,
        canonical_start + len(phrase),
        window_start,
    ) == (visible.index(phrase), visible.index(phrase) + len(phrase))
