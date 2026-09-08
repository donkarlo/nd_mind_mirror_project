from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_context_controller import (
    SelectionBookmarkContextController,
)


class _Cursor:
    def __init__(self, anchor: int, position: int) -> None:
        self._anchor = anchor
        self._position = position

    def hasSelection(self) -> bool:
        return self._anchor != self._position

    def anchor(self) -> int:
        return self._anchor

    def position(self) -> int:
        return self._position


class _SourceEditor:
    _edit_mode = "source"

    def __init__(self) -> None:
        self._cursor = _Cursor(10, 25)
        self.restored = None
        self.toggled = 0

    def textCursor(self):
        return self._cursor

    def _source_location_for_position(self, value: int):
        return (value + 1, 1)

    def _set_source_selection_from_locations(self, anchor, position) -> None:
        self.restored = (anchor, position)

    def toggle_bookmark_at_cursor(self) -> None:
        self.toggled += 1


def test_context_bookmark_replays_same_editor_action() -> None:
    editor = _SourceEditor()
    controller = SelectionBookmarkContextController(editor)
    locations = controller.capture_selection()
    assert locations == ((11, 1), (26, 1))

    controller.toggle_captured_selection(*locations)
    assert editor.restored == locations
    assert editor.toggled == 1
