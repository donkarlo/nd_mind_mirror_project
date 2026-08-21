"""Insert Unicode characters and LaTeX wrappers into the active LaTeX editor."""

from PySide6.QtCore import QObject
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class LatexInsertionController(QObject):
    """Apply toolbar insertions to either Source or Visual mode without changing source ownership."""

    def __init__(self, editor_panel, parent=None) -> None:
        """Keep a reference to the shared editor panel used to find the active LaTeX editor."""
        super().__init__(parent)
        self._editor_panel = editor_panel

    def insert_character(self, character: str) -> None:
        """Insert one Unicode character at the active Source or Visual cursor."""
        editor = self._active_latex_editor()
        if editor is None or not character:
            return
        target = editor._visual_editor if editor.edit_mode == "visual" else editor
        cursor = target.textCursor()
        cursor.insertText(str(character))
        target.setTextCursor(cursor)
        target.ensureCursorVisible()
        target.setFocus()

    def insert_iffalse(self) -> None:
        """Wrap the active selection in iffalse or insert the Dativ plural template when empty."""
        editor = self._active_latex_editor()
        if editor is None:
            return

        was_visual = editor.edit_mode == "visual"
        if was_visual:
            editor.set_edit_mode("source")

        cursor = editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n")
        body = selected if selected else "Dativ plural"
        start = min(cursor.anchor(), cursor.position())
        prefix = r"\iffalse "
        suffix = r"\fi"
        cursor.insertText(prefix + body + suffix)

        if not selected:
            cursor.setPosition(start + len(prefix))
            cursor.setPosition(
                start + len(prefix) + len(body),
                QTextCursor.MoveMode.KeepAnchor,
            )
            editor.setTextCursor(cursor)

        if was_visual:
            editor.set_edit_mode("visual")
        else:
            editor.ensureCursorVisible()
            editor.setFocus()

    def _active_latex_editor(self) -> LatexEditor | None:
        """Return the active LaTeX editor or None when another file type is selected."""
        editor = self._editor_panel.current_editor()
        return editor if isinstance(editor, LatexEditor) else None
