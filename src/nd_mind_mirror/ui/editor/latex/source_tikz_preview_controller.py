"""Asynchronous inline TikZ previews for LaTeX Source input/include lines."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, QTimer
from PySide6.QtGui import QImage, QTextCursor, QTextFormat

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_tikz_preview_widget import (
    SourceTikZPreviewWidget,
)
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_service import (
    TikZVisualPreviewService,
)


class SourceTikZPreviewController(QObject):
    """Project referenced TikZ children under their canonical Source lines."""

    _REFRESH_DELAY_MS = 45
    _IMAGE_GAP_PX = 8
    _MAX_WIDTH_RATIO = 0.92
    _BLOCK_TIKZ_SPACE_PROPERTY = int(QTextFormat.Property.UserProperty) + 431
    _INPUT = re.compile(
        r"^\s*\\(?:input|include)\s*\{[^}]+\}\s*(?:%.*)?$",
        re.MULTILINE,
    )

    def __init__(
        self,
        editor_panel,
        workspace_root: str | Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._service = TikZVisualPreviewService(workspace_root, self)
        self._service.preview_ready.connect(self._on_preview_ready)
        self._widgets: list[SourceTikZPreviewWidget] = []
        self._active_editor: LatexEditor | None = None
        self._layout: list[dict[str, object]] = []
        self._layout_viewport_width = -1

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(self._REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self._rebuild_layout)

        self._editor_panel.current_document_changed.connect(
            lambda *_args: self.schedule_refresh()
        )
        self._editor_panel.current_content_changed.connect(
            lambda *_args: self.schedule_refresh()
        )
        self._editor_panel.current_view_changed.connect(
            lambda *_args: self.refresh_positions()
        )
        QTimer.singleShot(0, self._rebuild_layout)

    def notify_tikz_changed(self, _path: str | Path) -> None:
        """Refresh the visible Source projection after an external TikZ save."""
        self.schedule_refresh()

    def schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def eventFilter(self, watched, event) -> bool:
        editor = self._active_editor
        if (
            editor is not None
            and watched is editor.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.schedule_refresh()
        return super().eventFilter(watched, event)

    def refresh_positions(self) -> None:
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_refresh()
            return
        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            self._hide_unused(0)
            return
        if editor.viewport().width() != self._layout_viewport_width:
            self.schedule_refresh()
            return

        viewport_height = editor.viewport().height()
        horizontal = editor.horizontalScrollBar().value()
        used = 0
        for item in self._layout:
            block = editor.document().findBlock(int(item["block_position"]))
            if not block.isValid():
                continue
            line_rect = editor.cursorRect(QTextCursor(block))
            height = int(item["height"])
            y = int(line_rect.bottom()) + self._IMAGE_GAP_PX
            if y > viewport_height or y + height < 0:
                continue

            widget = self._widget(used, editor.viewport())
            width = int(item["width"])
            available = max(editor.viewport().width() - 32, 120)
            x = max((available - (width + 6)) // 2 + 16 - horizontal, 0)
            if widget.display_image(
                QImage(item["image"]),
                target_width=width,
                x=x,
                y=y,
            ):
                used += 1
        self._hide_unused(used)

    def _rebuild_layout(self) -> None:
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self._detach_editor()
            self._active_editor = editor if isinstance(editor, LatexEditor) else None
            if self._active_editor is not None:
                self._active_editor.viewport().installEventFilter(self)
                self._active_editor.verticalScrollBar().valueChanged.connect(
                    self._on_scroll
                )
                self._active_editor.horizontalScrollBar().valueChanged.connect(
                    self._on_scroll
                )

        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            self._clear_reserved_space(editor if isinstance(editor, LatexEditor) else None)
            self._layout = []
            self._layout_viewport_width = -1
            self._hide_unused(0)
            return

        source = editor.toPlainText()
        self._clear_reserved_space(editor)
        available = max(editor.viewport().width() - 32, 120)
        layout: list[dict[str, object]] = []
        reservations: dict[int, int] = {}

        for match in self._INPUT.finditer(source):
            raw = match.group(0)
            image = self._service.preview_for_input(raw, editor.source_path)
            if image is None or image.isNull():
                continue

            block = editor.document().findBlock(match.start())
            if not block.isValid():
                continue
            native_width = max(int(image.width()), 1)
            width = min(native_width, max(int(available * self._MAX_WIDTH_RATIO), 1))
            scale = width / native_width
            height = max(int(round(float(image.height()) * scale)) + 6, 1)
            block_position = block.position()
            reservations[block_position] = max(
                reservations.get(block_position, 0),
                height + (self._IMAGE_GAP_PX * 2),
            )
            layout.append(
                {
                    "block_position": block_position,
                    "image": QImage(image),
                    "width": width,
                    "height": height,
                }
            )

        self._apply_reserved_space(editor, reservations)
        self._layout = layout
        self._layout_viewport_width = editor.viewport().width()
        self.refresh_positions()

    def _on_preview_ready(
        self,
        referring_file: str,
        _raw: str,
        image: object,
    ) -> None:
        if not isinstance(image, QImage) or image.isNull():
            return
        editor = self._editor_panel.current_editor()
        if not isinstance(editor, LatexEditor):
            return
        try:
            if Path(referring_file).expanduser().resolve() != editor.source_path:
                return
        except OSError:
            return
        self.schedule_refresh()

    def _on_scroll(self, _value: int) -> None:
        self.refresh_positions()

    def _detach_editor(self) -> None:
        editor = self._active_editor
        if editor is None:
            return
        self._clear_reserved_space(editor)
        try:
            editor.viewport().removeEventFilter(self)
            editor.verticalScrollBar().valueChanged.disconnect(self._on_scroll)
            editor.horizontalScrollBar().valueChanged.disconnect(self._on_scroll)
        except (RuntimeError, TypeError):
            pass
        self._active_editor = None
        self._layout = []
        self._layout_viewport_width = -1
        self._clear_widgets()

    @classmethod
    def _clear_reserved_space(cls, editor: LatexEditor | None) -> None:
        if editor is None:
            return
        document = editor.document()
        was_modified = document.isModified()
        editor_blocker = QSignalBlocker(editor)
        document_blocker = QSignalBlocker(document)
        try:
            block = document.begin()
            while block.isValid():
                block_format = block.blockFormat()
                if bool(block_format.property(cls._BLOCK_TIKZ_SPACE_PROPERTY)):
                    block_format.setBottomMargin(0.0)
                    block_format.clearProperty(cls._BLOCK_TIKZ_SPACE_PROPERTY)
                    QTextCursor(block).setBlockFormat(block_format)
                block = block.next()
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

    @classmethod
    def _apply_reserved_space(
        cls,
        editor: LatexEditor,
        reservations: dict[int, int],
    ) -> None:
        if not reservations:
            return
        document = editor.document()
        was_modified = document.isModified()
        editor_blocker = QSignalBlocker(editor)
        document_blocker = QSignalBlocker(document)
        try:
            for position, height in reservations.items():
                block = document.findBlock(int(position))
                if not block.isValid():
                    continue
                block_format = block.blockFormat()
                block_format.setBottomMargin(float(max(int(height), 0)))
                block_format.setProperty(cls._BLOCK_TIKZ_SPACE_PROPERTY, True)
                QTextCursor(block).setBlockFormat(block_format)
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

    def _widget(self, index: int, parent) -> SourceTikZPreviewWidget:
        while len(self._widgets) <= index:
            self._widgets.append(SourceTikZPreviewWidget(parent))
        widget = self._widgets[index]
        if widget.parent() is not parent:
            widget.setParent(parent)
        return widget

    def _hide_unused(self, used: int) -> None:
        for widget in self._widgets[max(int(used), 0):]:
            try:
                widget.hide()
            except RuntimeError:
                pass

    def _clear_widgets(self) -> None:
        for widget in self._widgets:
            try:
                widget.hide()
                widget.deleteLater()
            except RuntimeError:
                pass
        self._widgets.clear()
