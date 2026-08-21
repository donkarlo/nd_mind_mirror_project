"""Normalize editor undo/redo shortcuts across keyboard layouts before Qt widget handlers run."""

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QWidget

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor


class UndoRedoController(QObject):
    """Consume Undo/Redo keys for Source and Visual editors using Qt standard-key matching plus layout fallbacks."""

    def __init__(self, parent=None) -> None:
        """Install one application event filter so German QWERTZ and other layouts behave identically."""
        super().__init__(parent)
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        """Reserve and execute Undo/Redo before QAction, QShortcut, or editor-specific handlers can reinterpret Y/Z."""
        if not isinstance(event, QKeyEvent):
            return super().eventFilter(watched, event)
        if event.type() not in {
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
        }:
            return super().eventFilter(watched, event)

        editor = self._supported_editor(watched)
        if editor is None:
            return super().eventFilter(watched, event)

        command = self._command_for(event)
        if command is None:
            return super().eventFilter(watched, event)

        event.accept()
        if event.type() == QEvent.Type.ShortcutOverride:
            return True

        if command == "undo":
            editor.undo()
        else:
            editor.redo()
        return True

    @staticmethod
    def _supported_editor(watched) -> TextEditor | LatexVisualEditor | None:
        """Resolve the focused widget or one of its children to a Source or Visual editor instance."""
        widget = watched if isinstance(watched, QWidget) else QApplication.focusWidget()
        if widget is None:
            widget = QApplication.focusWidget()
        while widget is not None:
            if isinstance(widget, (TextEditor, LatexVisualEditor)):
                return widget
            widget = widget.parentWidget()
        return None

    @staticmethod
    def _command_for(event: QKeyEvent) -> str | None:
        """Map the key event to undo/redo using Qt's native-aware StandardKey matcher before logical-key fallbacks."""
        if event.matches(QKeySequence.StandardKey.Undo):
            return "undo"
        if event.matches(QKeySequence.StandardKey.Redo):
            return "redo"

        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        forbidden = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if not control or forbidden:
            return None

        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        text = event.text()
        if text == "\x1a":
            return "redo" if shift else "undo"
        if text == "\x19" and not shift:
            return "redo"

        key = event.key()
        if key == Qt.Key.Key_Z:
            return "redo" if shift else "undo"
        if key == Qt.Key.Key_Y and not shift:
            return "redo"

        native = int(event.nativeVirtualKey())
        if native in {ord("z"), ord("Z")}:
            return "redo" if shift else "undo"
        if native in {ord("y"), ord("Y")} and not shift:
            return "redo"
        return None
