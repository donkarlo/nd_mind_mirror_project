"""Route Navigator file clipboard keys before generic tree clipboard handling."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt


class NavigatorClipboardKeyEventFilter(QObject):
    """Own Ctrl+C/Ctrl+X/Ctrl+V while the Navigator tree has keyboard focus."""

    def __init__(self, context_controller, tree, parent=None) -> None:
        """Install one deterministic file-clipboard key path on the Navigator tree."""
        super().__init__(parent)
        self._context_controller = context_controller
        self._tree = tree
        self._tree.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Dispatch Navigator file clipboard keys before FileSystemPanel sees them."""
        if watched is not self._tree:
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.ShortcutOverride:
            if self._operation_for_event(event) is not None:
                event.accept()
                return True
            return super().eventFilter(watched, event)

        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)

        operation = self._operation_for_event(event)
        if operation is None:
            return super().eventFilter(watched, event)

        event.accept()
        if event.isAutoRepeat():
            return True

        if operation == "copy":
            self._context_controller.copy_selected_path()
        elif operation == "cut":
            self._context_controller.cut_selected_paths()
        else:
            self._context_controller.paste_into_selected_path()
        return True

    def _operation_for_event(self, event) -> str | None:
        """Return the claimed file operation, leaving image-paste fallback untouched."""
        if not self._is_plain_control(event.modifiers()):
            return None

        key = event.key()
        if key == Qt.Key.Key_C:
            return (
                "copy"
                if self._context_controller.selected_paths()
                else None
            )
        if key == Qt.Key.Key_X:
            return (
                "cut"
                if self._context_controller.selected_paths()
                else None
            )
        if key == Qt.Key.Key_V:
            return (
                "paste"
                if self._context_controller.can_paste()
                else None
            )
        return None

    @staticmethod
    def _is_plain_control(modifiers) -> bool:
        """Accept Ctrl without Shift/Alt/Meta so unrelated shortcuts keep their meaning."""
        if not bool(modifiers & Qt.KeyboardModifier.ControlModifier):
            return False
        forbidden = (
            Qt.KeyboardModifier.ShiftModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        )
        return not bool(modifiers & forbidden)
