"""Keep the active caret away from the bottom edge while preserving source text."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, QTimer
from PySide6.QtWidgets import QTextEdit, QWidget


class CaretScrollMarginController(QObject):
    """Add scroll-past-end space and keep a focused caret above the viewport bottom."""

    _BOTTOM_SPACE_RATIO = 0.35
    _CARET_RESERVE_RATIO = 0.22
    _MIN_BOTTOM_SPACE_PX = 96
    _MIN_CARET_RESERVE_PX = 64

    def __init__(self, editor: QTextEdit) -> None:
        super().__init__(editor)
        self._editor: QTextEdit | None = editor
        self._viewport: QWidget | None = editor.viewport()

        root_frame = editor.document().rootFrame()
        self._base_bottom_margin = (
            float(root_frame.frameFormat().bottomMargin())
            if root_frame is not None
            else 0.0
        )

        editor.installEventFilter(self)
        self._viewport.installEventFilter(self)
        editor.cursorPositionChanged.connect(self._schedule_refresh)
        editor.destroyed.connect(self._on_editor_destroyed)

        self._refresh()

    def eventFilter(self, watched, event) -> bool:
        """Refresh the visual scroll margin when the editor geometry changes."""
        editor = self._editor
        viewport = self._viewport
        if editor is None or viewport is None:
            return False

        event_type = event.type()
        if watched is editor and event_type in {
            QEvent.Type.Show,
            QEvent.Type.FocusIn,
            QEvent.Type.FontChange,
            QEvent.Type.LayoutRequest,
        }:
            self._schedule_refresh()
        elif watched is viewport and event_type in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._schedule_refresh()
        return super().eventFilter(watched, event)

    def _schedule_refresh(self) -> None:
        if self._editor is None:
            return
        QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        editor = self._editor
        viewport = self._viewport
        if editor is None or viewport is None:
            return
        self._apply_bottom_space(editor, viewport)
        self._keep_caret_above_bottom(editor, viewport)

    def _apply_bottom_space(
        self,
        editor: QTextEdit,
        viewport: QWidget,
    ) -> None:
        document = editor.document()
        root_frame = document.rootFrame()
        if root_frame is None:
            return

        extra_space = max(
            self._MIN_BOTTOM_SPACE_PX,
            int(round(viewport.height() * self._BOTTOM_SPACE_RATIO)),
        )
        target_margin = self._base_bottom_margin + float(extra_space)

        frame_format = root_frame.frameFormat()
        if abs(float(frame_format.bottomMargin()) - target_margin) < 0.5:
            return

        was_modified = document.isModified()
        editor_blocker = QSignalBlocker(editor)
        document_blocker = QSignalBlocker(document)
        try:
            frame_format.setBottomMargin(target_margin)
            root_frame.setFrameFormat(frame_format)
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

    def _keep_caret_above_bottom(
        self,
        editor: QTextEdit,
        viewport: QWidget,
    ) -> None:
        if not editor.isVisible() or not editor.hasFocus():
            return
        reserve = max(
            self._MIN_CARET_RESERVE_PX,
            int(round(viewport.height() * self._CARET_RESERVE_RATIO)),
        )
        lower_limit = max(viewport.height() - reserve, 1)
        cursor_rect = editor.cursorRect(editor.textCursor())
        overflow = cursor_rect.bottom() - lower_limit
        if overflow <= 0:
            return

        scrollbar = editor.verticalScrollBar()
        target = min(
            scrollbar.maximum(),
            scrollbar.value() + int(overflow),
        )
        if target != scrollbar.value():
            scrollbar.setValue(target)

    def _on_editor_destroyed(self, _object=None) -> None:
        self._editor = None
        self._viewport = None
