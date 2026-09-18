"""Control the visible text caret independently from editor text colors."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget


class CursorAppearanceController(QObject):
    """Render a configurable caret overlay for one ``QTextEdit`` instance."""

    def __init__(self, editor: QTextEdit) -> None:
        super().__init__(editor)
        self._editor = editor
        self._color = QColor("#202124")
        self._size_percent = 100
        self._thickness = 2
        self._blink_visible = True

        self._overlay = QWidget(editor.viewport())
        self._overlay.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self._overlay.hide()

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_blink)

        editor.installEventFilter(self)
        editor.viewport().installEventFilter(self)
        editor.cursorPositionChanged.connect(self._on_cursor_changed)
        editor.selectionChanged.connect(self._refresh)
        editor.verticalScrollBar().valueChanged.connect(self._refresh)
        editor.horizontalScrollBar().valueChanged.connect(self._refresh)

        self._hide_native_caret()
        self._restart_blink()
        self._refresh()

    def apply(
        self,
        *,
        color: str,
        size_percent: int,
        thickness: int,
    ) -> None:
        """Apply validated caret appearance without changing editor content."""
        parsed_color = QColor(str(color).strip())
        if not parsed_color.isValid():
            parsed_color = self._editor.palette().text().color()
        self._color = parsed_color
        self._size_percent = max(25, min(int(size_percent), 200))
        self._thickness = max(1, min(int(thickness), 12))
        self._overlay.setStyleSheet(
            f"background-color: {self._color.name(QColor.NameFormat.HexRgb)};"
        )
        self._hide_native_caret()
        self._refresh()

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if watched is self._editor:
            if event_type == QEvent.Type.FocusIn:
                self._restart_blink()
            elif event_type == QEvent.Type.FocusOut:
                self._blink_timer.stop()
                self._blink_visible = True
                self._refresh()
            elif event_type in {
                QEvent.Type.FontChange,
                QEvent.Type.LayoutRequest,
                QEvent.Type.Show,
                QEvent.Type.Hide,
            }:
                QTimer.singleShot(0, self._refresh)
        elif watched is self._editor.viewport() and event_type in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        }:
            QTimer.singleShot(0, self._refresh)
        return super().eventFilter(watched, event)

    def _hide_native_caret(self) -> None:
        # QTextEdit exposes native caret width only. Width zero suppresses it so
        # color, height and thickness are controlled by one consistent overlay.
        self._editor.setCursorWidth(0)

    def _on_cursor_changed(self) -> None:
        self._blink_visible = True
        self._restart_blink()
        self._refresh()

    def _restart_blink(self) -> None:
        self._blink_timer.stop()
        if not self._editor.hasFocus():
            return
        flash_time = QApplication.cursorFlashTime()
        if flash_time <= 0:
            self._blink_visible = True
            return
        self._blink_timer.setInterval(max(int(flash_time) // 2, 100))
        self._blink_timer.start()

    def _toggle_blink(self) -> None:
        self._blink_visible = not self._blink_visible
        self._refresh()

    def _refresh(self) -> None:
        if (
            not self._editor.isVisible()
            or not self._editor.hasFocus()
            or self._editor.textCursor().hasSelection()
        ):
            self._overlay.hide()
            return
        if not self._blink_visible:
            self._overlay.hide()
            return

        rect = self._editor.cursorRect(self._editor.textCursor())
        native_height = max(rect.height(), 1)
        height = max(
            1,
            int(round(native_height * self._size_percent / 100.0)),
        )
        top = rect.top() + (native_height - height) // 2
        self._overlay.setGeometry(
            rect.left(),
            top,
            self._thickness,
            height,
        )
        self._overlay.raise_()
        self._overlay.show()
