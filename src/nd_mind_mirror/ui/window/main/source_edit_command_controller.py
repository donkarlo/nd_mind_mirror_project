"""Source and Visual editor commands requested by the migration workflow."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_visual_editor import LatexVisualEditor
from nd_mind_mirror.ui.panel.editor.editor_panel import EditorPanel


class SourceEditCommandController(QObject):
    """Own editor-only line deletion and Source underscore escaping."""

    def __init__(self, editor_panel: EditorPanel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)

        modifiers = event.modifiers()
        required = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        if event.key() != Qt.Key.Key_D or modifiers != required:
            return super().eventFilter(watched, event)

        if isinstance(watched, LatexEditor) and watched.edit_mode == "source":
            self.delete_current_source_line(watched)
            event.accept()
            return True

        if isinstance(watched, LatexVisualEditor):
            owner = watched.parentWidget()
            if isinstance(owner, LatexEditor) and owner.edit_mode == "visual":
                self.delete_current_visual_line(owner, watched)
                event.accept()
                return True

        return super().eventFilter(watched, event)

    @classmethod
    def delete_current_source_line(cls, editor: LatexEditor) -> None:
        """Delete the complete canonical Source line containing the Source cursor."""
        cls._delete_source_line(editor, editor.textCursor().blockNumber() + 1)

    @classmethod
    def delete_current_visual_line(
        cls,
        editor: LatexEditor,
        visual_editor: LatexVisualEditor,
    ) -> None:
        """Delete the canonical Source line represented by the current Visual cursor."""
        try:
            line_number, _column = visual_editor.current_source_location()
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return
        if not cls._delete_source_line(editor, line_number):
            return

        editor._visual_dirty = True
        editor._refresh_visual_projection()
        try:
            visual_editor.go_to_source_location(
                max(int(line_number), 1),
                1,
                align_top=False,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            pass
        visual_editor.setFocus()
        editor.active_cursor_changed.emit()
        editor.active_view_changed.emit()

    @staticmethod
    def _delete_source_line(editor: LatexEditor, line_number: int) -> bool:
        """Delete one numbered canonical Source block without changing editor mode."""
        block = editor.document().findBlockByNumber(max(int(line_number) - 1, 0))
        if not block.isValid():
            return False

        cursor = QTextCursor(block)
        has_next_block = block.next().isValid()
        has_previous_block = block.previous().isValid()
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
        if editor.edit_mode == "source":
            editor.ensureCursorVisible()
        return True

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
