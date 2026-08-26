"""Keep the last text caret visible when keyboard focus moves outside an editor."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QPaintEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget


class PersistentCaretOverlay(QWidget):
    """Draw a steady non-focus caret above Source or Visual text without stealing mouse input."""

    _LEFT_GUTTER_WIDTH = 18

    def __init__(self, editor: QTextEdit) -> None:
        """Attach a transparent caret layer to one text editor viewport."""
        super().__init__(editor.viewport())
        self._editor = editor
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        editor.viewport().installEventFilter(self)
        editor.cursorPositionChanged.connect(self.update)
        editor.selectionChanged.connect(self.update)
        editor.textChanged.connect(self.update)
        editor.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        editor.horizontalScrollBar().valueChanged.connect(self._on_scroll_changed)

        application = QApplication.instance()
        if application is not None:
            application.focusChanged.connect(self._on_application_focus_changed)

        self._sync_geometry()
        self.show()
        self.raise_()

    @Slot(int)
    def _on_scroll_changed(self, _value: int) -> None:
        """Refresh the overlay after editor scrolling."""
        self.update()

    @Slot(object, object)
    def _on_application_focus_changed(self, _old, _new) -> None:
        """Refresh without leaving a lambda callback alive after deletion."""
        self.update()

    def eventFilter(self, watched, event) -> bool:
        """Keep the overlay sized to the viewport and refreshed across layout changes."""
        if watched is self._editor.viewport():
            event_type = event.type()
            if event_type in {
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.LayoutRequest,
            }:
                self._sync_geometry()
                self.show()
                self.raise_()
        return False

    def _sync_geometry(self) -> None:
        """Cover the text area while leaving the bookmark gutter unobscured."""
        viewport = self._editor.viewport()
        left = min(self._LEFT_GUTTER_WIDTH, max(viewport.width() - 1, 0))
        self.setGeometry(
            left,
            0,
            max(viewport.width() - left, 0),
            viewport.height(),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the current caret steadily whenever Qt hides its blinking focus caret."""
        del event
        editor = self._editor
        if editor.hasFocus() or not editor.isVisible():
            return

        cursor_rect = editor.cursorRect(editor.textCursor())
        x = cursor_rect.left() - self.geometry().left()
        if x < -2 or x > self.width() + 2:
            return
        if cursor_rect.bottom() < 0 or cursor_rect.top() > self.height():
            return

        top = max(cursor_rect.top(), 0)
        height = max(cursor_rect.height(), editor.fontMetrics().height(), 2)
        bottom = min(top + height, max(self.height() - 1, 0))
        if bottom <= top:
            return

        color = editor.palette().color(QPalette.ColorRole.Text)
        color.setAlpha(235)
        pen = QPen(color)
        pen.setWidth(max(int(editor.cursorWidth()), 2))

        painter = QPainter(self)
        painter.setPen(pen)
        draw_x = max(0, min(int(x), max(self.width() - 1, 0)))
        painter.drawLine(draw_x, top, draw_x, bottom)
        painter.end()
