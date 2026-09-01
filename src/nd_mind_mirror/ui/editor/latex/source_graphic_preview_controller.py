"""Render lightweight image thumbnails beside visible LaTeX Source figure commands."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_graphic_preview_widget import (
    SourceGraphicPreviewWidget,
)


class SourceGraphicPreviewController(QObject):
    """Show raster figures near visible Source code without copying the full document."""

    _LANE_WIDTH = 228
    _REFRESH_DELAY_MS = 220
    _IMAGE_POLL_MS = 700
    _WINDOW_PADDING_BLOCKS = 12
    _RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    _INCLUDEGRAPHICS = re.compile(
        r"\\includegraphics\s*(?:\[(?P<options>[^\]]*)\]\s*)?"
        r"\{(?P<path>[^{}]+)\}",
        re.IGNORECASE,
    )
    _RELATIVE_WIDTH = re.compile(
        r"(?:^|,)\s*width\s*=\s*(?P<ratio>[0-9]*\.?[0-9]+)\s*"
        r"\\(?:textwidth|linewidth|columnwidth)\s*(?:,|$)",
        re.IGNORECASE,
    )

    def __init__(self, editor_panel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._widgets: list[SourceGraphicPreviewWidget] = []
        self._active_editor: LatexEditor | None = None
        self._base_right_margin = 0.0
        self._margin_applied = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(self._REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        self._image_poll_timer = QTimer(self)
        self._image_poll_timer.setInterval(self._IMAGE_POLL_MS)
        self._image_poll_timer.timeout.connect(self.schedule_refresh)
        self._image_poll_timer.start()

        self._editor_panel.current_document_changed.connect(
            lambda *_args: self.schedule_refresh()
        )
        self._editor_panel.current_content_changed.connect(
            lambda *_args: self.schedule_refresh()
        )
        self._editor_panel.current_view_changed.connect(
            lambda *_args: self.schedule_refresh()
        )
        QTimer.singleShot(0, self.refresh)

    def schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def refresh(self) -> None:
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self._restore_margin()
            self._clear_widgets()
            self._active_editor = editor if isinstance(editor, LatexEditor) else None
            self._margin_applied = False

        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            self._restore_margin()
            self._hide_unused(0)
            return

        viewport = editor.viewport()
        top_position = editor.cursorForPosition(QPoint(1, 1)).position()
        bottom_position = editor.cursorForPosition(
            QPoint(max(viewport.width() - 2, 1), max(viewport.height() - 2, 1))
        ).position()
        source_window, base_position = self._visible_source_window(
            editor,
            top_position,
            bottom_position,
        )
        matches = list(self._INCLUDEGRAPHICS.finditer(source_window))
        if not matches:
            self._restore_margin()
            self._hide_unused(0)
            return

        resolved_matches: list[tuple[re.Match[str], Path, int]] = []
        for match in matches:
            image_path = self._resolve_image_path(
                editor.source_path.parent,
                match.group("path"),
            )
            if image_path is None:
                continue
            resolved_matches.append((match, image_path, base_position + match.start()))

        if not resolved_matches:
            self._restore_margin()
            self._hide_unused(0)
            return

        self._reserve_preview_lane(editor)
        lane_left = max(viewport.width() - self._LANE_WIDTH, 0)
        used = 0
        for match, image_path, source_position in resolved_matches:
            block = editor.document().findBlock(source_position)
            if not block.isValid():
                continue
            rectangle = editor.cursorRect(QTextCursor(block))
            y = int(rectangle.top()) + 3
            if y < -SourceGraphicPreviewWidget._MAX_HEIGHT or y > viewport.height():
                continue

            widget = self._widget(used, viewport)
            ratio = self._width_ratio(match.group("options") or "")
            target_width = int((self._LANE_WIDTH - 16) * ratio)
            if widget.display_image(
                image_path,
                target_width,
                y,
                lane_left,
                self._LANE_WIDTH,
            ):
                used += 1

        self._hide_unused(used)

    @classmethod
    def _visible_source_window(
        cls,
        editor: LatexEditor,
        top_position: int,
        bottom_position: int,
    ) -> tuple[str, int]:
        """Return only visible-neighbouring text blocks and their document offset."""
        document = editor.document()
        start_block = document.findBlock(min(top_position, bottom_position))
        end_block = document.findBlock(max(top_position, bottom_position))
        for _ in range(cls._WINDOW_PADDING_BLOCKS):
            previous = start_block.previous()
            if not previous.isValid():
                break
            start_block = previous
        for _ in range(cls._WINDOW_PADDING_BLOCKS):
            following = end_block.next()
            if not following.isValid():
                break
            end_block = following

        base_position = max(int(start_block.position()), 0)
        parts: list[str] = []
        block = start_block
        while block.isValid():
            parts.append(block.text())
            if block == end_block:
                break
            parts.append("\n")
            block = block.next()
        return "".join(parts), base_position

    def _reserve_preview_lane(self, editor: LatexEditor) -> None:
        if self._margin_applied:
            return
        frame = editor.document().rootFrame()
        if frame is None:
            return
        fmt = frame.frameFormat()
        self._base_right_margin = float(fmt.rightMargin())
        fmt.setRightMargin(self._base_right_margin + float(self._LANE_WIDTH))
        frame.setFrameFormat(fmt)
        self._margin_applied = True
        editor.viewport().update()

    def _restore_margin(self) -> None:
        editor = self._active_editor
        if not self._margin_applied or editor is None:
            return
        try:
            frame = editor.document().rootFrame()
            if frame is not None:
                fmt = frame.frameFormat()
                fmt.setRightMargin(self._base_right_margin)
                frame.setFrameFormat(fmt)
                editor.viewport().update()
        except RuntimeError:
            pass
        self._margin_applied = False

    def _widget(self, index: int, parent) -> SourceGraphicPreviewWidget:
        while len(self._widgets) <= index:
            self._widgets.append(SourceGraphicPreviewWidget(parent))
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

    @classmethod
    def _width_ratio(cls, options: str) -> float:
        match = cls._RELATIVE_WIDTH.search(str(options))
        if match is None:
            return 0.90
        try:
            return max(0.20, min(float(match.group("ratio")), 1.0))
        except (TypeError, ValueError):
            return 0.90

    @classmethod
    def _resolve_image_path(cls, directory: Path, raw_path: str) -> Path | None:
        value = str(raw_path).strip()
        if not value or value.startswith("\\") or "://" in value:
            return None
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = directory / candidate

        options = [candidate]
        if not candidate.suffix:
            options = [candidate.with_suffix(suffix) for suffix in cls._RASTER_SUFFIXES]
        for option in options:
            try:
                resolved = option.resolve()
            except OSError:
                continue
            if resolved.is_file() and resolved.suffix.lower() in cls._RASTER_SUFFIXES:
                return resolved
        return None
