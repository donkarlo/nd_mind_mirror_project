import re
from typing import Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QTextBlockFormat,
    QTextCursor,
    QTextFormat,
    QTextOption,
    QWheelEvent,
)
from PySide6.QtWidgets import QTextEdit


class TextEditor(QTextEdit):
    """Plain-source editor with rich visual layout only.

    QTextEdit is used instead of QPlainTextEdit because QTextDocument's normal
    layout honours QTextBlockFormat line height, paragraph margins, and first
    line indentation. The editor still accepts and saves plain text only.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._font_min_size = 6
        self._font_max_size = 40
        self._soft_wrap = True
        self._line_height_percent = 200
        self._wrap_marker = "↳"
        self._wrap_marker_color = QColor("#9aa0a6")
        self._wrap_marker_margin = 18
        self._current_line_color = QColor("#eaf4ff")
        self._search_highlight_ranges: list[tuple[int, int, bool]] = []
        self._base_document_margin = self.document().documentMargin()
        self._applying_block_layout = False
        self._block_direction_resolver: Callable[[str], Qt.LayoutDirection] | None = None

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setReadOnly(False)
        self.setAcceptRichText(False)
        self.setCursorWidth(2)
        self.setTabStopDistance(32.0)
        self.setMinimumWidth(0)

        font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )
        font.setPointSize(16)
        self.setFont(font)

        self.cursorPositionChanged.connect(
            self._highlight_current_line
        )

        self._block_layout_timer = QTimer(self)
        self._block_layout_timer.setSingleShot(True)
        self._block_layout_timer.setInterval(25)
        self._pending_layout_start = 0
        self._pending_layout_end = 0
        self._block_layout_timer.timeout.connect(
            self._apply_pending_block_layout_preferences
        )
        self.document().contentsChange.connect(
            self._schedule_block_layout_update_for_change
        )

        self.apply_visual_preferences(
            soft_wrap=True,
            wrap_marker="↳",
            wrap_marker_color="#9aa0a6",
            wrap_marker_margin=18,
            current_line_highlight="#eaf4ff",
            cursor_width=2,
        )

    def apply_font_preferences(
        self,
        font_family: str,
        font_size: int,
        font_min_size: int,
        font_max_size: int,
    ) -> None:
        self._font_min_size = max(int(font_min_size), 1)
        self._font_max_size = max(
            int(font_max_size),
            self._font_min_size,
        )

        if font_family.strip():
            font = self.font()
            font.setFamily(font_family.strip())
        else:
            font = QFontDatabase.systemFont(
                QFontDatabase.SystemFont.FixedFont
            )

        font.setPointSize(
            max(
                self._font_min_size,
                min(int(font_size), self._font_max_size),
            )
        )
        self.setFont(font)
        self._apply_block_layout_preferences()

    def apply_line_height(self, percent: int) -> None:
        self._line_height_percent = max(
            60,
            min(int(percent), 300),
        )
        self._apply_block_layout_preferences()

    def go_to_line(
        self,
        line_number: int,
        align_top: bool = True,
    ) -> None:
        block = self.document().findBlockByNumber(
            max(int(line_number) - 1, 0)
        )
        if not block.isValid():
            return

        cursor = QTextCursor(block)
        self.setTextCursor(cursor)

        if align_top:
            # QTextEdit's vertical scrollbar is pixel based. Move the current
            # cursor rectangle to the top edge rather than merely ensuring it
            # is somewhere inside the viewport. This makes Structure clicks
            # deterministic and also gives SyncTeX a stable source anchor.
            self.ensureCursorVisible()
            rectangle = self.cursorRect(cursor)
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(
                scrollbar.value() + rectangle.top()
            )
        else:
            self.ensureCursorVisible()

        self.setFocus()

    def view_state(self) -> dict[str, int]:
        cursor = self.textCursor()
        return {
            "cursor": int(cursor.position()),
            "vertical": int(self.verticalScrollBar().value()),
            "horizontal": int(self.horizontalScrollBar().value()),
        }

    def restore_view_state(self, state: dict | None) -> None:
        if not isinstance(state, dict):
            return

        try:
            position = int(state.get("cursor", 0))
            vertical = int(state.get("vertical", 0))
            horizontal = int(state.get("horizontal", 0))
        except (TypeError, ValueError):
            return

        cursor = self.textCursor()
        cursor.setPosition(
            max(
                0,
                min(
                    position,
                    max(self.document().characterCount() - 1, 0),
                ),
            )
        )
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(vertical)
        self.horizontalScrollBar().setValue(horizontal)

    def first_visible_source_position(self) -> tuple[int, int]:
        cursor = self.cursorForPosition(QPoint(2, 2))
        return (
            max(cursor.blockNumber() + 1, 1),
            max(cursor.positionInBlock() + 1, 1),
        )

    def set_block_direction_resolver(
        self,
        resolver: Callable[[str], Qt.LayoutDirection] | None,
    ) -> None:
        """Set a per-source-line visual direction resolver.

        The resolver changes only QTextBlock layout metadata. The plain source
        returned by toPlainText() is never modified.
        """
        self._block_direction_resolver = resolver
        self._apply_block_layout_preferences()

    def _block_direction(self, text: str) -> Qt.LayoutDirection:
        if self._block_direction_resolver is None:
            return Qt.LayoutDirection.LeftToRight

        try:
            direction = self._block_direction_resolver(text)
        except Exception:
            return Qt.LayoutDirection.LeftToRight

        if direction == Qt.LayoutDirection.RightToLeft:
            return Qt.LayoutDirection.RightToLeft
        return Qt.LayoutDirection.LeftToRight

    def apply_visual_preferences(
        self,
        soft_wrap: bool,
        wrap_marker: str,
        wrap_marker_color: str,
        wrap_marker_margin: int,
        current_line_highlight: str,
        cursor_width: int,
    ) -> None:
        self._soft_wrap = bool(soft_wrap)
        self._wrap_marker = wrap_marker or "↳"
        self._wrap_marker_color = QColor(wrap_marker_color)
        self._wrap_marker_margin = max(
            int(wrap_marker_margin),
            0,
        )
        self._current_line_color = QColor(
            current_line_highlight
        )

        self.setCursorWidth(max(int(cursor_width), 1))

        if self._soft_wrap:
            self.setLineWrapMode(
                QTextEdit.LineWrapMode.WidgetWidth
            )
            self.setWordWrapMode(
                QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
            )
            self.document().setDocumentMargin(
                self._base_document_margin
                + self._wrap_marker_margin
            )
        else:
            self.setLineWrapMode(
                QTextEdit.LineWrapMode.NoWrap
            )
            self.document().setDocumentMargin(
                self._base_document_margin
            )

        self._apply_block_layout_preferences()
        self._highlight_current_line()
        self.viewport().update()

    def _schedule_block_layout_update_for_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        if self._applying_block_layout:
            return

        start = max(int(position), 0)
        end = max(
            start,
            start + max(int(chars_added), int(chars_removed), 1),
        )

        if not self._block_layout_timer.isActive():
            self._pending_layout_start = start
            self._pending_layout_end = end
        else:
            self._pending_layout_start = min(
                self._pending_layout_start,
                start,
            )
            self._pending_layout_end = max(
                self._pending_layout_end,
                end,
            )
        self._block_layout_timer.start()

    def _apply_pending_block_layout_preferences(self) -> None:
        if self._applying_block_layout:
            return

        document = self.document()
        start_block = document.findBlock(
            max(self._pending_layout_start - 1, 0)
        )
        end_block = document.findBlock(
            min(
                self._pending_layout_end + 1,
                max(document.characterCount() - 1, 0),
            )
        )
        self._apply_block_layout_range(start_block, end_block)

    def _apply_block_layout_preferences(self) -> None:
        """Apply visual line spacing and hanging soft-wrap indentation.

        The first visual line keeps the source whitespace exactly where it
        already places the text. Continuation lines receive a left margin equal
        to the width of that leading whitespace. The source string is never
        changed; toPlainText() remains byte-for-byte equivalent apart from the
        normal newline handling of Qt.
        """
        if self._applying_block_layout:
            return

        # A full preference application supersedes any queued incremental
        # pass (for example the contentsChange emitted by setPlainText).
        # Cancelling it avoids traversing a large document twice on load.
        self._block_layout_timer.stop()
        self._pending_layout_start = 0
        self._pending_layout_end = 0

        document = self.document()
        self._apply_block_layout_range(
            document.begin(),
            document.lastBlock(),
        )

    def _apply_block_layout_range(
        self,
        start_block,
        end_block,
    ) -> None:
        if self._applying_block_layout or not start_block.isValid():
            return

        self._applying_block_layout = True
        document = self.document()
        was_modified = document.isModified()
        editor_signals_were_blocked = self.signalsBlocked()
        self.blockSignals(True)

        try:
            metrics = QFontMetricsF(self.font())
            block = start_block
            end_number = (
                end_block.blockNumber()
                if end_block.isValid()
                else start_block.blockNumber()
            )

            while block.isValid() and block.blockNumber() <= end_number:
                self._apply_layout_to_block(block, metrics)
                block = block.next()

            document.setModified(was_modified)
            dirty_start = max(start_block.position(), 0)
            if end_block.isValid():
                dirty_end = end_block.position() + end_block.length()
            else:
                dirty_end = dirty_start + 1
            document.markContentsDirty(
                dirty_start,
                max(dirty_end - dirty_start, 1),
            )
        finally:
            self.blockSignals(editor_signals_were_blocked)
            self._applying_block_layout = False

        self.viewport().update()

    def _apply_layout_to_block(
        self,
        block,
        metrics: QFontMetricsF,
    ) -> None:
        text = block.text()
        leading = re.match(r"^[ \t]*", text)
        prefix = leading.group(0) if leading else ""
        hanging_indent = (
            self._indent_width_pixels(prefix, metrics)
            if self._soft_wrap
            else 0.0
        )

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
            block_format.setLeftMargin(0.0)
            if hanging_indent > 0.0:
                block_format.setRightMargin(hanging_indent)
                block_format.setTextIndent(-hanging_indent)
            else:
                block_format.setRightMargin(0.0)
                block_format.setTextIndent(0.0)
        else:
            block_format.setAlignment(
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignAbsolute
            )
            block_format.setRightMargin(0.0)
            if hanging_indent > 0.0:
                block_format.setLeftMargin(hanging_indent)
                block_format.setTextIndent(-hanging_indent)
            else:
                block_format.setLeftMargin(0.0)
                block_format.setTextIndent(0.0)

        cursor = QTextCursor(block)
        cursor.setBlockFormat(block_format)

    def _indent_width_pixels(
        self,
        prefix: str,
        metrics: QFontMetricsF,
    ) -> float:
        if not prefix:
            return 0.0

        width = 0.0
        tab_stop = max(float(self.tabStopDistance()), 1.0)

        for character in prefix:
            if character == "\t":
                width += tab_stop - (width % tab_stop)
            else:
                width += metrics.horizontalAdvance(character)

        return width

    def wheelEvent(self, event: QWheelEvent) -> None:
        if bool(
            event.modifiers()
            & Qt.KeyboardModifier.ControlModifier
        ):
            direction = event.angleDelta().y()

            if direction == 0:
                event.accept()
                return

            font = self.font()
            current_size = font.pointSize()

            if current_size <= 0:
                current_size = 16

            next_size = (
                current_size + 1
                if direction > 0
                else current_size - 1
            )
            next_size = max(
                self._font_min_size,
                min(next_size, self._font_max_size),
            )

            font.setPointSize(next_size)
            self.setFont(font)
            self._apply_block_layout_preferences()
            self.viewport().update()
            event.accept()
            return

        super().wheelEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        # QTextEdit hides its native caret as soon as focus leaves the editor.
        # Keep a non-blinking passive caret visible at the last editing
        # position so the user never loses the source anchor while working in
        # another panel or application.
        self.viewport().update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        if not self.hasFocus():
            cursor = self.textCursor()
            if not cursor.hasSelection():
                rect = self.cursorRect(cursor)
                caret_painter = QPainter(self.viewport())
                caret_painter.setPen(self.palette().text().color())
                x = rect.left()
                caret_painter.drawLine(x, rect.top(), x, rect.bottom())
                # Explicitly end this painter before the wrap-marker painter
                # below is created. Two active QPainters on the same viewport
                # can make Qt render a black widget or abort on some drivers.
                caret_painter.end()

        if (
            not self._soft_wrap
            or not self._wrap_marker
            or self._wrap_marker_margin <= 0
        ):
            return

        painter = QPainter(self.viewport())
        painter.setPen(self._wrap_marker_color)
        painter.setFont(self.font())

        document_layout = self.document().documentLayout()
        scroll_y = self.verticalScrollBar().value()
        viewport_bottom = self.viewport().height()

        # Start close to the first visible block instead of walking the whole
        # document on every repaint.
        block = self.cursorForPosition(QPoint(0, 0)).block()
        if not block.isValid():
            block = self.document().begin()

        while block.isValid():
            block_rect = document_layout.blockBoundingRect(block)
            block_top = block_rect.top() - scroll_y

            if block_top > viewport_bottom:
                break

            layout = block.layout()
            if (
                block.isVisible()
                and layout is not None
                and layout.lineCount() > 1
            ):
                for line_index in range(1, layout.lineCount()):
                    line = layout.lineAt(line_index)
                    baseline = (
                        block_top
                        + line.y()
                        + line.ascent()
                    )
                    painter.drawText(
                        2,
                        int(baseline),
                        self._wrap_marker,
                    )

            block = block.next()

        painter.end()


    def set_search_highlights(
        self,
        ranges: list[tuple[int, int]],
        current_index: int = -1,
    ) -> None:
        self._search_highlight_ranges = [
            (int(start), int(end), index == int(current_index))
            for index, (start, end) in enumerate(ranges)
            if int(end) > int(start)
        ]
        self._highlight_current_line()

    def clear_search_highlights(self) -> None:
        if not self._search_highlight_ranges:
            return
        self._search_highlight_ranges = []
        self._highlight_current_line()

    def _highlight_current_line(self) -> None:
        selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(
                self._current_line_color
            )
            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection,
                True,
            )
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)

        document_limit = max(self.document().characterCount() - 1, 0)
        for start, end, is_current in self._search_highlight_ranges:
            if start < 0 or start >= document_limit:
                continue
            cursor = QTextCursor(self.document())
            cursor.setPosition(min(start, document_limit))
            cursor.setPosition(
                min(end, document_limit),
                QTextCursor.MoveMode.KeepAnchor,
            )
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(
                QColor("#ffd27a" if is_current else "#fff3a6")
            )
            selections.append(selection)

        self.setExtraSelections(selections)
