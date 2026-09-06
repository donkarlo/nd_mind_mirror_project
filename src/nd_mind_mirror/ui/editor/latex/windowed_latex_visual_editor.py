"""Windowed Visual LaTeX editor with explicit current-line deletion."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextBlockFormat, QTextCursor

from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta
from nd_mind_mirror.ui.editor.latex.windowed_latex_visual_editor_core import (
    WindowedLatexVisualEditor as WindowedLatexVisualEditorCore,
)


class WindowedLatexVisualEditor(WindowedLatexVisualEditorCore):
    """Add Ctrl+Shift+D line deletion to the windowed Visual editor."""

    def keyPressEvent(self, event) -> None:
        modifiers = event.modifiers()
        control = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        alt_or_meta = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )
        if (
            control
            and shift
            and not alt_or_meta
            and event.key() == Qt.Key.Key_D
        ):
            self._delete_current_visual_line()
            event.accept()
            return
        super().keyPressEvent(event)

    def _delete_current_visual_line(self) -> None:
        """Delete one Visual block while preserving the following block metadata."""
        cursor = self.textCursor()
        block = cursor.block()
        if not block.isValid():
            return

        document = self.document()
        start = block.position()
        next_block = block.next()
        next_meta = None
        next_format = None
        if next_block.isValid():
            next_meta = self._copy_block_meta(next_block.userData())
            next_format = QTextBlockFormat(next_block.blockFormat())

        edit = QTextCursor(document)
        edit.beginEditBlock()
        if next_block.isValid():
            edit.setPosition(start)
            edit.setPosition(
                next_block.position(),
                QTextCursor.MoveMode.KeepAnchor,
            )
        else:
            previous = block.previous()
            if previous.isValid():
                edit.setPosition(max(start - 1, 0))
                edit.setPosition(
                    start + len(block.text()),
                    QTextCursor.MoveMode.KeepAnchor,
                )
            else:
                edit.select(QTextCursor.SelectionType.Document)
        edit.removeSelectedText()

        survivor = document.findBlock(start)
        if survivor.isValid():
            survivor.setUserData(next_meta)
            format_cursor = QTextCursor(survivor)
            format_cursor.setBlockFormat(
                next_format if next_format is not None else QTextBlockFormat()
            )
        edit.endEditBlock()

        restored = QTextCursor(document)
        restored.setPosition(
            min(max(start, 0), max(document.characterCount() - 1, 0))
        )
        self.setTextCursor(restored)
        self.ensureCursorVisible()

    @staticmethod
    def _copy_block_meta(data) -> _BlockMeta | None:
        """Copy Visual source metadata before QTextBlock removal invalidates it."""
        if not isinstance(data, _BlockMeta):
            return None
        return _BlockMeta(
            kind=data.kind,
            command=data.command,
            raw=data.raw,
            display=data.display,
            depth=data.depth,
            source_line=data.source_line,
            source_segments=list(data.source_segments),
        )
