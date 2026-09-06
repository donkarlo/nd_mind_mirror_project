"""Close the current editor tab reliably from Source or Visual with Ctrl+W."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget


class CurrentEditorTabCloseController(QObject):
    """Route Ctrl+W from the active editor subtree to the canonical tab-close workflow."""

    def __init__(self, main_window, editor_panel, close_action, parent=None) -> None:
        """Install one application-level key filter and reuse the existing close action."""
        super().__init__(parent or main_window)
        self._window = main_window
        self._editor_panel = editor_panel
        self._close_action = close_action
        self._application = QApplication.instance()

        try:
            self._close_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._close_action.triggered.connect(self.request_close_current_tab)

        if self._application is not None:
            self._application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Consume Ctrl+W only while keyboard focus belongs to the current editor."""
        if event.type() == QEvent.Type.ShortcutOverride:
            if self._is_close_key(event) and self._focus_is_in_current_editor():
                event.accept()
            return super().eventFilter(watched, event)

        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)

        if not self._is_close_key(event) or not self._focus_is_in_current_editor():
            return super().eventFilter(watched, event)

        event.accept()
        if not event.isAutoRepeat():
            self.request_close_current_tab()
        return True

    def request_close_current_tab(self, _checked: bool = False) -> None:
        """Close the current tab, including a pinned tab, through the normal save prompt."""
        path = self._editor_panel.current_path()
        pinned_controller = getattr(self._window, "_pinned_tab_controller", None)
        was_pinned = bool(
            path is not None
            and pinned_controller is not None
            and pinned_controller._is_pinned(path)
        )

        # PinnedTabController intentionally protects pins from automatic
        # eviction. Ctrl+W is an explicit user close, so temporarily unpin it.
        # If the unsaved-changes dialog is cancelled, restore the pin.
        if was_pinned:
            pinned_controller.unpin_path(path)

        self._editor_panel.request_close_current_tab()

        if (
            was_pinned
            and path is not None
            and self._editor_panel._index_for_path(path) >= 0
        ):
            pinned_controller.pin_path(path)

    @staticmethod
    def _is_close_key(event) -> bool:
        """Return True only for plain Ctrl+W, not Ctrl+Shift/Alt/Meta variants."""
        if event.key() != Qt.Key.Key_W:
            return False
        modifiers = event.modifiers()
        if not bool(modifiers & Qt.KeyboardModifier.ControlModifier):
            return False
        disallowed = (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        return not bool(modifiers & disallowed)

    def _focus_is_in_current_editor(self) -> bool:
        """Return whether focus is on Source/Visual or another child of the active editor."""
        editor = self._editor_panel.current_editor()
        focus = QApplication.focusWidget()
        if editor is None or focus is None or not isinstance(editor, QWidget):
            return False
        return focus is editor or editor.isAncestorOf(focus)
