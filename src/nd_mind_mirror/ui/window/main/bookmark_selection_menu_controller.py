"""Own the single contextual bookmark command shown in the Bookmarks menu."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget


class BookmarkSelectionMenuController(QObject):
    """Route the one bookmark action to a selection or cursor bookmark."""

    def __init__(
        self,
        editor_panel,
        bookmarks_menu,
        toggle_action: QAction,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._menu = bookmarks_menu
        self._toggle_action = toggle_action
        self._application = QApplication.instance()

        self._menu.aboutToShow.connect(self._refresh_action)
        try:
            self._toggle_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._toggle_action.triggered.connect(self._toggle_contextual_bookmark)

        if self._application is not None:
            self._application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if event_type not in {
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
        }:
            return super().eventFilter(watched, event)

        if (
            not self._event_matches_toggle_shortcut(event)
            or not self._focus_is_in_current_editor()
        ):
            return super().eventFilter(watched, event)

        event.accept()
        if event_type == QEvent.Type.ShortcutOverride:
            return super().eventFilter(watched, event)

        if not event.isAutoRepeat():
            self._toggle_contextual_bookmark()
        return True

    def _refresh_action(self) -> None:
        """Keep one action and describe the operation it will perform now."""
        self._toggle_action.setText(
            "Bookmark Selection"
            if self._selection_is_available()
            else "Toggle Bookmark at Cursor"
        )
        self._toggle_action.setEnabled(self._editor_panel.current_editor() is not None)

    def _toggle_contextual_bookmark(self, _checked: bool = False) -> None:
        editor = self._editor_panel.current_editor()
        if editor is None:
            return
        if self._selection_is_available():
            toggle_selection = getattr(editor, "toggle_bookmark_selection", None)
            if callable(toggle_selection):
                toggle_selection()
                return
        self._editor_panel.toggle_current_bookmark()

    def _selection_is_available(self) -> bool:
        editor = self._editor_panel.current_editor()
        capture = getattr(editor, "_selection_bookmark_context", None)
        if capture is None:
            return False
        capture_selection = getattr(capture, "capture_selection", None)
        if not callable(capture_selection):
            return False
        return capture_selection() is not None

    def _event_matches_toggle_shortcut(self, event) -> bool:
        return self._event_matches_shortcut(
            event,
            self._toggle_action.shortcut(),
        )

    @staticmethod
    def _event_matches_shortcut(event, sequence: QKeySequence) -> bool:
        if sequence.isEmpty():
            return False
        try:
            event_sequence = QKeySequence(event.keyCombination())
        except (AttributeError, TypeError):
            return False
        return event_sequence == sequence

    def _focus_is_in_current_editor(self) -> bool:
        editor = self._editor_panel.current_editor()
        focus = QApplication.focusWidget()
        if editor is None or focus is None or not isinstance(editor, QWidget):
            return False
        return focus is editor or editor.isAncestorOf(focus)
