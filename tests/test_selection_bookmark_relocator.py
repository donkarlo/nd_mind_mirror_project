from nd_mind_mirror.core.bookmark.selection_bookmark_relocator import (
    SelectionBookmarkRelocator,
)


def test_selection_moves_with_relocated_anchor() -> None:
    relocator = SelectionBookmarkRelocator()
    source = "inserted\nalpha\nbeta\n"
    bookmarks = [
        {
            "line": 1,
            "column": 1,
            "name": "",
            "anchor": "alpha",
            "selection": {
                "anchor": [1, 1],
                "position": [2, 3],
                "text": "alpha\nbe",
            },
        }
    ]

    relocated, changed = relocator.relocate(bookmarks, source)

    assert changed is True
    assert relocated[0]["line"] == 2
    assert relocated[0]["selection"]["anchor"] == [2, 1]
    assert relocated[0]["selection"]["position"] == [3, 3]


def test_selection_payload_is_preserved_without_relocation() -> None:
    relocator = SelectionBookmarkRelocator()
    source = "alpha\nbeta\n"
    bookmarks = [
        {
            "line": 1,
            "column": 1,
            "name": "",
            "anchor": "alpha",
            "selection": {
                "anchor": [1, 2],
                "position": [2, 3],
                "text": "lpha\nbe",
            },
        }
    ]

    relocated, changed = relocator.relocate(bookmarks, source)

    assert changed is False
    assert relocated[0]["selection"] == bookmarks[0]["selection"]
