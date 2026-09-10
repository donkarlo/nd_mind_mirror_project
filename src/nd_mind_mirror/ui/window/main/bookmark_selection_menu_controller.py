"""Own bookmark menu commands and the editor-scoped bookmark shortcut."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget


class BookmarkSelectionMenuController(QObject):
    """Route menu clicks and the configured bookmark shortcut through one command path."""

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

        self._selection_action = QAction("Bookmark Selection", self)
        self._selection_action.triggered.connect(self._toggle_current_selection)
        self._menu.aboutToShow.connect(self._refresh_action)

        # The controller is the single command owner. Menu activation and the
        # keyboard path therefore cannot drift apart.
        try:
            self._toggle_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._toggle_action.triggered.connect(self._toggle_current_bookmark)

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
            # Accept the override so Qt does not dispatch the QAction shortcut
            # separately; the following KeyPress executes the command once.
            return super().eventFilter(watched, event)

        if not event.isAutoRepeat():
            self._toggle_current_bookmark()
        return True

    def _refresh_action(self) -> None:
        """Keep Bookmark Selection immediately after the normal toggle action."""
        self._menu.removeAction(self._selection_action)
        actions = list(self._menu.actions())

        before = None
        try:
            toggle_index = actions.index(self._toggle_action)
        except ValueError:
            toggle_index = -1
        if 0 <= toggle_index + 1 < len(actions):
            before = actions[toggle_index + 1]

        if before is None:
            self._menu.addAction(self._selection_action)
        else:
            self._menu.insertAction(before, self._selection_action)

        editor = self._editor_panel.current_editor()
        capture = getattr(editor, "_selection_bookmark_context", None)
        self._selection_action.setEnabled(
            capture is not None and capture.capture_selection() is not None
        )

    def _toggle_current_bookmark(self, _checked: bool = False) -> None:
        """Toggle a range bookmark when selected, otherwise toggle the current line."""
        self._editor_panel.toggle_current_bookmark()

    def _toggle_current_selection(self, _checked: bool = False) -> None:
        editor = self._editor_panel.current_editor()
        toggle = getattr(editor, "toggle_bookmark_selection", None)
        if callable(toggle):
            toggle()

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
