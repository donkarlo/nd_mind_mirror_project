"""Make Source/Visual context-menu bookmarks use the same selection path as the main action."""


class SelectionBookmarkContextController:
    """Capture a canonical selection and replay it through the normal bookmark action."""

    def __init__(self, editor) -> None:
        self._editor = editor

    def capture_selection(
        self,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return the active Source range in canonical line/column coordinates."""
        if getattr(self._editor, "_edit_mode", "source") == "visual":
            visual = self._editor._visual_editor
            cursor = visual.textCursor()
            if not cursor.hasSelection():
                return None
            anchor, position = visual.source_selection_locations()
        else:
            cursor = self._editor.textCursor()
            if not cursor.hasSelection():
                return None
            anchor = self._editor._source_location_for_position(cursor.anchor())
            position = self._editor._source_location_for_position(cursor.position())

        if anchor == position:
            return None
        return anchor, position

    def toggle_captured_selection(
        self,
        anchor: tuple[int, int],
        position: tuple[int, int],
    ) -> None:
        """Restore a saved range, then invoke the same toggle used by the Bookmarks action."""
        if getattr(self._editor, "_edit_mode", "source") == "visual":
            self._editor._visual_editor.set_selection_from_source_locations(
                anchor,
                position,
                ensure_visible=True,
            )
        else:
            self._editor._set_source_selection_from_locations(
                anchor,
                position,
            )
        self._editor.toggle_bookmark_at_cursor()
