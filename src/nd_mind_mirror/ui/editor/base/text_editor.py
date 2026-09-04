from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.ui.editor.base.text_editor_rich_core import (
    TextEditor as RichTextEditor,
)


class TextEditor(RichTextEditor):
    """Use Qt's native rich source layout with a reduced-cost large mode.

    QTextEdit keeps the paragraph geometry required by Persian/Arabic source
    direction and inline figure reservations. Large LaTeX files are bounded by
    LargeLatexEditor, so this class never needs a custom QTextDocumentLayout.
    """

    _NORMAL_LAYOUT_DEBOUNCE_MS = 25
    _LARGE_LAYOUT_DEBOUNCE_MS = 90

    def __init__(self, parent=None) -> None:
        # RichTextEditor applies block formatting during its constructor, so
        # this flag must exist before dynamic dispatch reaches our override.
        self._large_document_mode = False
        super().__init__(parent)

    @property
    def large_document_mode(self) -> bool:
        return bool(self._large_document_mode)

    def set_large_document_mode(self, enabled: bool) -> None:
        value = bool(enabled)
        if value == self._large_document_mode:
            return
        self._large_document_mode = value
        self._block_layout_timer.setInterval(
            self._LARGE_LAYOUT_DEBOUNCE_MS
            if value
            else self._NORMAL_LAYOUT_DEBOUNCE_MS
        )
        self.viewport().update()

    def _apply_layout_to_block(self, block, metrics) -> None:
        if not self._large_document_mode:
            super()._apply_layout_to_block(block, metrics)
            return

        # Keep native paragraph direction, alignment, line spacing, and the
        # top margin used by Source figure previews. Hanging-indent measurement
        # is skipped for large windows because it is decorative and relatively
        # expensive while typing.
        text = block.text()
        block_format = block.blockFormat()
        block_format.setLineHeight(
            float(self._line_height_percent),
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )

        direction = self._block_direction(text)
        block_format.setLayoutDirection(direction)
        if direction == Qt.LayoutDirection.RightToLeft:
            block_format.setAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignAbsolute
            )
        else:
            block_format.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignAbsolute
            )

        block_format.setLeftMargin(0.0)
        block_format.setRightMargin(0.0)
        block_format.setTextIndent(0.0)
        QTextCursor(block).setBlockFormat(block_format)

    def paintEvent(self, event) -> None:
        if not self._large_document_mode:
            super().paintEvent(event)
            return

        # Let QTextEdit paint the source natively. Large mode omits the custom
        # indent-guide and soft-wrap-marker painters, which are decorative.
        QTextEdit.paintEvent(self, event)

        if self.hasFocus():
            return
        cursor = self.textCursor()
        if cursor.hasSelection():
            return

        rectangle = self.cursorRect(cursor)
        painter = QPainter(self.viewport())
        painter.setPen(self.palette().text().color())
        painter.drawLine(
            rectangle.left(),
            rectangle.top(),
            rectangle.left(),
            rectangle.bottom(),
        )
        painter.end()
