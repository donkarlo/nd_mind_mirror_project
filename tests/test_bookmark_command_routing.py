from PySide6.QtCore import QKeyCombination, Qt
from PySide6.QtGui import QKeySequence

from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_editor_mixin import (
    SelectionBookmarkEditorMixin,
)
from nd_mind_mirror.ui.window.main.bookmark_selection_menu_controller import (
    BookmarkSelectionMenuController,
)


class _BookmarkBase:
    def __init__(self) -> None:
        self.line_toggles = 0

    def toggle_bookmark_at_cursor(self) -> None:
        self.line_toggles += 1


class _SelectionContext:
    def __init__(self, captured):
        self._captured = captured

    def capture_selection(self):
        return self._captured


class _SelectionEditor(SelectionBookmarkEditorMixin, _BookmarkBase):
    def __init__(self, captured) -> None:
        _BookmarkBase.__init__(self)
        self._selection_bookmark_context = _SelectionContext(captured)
        self.selection_toggles = []

    def _toggle_selection_bookmark(self, anchor, position) -> None:
        self.selection_toggles.append((anchor, position))


class _KeyEvent:
    def __init__(self) -> None:
        self._combination = QKeyCombination(
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier,
            Qt.Key.Key_B,
        )

    def keyCombination(self):
        return self._combination


def test_toggle_bookmark_uses_selection_when_present() -> None:
    editor = _SelectionEditor(((2, 3), (4, 5)))

    editor.toggle_bookmark_at_cursor()

    assert editor.selection_toggles == [((2, 3), (4, 5))]
    assert editor.line_toggles == 0


def test_toggle_bookmark_falls_back_to_current_line_without_selection() -> None:
    editor = _SelectionEditor(None)

    editor.toggle_bookmark_at_cursor()

    assert editor.selection_toggles == []
    assert editor.line_toggles == 1


def test_ctrl_shift_b_matches_bookmark_toggle_shortcut() -> None:
    assert BookmarkSelectionMenuController._event_matches_shortcut(
        _KeyEvent(),
        QKeySequence("Ctrl+Shift+B"),
    )
