from nd_mind_mirror.core.bookmark.bookmark_anchor_relocator import (
    BookmarkAnchorRelocator,
)


def test_bookmark_relocates_with_inserted_lines_and_keeps_column_and_name():
    relocator = BookmarkAnchorRelocator()
    bookmarks = [
        {
            "line": 2,
            "column": 5,
            "name": "Important state",
            "anchor": "target paragraph",
        }
    ]

    relocated, changed = relocator.relocate(
        bookmarks,
        "new first line\nold first line\ntarget paragraph\nafter",
    )

    assert changed is True
    assert relocated == [
        {
            "line": 3,
            "column": 5,
            "name": "Important state",
            "anchor": "target paragraph",
        }
    ]


def test_bookmark_column_is_clamped_when_bookmarked_line_is_shortened():
    relocator = BookmarkAnchorRelocator()
    relocated, _changed = relocator.relocate(
        [{"line": 1, "column": 99, "name": "", "anchor": "old text"}],
        "x",
    )
    assert relocated[0]["line"] == 1
    assert relocated[0]["column"] == 2
    assert relocated[0]["anchor"] == "x"
