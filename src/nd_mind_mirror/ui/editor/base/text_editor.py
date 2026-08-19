import re

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
        self._line_height_percent = 120
        self._wrap_marker = "↳"
        self._wrap_marker_color = QColor("#9aa0a6")
        self._wrap_marker_margin = 18
        self._current_line_color = QColor("#eaf4ff")
        self._base_document_margin = self.document().documentMargin()
        self._applying_block_layout = False

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setReadOnly(False)
        self.setAcceptRichText(False)
        self.setCursorWidth(2)
        self.setTabStopDistance(32.0)
        self.setMinimumWidth(0)

        font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )
        font.setPointSize(11)
        self.setFont(font)

        self.cursorPositionChanged.connect(
            self._highlight_current_line
        )

        self._block_layout_timer = QTimer(self)
        self._block_layout_timer.setSingleShot(True)
        self._block_layout_timer.setInterval(25)
        self._block_layout_timer.timeout.connect(
            self._apply_block_layout_preferences
        )
        self.textChanged.connect(
            self._schedule_block_layout_update
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

    def _schedule_block_layout_update(self) -> None:
        if self._applying_block_layout:
            return
        self._block_layout_timer.start()

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

        self._applying_block_layout = True
        document = self.document()
        was_modified = document.isModified()
        editor_signals_were_blocked = self.signalsBlocked()
        self.blockSignals(True)

        try:
            metrics = QFontMetricsF(self.font())
            block = document.begin()

            while block.isValid():
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

                if hanging_indent > 0.0:
                    # QTextEdit's document layout honours both properties:
                    # leftMargin applies to every visual line, while textIndent
                    # adjusts the first visual line. Because the actual source
                    # spaces remain in the block, cancelling the margin on the
                    # first visual line yields a true hanging indent:
                    #
                    # first line:  +H margin -H textIndent +H source spaces = H
                    # wraps:       +H margin                           = H
                    block_format.setLeftMargin(hanging_indent)
                    block_format.setTextIndent(-hanging_indent)
                else:
                    block_format.setLeftMargin(0.0)
                    block_format.setTextIndent(0.0)

                cursor = QTextCursor(block)
                cursor.setBlockFormat(block_format)
                block = block.next()

            document.setModified(was_modified)
            document.markContentsDirty(
                0,
                max(document.characterCount(), 1),
            )
        finally:
            self.blockSignals(editor_signals_were_blocked)
            self._applying_block_layout = False

        self.viewport().update()

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
                current_size = 11

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

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

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

        self.setExtraSelections(selections)
