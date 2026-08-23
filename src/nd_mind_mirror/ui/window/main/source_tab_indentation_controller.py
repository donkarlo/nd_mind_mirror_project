"""Give every source editor configurable space-based Tab and Shift+Tab indentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor

from nd_mind_mirror.ui.editor.base.text_editor import TextEditor


class SourceTabIndentationController:
    """Normalize source Tab and Backtab behavior around each editor's configured tab size."""

    _installed = False

    @classmethod
    def install(cls) -> None:
        """Patch the shared TextEditor key handler once for all source-editor subclasses."""
        if cls._installed:
            return

        original_key_press = TextEditor.keyPressEvent

        def key_press(editor: TextEditor, event: QKeyEvent) -> None:
            if cls._handle_tab_key(editor, event):
                return
            original_key_press(editor, event)

        TextEditor.keyPressEvent = key_press
        cls._installed = True

    @classmethod
    def _handle_tab_key(cls, editor: TextEditor, event: QKeyEvent) -> bool:
        """Indent or outdent by one configured space unit when Tab/Backtab is pressed."""
        modifiers = event.modifiers()
        if bool(
            modifiers
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return False

        key = event.key()
        outdent = key == Qt.Key.Key_Backtab or (
            key == Qt.Key.Key_Tab
            and bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        )
        if key not in {Qt.Key.Key_Tab, Qt.Key.Key_Backtab}:
            return False

        if outdent:
            cls._outdent(editor)
        else:
            cls._indent(editor)
        event.accept()
        return True

    @classmethod
    def _indent(cls, editor: TextEditor) -> None:
        """Insert one tab-size of spaces or indent every selected logical line."""
        cursor = editor.textCursor()
        spaces = " " * max(int(editor.tab_size), 1)
        if not cursor.hasSelection():
            cursor.insertText(spaces)
            editor.setTextCursor(cursor)
            return

        blocks = cls._selected_blocks(editor, cursor)
        saved_cursor = QTextCursor(cursor)
        group = QTextCursor(editor.document())
        group.beginEditBlock()
        try:
            for block in reversed(blocks):
                edit = QTextCursor(block)
                edit.movePosition(QTextCursor.MoveOperation.StartOfBlock)
                edit.insertText(spaces)
        finally:
            group.endEditBlock()
        editor.setTextCursor(saved_cursor)

    @classmethod
    def _outdent(cls, editor: TextEditor) -> None:
        """Remove at most one configured indentation unit from selected logical lines."""
        cursor = editor.textCursor()
        blocks = cls._selected_blocks(editor, cursor)
        saved_cursor = QTextCursor(cursor)
        tab_size = max(int(editor.tab_size), 1)
        group = QTextCursor(editor.document())
        group.beginEditBlock()
        try:
            for block in reversed(blocks):
                text = block.text()
                remove_count = cls._leading_remove_count(text, tab_size)
                if remove_count <= 0:
                    continue
                edit = QTextCursor(block)
                start = block.position()
                edit.setPosition(start)
                edit.setPosition(
                    start + remove_count,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                edit.removeSelectedText()
        finally:
            group.endEditBlock()
        editor.setTextCursor(saved_cursor)

    @staticmethod
    def _leading_remove_count(text: str, tab_size: int) -> int:
        """Return how many leading characters make one removable indentation unit."""
        if text.startswith("\t"):
            return 1
        leading_spaces = len(text) - len(text.lstrip(" "))
        return min(leading_spaces, max(int(tab_size), 1))

    @staticmethod
    def _selected_blocks(editor: TextEditor, cursor: QTextCursor):
        """Return logical QTextBlocks touched by the current selection or cursor line."""
        document = editor.document()
        start = min(cursor.anchor(), cursor.position())
        end = max(cursor.anchor(), cursor.position())
        start_block = document.findBlock(start)

        if not cursor.hasSelection():
            return [start_block] if start_block.isValid() else []

        end_probe = max(end - 1, start)
        end_block = document.findBlock(end_probe)
        blocks = []
        block = start_block
        while block.isValid():
            blocks.append(block)
            if block == end_block:
                break
            block = block.next()
        return blocks
