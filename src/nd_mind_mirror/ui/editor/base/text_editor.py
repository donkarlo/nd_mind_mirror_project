from PySide6.QtCore import Qt
from PySide6.QtGui import QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from nd_mind_mirror.ui.editor.base.text_editor_rich_core import (
    TextEditor as RichTextEditor,
)
from nd_mind_mirror.ui.editor.cursor.caret_scroll_margin_controller import (
    CaretScrollMarginController,
)
from nd_mind_mirror.ui.editor.cursor.cursor_appearance_controller import (
    CursorAppearanceController,
)


class TextEditor(RichTextEditor):
    """Use Qt's native rich source layout with a reduced-cost large mode.

    QTextEdit keeps the paragraph geometry required by Persian/Arabic source
    direction and inline figure reservations. Large LaTeX files are bounded by
    LargeLatexEditor, so rich layout work is restricted to a small Source window.
    """

    _NORMAL_LAYOUT_DEBOUNCE_MS = 25
    _LARGE_LAYOUT_DEBOUNCE_MS = 90

    def __init__(self, parent=None) -> None:
        # RichTextEditor applies block formatting during its constructor, so
        # this flag must exist before dynamic dispatch reaches our override.
        self._large_document_mode = False
        super().__init__(parent)
        self._cursor_appearance = CursorAppearanceController(self)
        self._caret_scroll_margin = CaretScrollMarginController(self)

    def apply_cursor_preferences(
        self,
        *,
        color: str,
        size_percent: int,
        thickness: int,
    ) -> None:
        """Apply configurable caret appearance to this source editor."""
        self._cursor_appearance.apply(
            color=color,
            size_percent=size_percent,
            thickness=thickness,
        )

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

    def _schedule_block_layout_update_for_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        """Avoid rewriting unchanged rich block formats during large-file typing."""
        if not self._large_document_mode:
            super()._schedule_block_layout_update_for_change(
                position,
                chars_removed,
                chars_added,
            )
            return

        if int(chars_removed) == 0 and int(chars_added) == 0:
            return

        document = self.document()
        block = document.findBlock(max(int(position), 0))
        if not block.isValid():
            super()._schedule_block_layout_update_for_change(
                position,
                chars_removed,
                chars_added,
            )
            return

        block_format = block.blockFormat()
        expected_direction = self._block_direction(block.text())
        direction_is_current = (
            block_format.layoutDirection() == expected_direction
        )
        line_height_is_current = (
            abs(
                float(block_format.lineHeight())
                - float(self._line_height_percent)
            )
            < 0.5
        )
        if direction_is_current and line_height_is_current:
            return

        super()._schedule_block_layout_update_for_change(
            position,
            chars_removed,
            chars_added,
        )

    def _handle_common_editor_shortcut(self, event) -> bool:
        """Handle source-only line deletion before the shared shortcuts."""
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
            self._delete_current_line()
            event.accept()
            return True
        return super()._handle_common_editor_shortcut(event)

    def _delete_current_line(self) -> None:
        """Delete the logical source line containing the active cursor."""
        cursor = self.textCursor()
        block = cursor.block()
        if not block.isValid():
            return

        document = self.document()
        start = block.position()
        next_block = block.next()

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
        edit.endEditBlock()

        restored = QTextCursor(document)
        restored.setPosition(
            min(max(start, 0), max(document.characterCount() - 1, 0))
        )
        self.setTextCursor(restored)
        self.ensureCursorVisible()

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

