"""Draw logical source-line numbers without numbering soft-wrapped visual rows."""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget


class LogicalLineNumberOverlay(QWidget):
    """Reserve and paint one logical line number for an active Source editor."""

    _MIN_WIDTH = 34
    _HORIZONTAL_PADDING = 10

    def __init__(self, editor) -> None:
        """Attach a logical-line gutter to one QTextEdit-compatible Source editor."""
        super().__init__(editor)
        self._editor = editor
        self._base_margins = editor.viewportMargins()
        self._gutter_width = 0
        self._active = True
        self._signals_connected = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        editor.installEventFilter(self)
        editor.viewport().installEventFilter(self)
        self._connect_updates()

        self._update_width()
        self.show()
        self.raise_()

    def set_active(self, active: bool) -> None:
        """Suspend all Source gutter work while another edit mode is active."""
        value = bool(active)
        if value == self._active:
            return
        self._active = value
        if not value:
            self._disconnect_updates()
            self.hide()
            return

        self._connect_updates()
        self._update_width()
        self.show()
        self.raise_()
        self._refresh()

    def _connect_updates(self) -> None:
        """Connect Source-only signals exactly once while the gutter is active."""
        if self._signals_connected:
            return
        self._editor.verticalScrollBar().valueChanged.connect(self._refresh)
        self._editor.document().blockCountChanged.connect(self._update_width)
        self._editor.textChanged.connect(self._refresh)
        self._signals_connected = True

    def _disconnect_updates(self) -> None:
        """Disconnect Source-only signals so Visual edits perform no gutter work."""
        if not self._signals_connected:
            return
        try:
            self._editor.verticalScrollBar().valueChanged.disconnect(self._refresh)
        except (RuntimeError, TypeError):
            pass
        try:
            self._editor.document().blockCountChanged.disconnect(self._update_width)
        except (RuntimeError, TypeError):
            pass
        try:
            self._editor.textChanged.disconnect(self._refresh)
        except (RuntimeError, TypeError):
            pass
        self._signals_connected = False

    def eventFilter(self, watched, event) -> bool:
        """Keep the gutter aligned only while its Source presentation is active."""
        if not self._active:
            return super().eventFilter(watched, event)
        if event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.FontChange,
            QEvent.Type.LayoutRequest,
        }:
            self._update_width()
            self._refresh()
        return super().eventFilter(watched, event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint only the first visual row of each logical QTextBlock."""
        del event
        if not self._active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        palette = self._editor.palette()
        color = palette.color(QPalette.ColorRole.PlaceholderText)
        if not color.isValid():
            color = QColor("#7a7a7a")
        painter.setPen(color)

        font = self._editor.font()
        point_size = font.pointSizeF()
        if point_size > 0:
            font.setPointSizeF(max(point_size * 0.78, 7.0))
        painter.setFont(font)
        metrics = QFontMetricsF(font)

        viewport = self._editor.viewport()
        first_cursor = self._editor.cursorForPosition(QPoint(2, 0))
        block = first_cursor.block()
        if block.previous().isValid():
            block = block.previous()

        viewport_height = float(viewport.height())
        while block.isValid():
            cursor = self._editor.textCursor()
            cursor.setPosition(block.position())
            rectangle = self._editor.cursorRect(cursor)
            top = float(rectangle.top())

            if top > viewport_height + metrics.height():
                break

            if top + metrics.height() >= 0:
                text_rect = QRectF(
                    0.0,
                    top,
                    float(max(self._gutter_width - 6, 1)),
                    float(max(metrics.height(), rectangle.height())),
                )
                painter.drawText(
                    text_rect,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                    str(block.blockNumber() + 1),
                )
            block = block.next()

    def _update_width(self, *args) -> None:
        """Resize the reserved gutter when the active Source gains another digit."""
        del args
        if not self._active:
            return
        digits = max(2, len(str(max(self._editor.document().blockCount(), 1))))
        metrics = QFontMetricsF(self._editor.font())
        desired = max(
            self._MIN_WIDTH,
            int(math.ceil(metrics.horizontalAdvance("9" * digits)))
            + self._HORIZONTAL_PADDING,
        )
        if desired != self._gutter_width:
            self._gutter_width = desired
            margins = self._base_margins
            self._editor.setViewportMargins(
                margins.left() + self._gutter_width,
                margins.top(),
                margins.right(),
                margins.bottom(),
            )
        self._position()

    def _position(self) -> None:
        """Place the active gutter inside the area immediately left of the viewport."""
        if not self._active:
            return
        geometry = self._editor.viewport().geometry()
        self.setGeometry(
            geometry.left() - self._gutter_width,
            geometry.top(),
            self._gutter_width,
            geometry.height(),
        )
        self.raise_()

    def _refresh(self, *args) -> None:
        """Repaint the active Source gutter after scroll or source changes."""
        del args
        if not self._active:
            return
        self._position()
        self.update()
