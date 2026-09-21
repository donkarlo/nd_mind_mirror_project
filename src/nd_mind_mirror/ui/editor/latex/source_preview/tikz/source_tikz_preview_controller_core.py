"""Asynchronous inline TikZ previews for LaTeX Source input/include lines."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, QTimer
from PySide6.QtGui import QImage, QTextCursor, QTextFormat
from shiboken6 import isValid

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_tikz_preview_widget import (
    SourceTikZPreviewWidget,
)
from nd_mind_mirror.ui.editor.latex.source_tikz_preview_anchor import (
    SourceTikZPreviewAnchor,
)
from nd_mind_mirror.ui.editor.latex.tikz_visual_preview_service import (
    TikZVisualPreviewService,
)


class SourceTikZPreviewController(QObject):
    """Project referenced TikZ children below their complete Source input/include lines."""

    _REFRESH_DELAY_MS = 70
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
        self._reserved_blocks: dict[int, object] = {}

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
        """Coalesce Source preview work while the editor is changing."""
        if isValid(self._refresh_timer):
            self._refresh_timer.start()

    def eventFilter(self, watched, event) -> bool:
        """Track viewport resizes without touching an editor after Qt destroys it."""
        editor = self._active_editor
        if self._editor_is_alive(editor):
            viewport = self._viewport(editor)
            if (
                viewport is not None
                and watched is viewport
                and event.type() == QEvent.Type.Resize
            ):
                self.schedule_refresh()
        return super().eventFilter(watched, event)

    def refresh_positions(self) -> None:
        """Place every preview below the end of its full input/include source line."""
        editor = self._current_live_editor()
        if editor is not self._active_editor:
            self.schedule_refresh()
            return
        if editor is None or editor.edit_mode != "source":
            self._hide_unused(0)
            return

        viewport = self._viewport(editor)
        if viewport is None:
            self._reset_dead_editor()
            return
        if viewport.width() != self._layout_viewport_width:
            self.schedule_refresh()
            return

        viewport_height = viewport.height()
        horizontal = editor.horizontalScrollBar().value()
        used = 0
        document = editor.document()
        if not isValid(document):
            self._reset_dead_editor()
            return

        max_position = max(document.characterCount() - 1, 0)
        for item in self._layout:
            anchor = QTextCursor(document)
            anchor.setPosition(
                max(0, min(int(item["anchor_position"]), max_position))
            )
            anchor_rect = editor.cursorRect(anchor)
            height = int(item["height"])
            y = int(anchor_rect.bottom()) + self._IMAGE_GAP_PX
            if y > viewport_height or y + height < 0:
                continue

            widget = self._widget(used, viewport)
            width = int(item["width"])
            available = max(viewport.width() - 32, 120)
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
        """Rebuild only TikZ reservations; never scan every QTextBlock in the document."""
        editor = self._current_live_editor()
        if editor is not self._active_editor:
            self._detach_editor()
            if editor is not None:
                self._attach_editor(editor)

        editor = self._active_editor
        if editor is None:
            self._layout = []
            self._layout_viewport_width = -1
            self._hide_unused(0)
            return
        if editor.edit_mode != "source":
            self._clear_reserved_space(editor)
            self._layout = []
            self._layout_viewport_width = -1
            self._hide_unused(0)
            return

        viewport = self._viewport(editor)
        document = editor.document()
        if viewport is None or not isValid(document):
            self._reset_dead_editor()
            return

        source = editor.toPlainText()
        self._clear_reserved_space(editor)
        if not self._editor_is_alive(editor):
            self._reset_dead_editor()
            return

        available = max(viewport.width() - 32, 120)
        layout: list[dict[str, object]] = []
        reservations: dict[int, int] = {}

        for match in self._INPUT.finditer(source):
            raw = match.group(0)
            image = self._service.preview_for_input(raw, editor.source_path)
            if image is None or image.isNull():
                continue

            anchor_position = SourceTikZPreviewAnchor.position(match.start(), match.end())
            block = document.findBlock(anchor_position)
            if not block.isValid():
                continue

            native_width = max(int(image.width()), 1)
            width = min(
                native_width,
                max(int(available * self._MAX_WIDTH_RATIO), 1),
            )
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
                    "anchor_position": anchor_position,
                    "image": QImage(image),
                    "width": width,
                    "height": height,
                }
            )

        self._apply_reserved_space(editor, reservations)
        if not self._editor_is_alive(editor):
            self._reset_dead_editor()
            return
        self._layout = layout
        self._layout_viewport_width = viewport.width()
        self.refresh_positions()

    def _attach_editor(self, editor: LatexEditor) -> None:
        """Attach filters/signals to one live editor and clear them on destruction."""
        if not self._editor_is_alive(editor):
            return
        viewport = self._viewport(editor)
        if viewport is None:
            return
        self._active_editor = editor
        viewport.installEventFilter(self)
        editor.verticalScrollBar().valueChanged.connect(self._on_scroll)
        editor.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        editor.destroyed.connect(self._on_active_editor_destroyed)

    def _on_active_editor_destroyed(self, *_args) -> None:
        """Drop Python references immediately when Qt destroys the editor C++ object."""
        self._active_editor = None
        self._layout = []
        self._layout_viewport_width = -1
        self._reserved_blocks.clear()
        self._hide_unused(0)

    def _on_preview_ready(
        self,
        referring_file: str,
        _raw: str,
        image: object,
    ) -> None:
        if not isinstance(image, QImage) or image.isNull():
            return
        editor = self._current_live_editor()
        if editor is None:
            return
        try:
            if Path(referring_file).expanduser().resolve() != editor.source_path:
                return
        except (OSError, RuntimeError):
            return
        self.schedule_refresh()

    def _on_scroll(self, _value: int) -> None:
        self.refresh_positions()

    def _detach_editor(self) -> None:
        """Detach from the previous editor without dereferencing a deleted Qt object."""
        editor = self._active_editor
        self._active_editor = None
        self._layout = []
        self._layout_viewport_width = -1

        if not self._editor_is_alive(editor):
            self._reserved_blocks.clear()
            self._clear_widgets()
            return

        self._clear_reserved_space(editor)
        viewport = self._viewport(editor)
        try:
            if viewport is not None:
                viewport.removeEventFilter(self)
            editor.verticalScrollBar().valueChanged.disconnect(self._on_scroll)
            editor.horizontalScrollBar().valueChanged.disconnect(self._on_scroll)
            editor.destroyed.disconnect(self._on_active_editor_destroyed)
        except (RuntimeError, TypeError):
            pass
        self._clear_widgets()

    def _reset_dead_editor(self) -> None:
        """Reset controller state after a Qt wrapper loses its backing C++ object."""
        self._active_editor = None
        self._layout = []
        self._layout_viewport_width = -1
        self._reserved_blocks.clear()
        self._hide_unused(0)

    def _current_live_editor(self) -> LatexEditor | None:
        try:
            editor = self._editor_panel.current_editor()
        except RuntimeError:
            return None
        if not isinstance(editor, LatexEditor):
            return None
        return editor if self._editor_is_alive(editor) else None

    @staticmethod
    def _editor_is_alive(editor: LatexEditor | None) -> bool:
        if editor is None:
            return False
        try:
            return bool(isValid(editor))
        except RuntimeError:
            return False

    @staticmethod
    def _viewport(editor: LatexEditor):
        if not SourceTikZPreviewController._editor_is_alive(editor):
            return None
        try:
            viewport = editor.viewport()
        except RuntimeError:
            return None
        return viewport if isValid(viewport) else None

    def _clear_reserved_space(self, editor: LatexEditor | None) -> None:
        """Clear only blocks previously owned by this controller."""
        if not self._editor_is_alive(editor):
            self._reserved_blocks.clear()
            return
        try:
            document = editor.document()
        except RuntimeError:
            self._reserved_blocks.clear()
            return
        if not isValid(document):
            self._reserved_blocks.clear()
            return

        was_modified = document.isModified()
        editor_blocker = QSignalBlocker(editor)
        document_blocker = QSignalBlocker(document)
        try:
            for block in tuple(self._reserved_blocks.values()):
                if block is None or not block.isValid():
                    continue
                block_format = block.blockFormat()
                if not bool(
                    block_format.property(self._BLOCK_TIKZ_SPACE_PROPERTY)
                ):
                    continue
                block_format.setBottomMargin(0.0)
                block_format.clearProperty(self._BLOCK_TIKZ_SPACE_PROPERTY)
                QTextCursor(block).setBlockFormat(block_format)
            document.setModified(was_modified)
        except RuntimeError:
            pass
        finally:
            self._reserved_blocks.clear()
            del document_blocker
            del editor_blocker

    def _apply_reserved_space(
        self,
        editor: LatexEditor,
        reservations: dict[int, int],
    ) -> None:
        """Reserve image space only on the include blocks that need it."""
        if not reservations or not self._editor_is_alive(editor):
            return
        try:
            document = editor.document()
        except RuntimeError:
            return
        if not isValid(document):
            return

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
                block_format.setProperty(self._BLOCK_TIKZ_SPACE_PROPERTY, True)
                QTextCursor(block).setBlockFormat(block_format)
                self._reserved_blocks[int(block.position())] = block
            document.setModified(was_modified)
        except RuntimeError:
            return
        finally:
            del document_blocker
            del editor_blocker

    def _widget(self, index: int, parent) -> SourceTikZPreviewWidget:
        while len(self._widgets) <= index:
            self._widgets.append(SourceTikZPreviewWidget(parent))
        widget = self._widgets[index]
        if not isValid(widget):
            widget = SourceTikZPreviewWidget(parent)
            self._widgets[index] = widget
        elif widget.parent() is not parent:
            widget.setParent(parent)
        return widget

    def _hide_unused(self, used: int) -> None:
        for widget in self._widgets[max(int(used), 0):]:
            try:
                if isValid(widget):
                    widget.hide()
            except RuntimeError:
                pass

    def _clear_widgets(self) -> None:
        for widget in self._widgets:
            try:
                if isValid(widget):
                    widget.hide()
                    widget.deleteLater()
            except RuntimeError:
                pass
        self._widgets.clear()
