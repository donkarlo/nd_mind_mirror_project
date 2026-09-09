"""Own the Bookmarks-menu action for bookmarking the active selection."""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction


class BookmarkSelectionMenuController(QObject):
    """Insert a stable Bookmark Selection action after every menu rebuild."""

    def __init__(self, editor_panel, bookmarks_menu, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._menu = bookmarks_menu
        self._action = QAction("Bookmark Selection", self)
        self._action.triggered.connect(self._toggle_current_selection)
        self._menu.aboutToShow.connect(self._refresh_action)

    def _refresh_action(self) -> None:
        self._menu.removeAction(self._action)
        actions = list(self._menu.actions())
        before = actions[1] if len(actions) > 1 else None
        if before is None:
            self._menu.addAction(self._action)
        else:
            self._menu.insertAction(before, self._action)

        editor = self._editor_panel.current_editor()
        capture = getattr(editor, "_selection_bookmark_context", None)
        self._action.setEnabled(
            capture is not None and capture.capture_selection() is not None
        )

    def _toggle_current_selection(self) -> None:
        editor = self._editor_panel.current_editor()
        toggle = getattr(editor, "toggle_bookmark_selection", None)
        if callable(toggle):
            toggle()
