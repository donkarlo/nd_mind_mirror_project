"""Source-editor commands requested by migrations 6 and 7."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel


class SourceEditCommandController(QObject):
    """Own Source-only line deletion and underscore escaping without modifying editor classes."""

    def __init__(self, editor_panel: EditorPanel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() != QEvent.Type.KeyPress
            or not isinstance(watched, LatexEditor)
            or watched.edit_mode != "source"
        ):
            return super().eventFilter(watched, event)

        modifiers = event.modifiers()
        required = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        if event.key() == Qt.Key.Key_D and modifiers == required:
            self.delete_current_source_line(watched)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    @staticmethod
    def delete_current_source_line(editor: LatexEditor) -> None:
        """Delete the complete Source line containing the cursor."""
        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            return

        cursor = editor.textCursor()
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        has_next_block = cursor.block().next().isValid()
        has_previous_block = cursor.block().previous().isValid()

        cursor.beginEditBlock()
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.removeSelectedText()
        if has_next_block:
            cursor.deleteChar()
        elif has_previous_block:
            cursor.deletePreviousChar()
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        editor.ensureCursorVisible()

    def escape_selected_underscores(self) -> None:
        """Replace every unescaped underscore in the current Source selection."""
        editor = self._editor_panel.current_editor()
        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            return

        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return

        selected = cursor.selectedText().replace("\u2029", "\n")
        escaped = self._escape_underscores(selected)
        if escaped == selected:
            return

        selection_start = cursor.selectionStart()
        cursor.beginEditBlock()
        cursor.insertText(escaped)
        cursor.endEditBlock()
        selection_end = cursor.position()
        cursor.setPosition(selection_start)
        cursor.setPosition(
            selection_end,
            QTextCursor.MoveMode.KeepAnchor,
        )
        editor.setTextCursor(cursor)

    @staticmethod
    def _escape_underscores(text: str) -> str:
        result: list[str] = []
        backslash_run = 0
        for character in text:
            if character == "_":
                if backslash_run % 2 == 0:
                    result.append("\\")
                result.append("_")
                backslash_run = 0
                continue

            result.append(character)
            if character == "\\":
                backslash_run += 1
            else:
                backslash_run = 0
        return "".join(result)
