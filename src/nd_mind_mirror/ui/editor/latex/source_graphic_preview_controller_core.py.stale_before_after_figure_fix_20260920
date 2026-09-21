"""Lay out LaTeX figure previews inline in Source without changing canonical text."""

from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QEvent, QObject, QPoint, QSignalBlocker, QTimer, Qt
from PySide6.QtGui import QImageReader, QTextCursor, QTextFormat

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_graphic_preview_widget import (
    SourceGraphicPreviewWidget,
)


class SourceGraphicPreviewController(QObject):
    """Reserve stable inline space for figure images and draw only visible previews."""

    _REFRESH_DELAY_MS = 120
    _IMAGE_POLL_MS = 700
    _IMAGE_GAP_PX = 8
    _MIN_IMAGE_WIDTH_PX = 48
    _MAX_WIDTH_RATIO = 4.0
    _BLOCK_IMAGE_SPACE_PROPERTY = int(QTextFormat.Property.UserProperty) + 430
    _RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    _FIGURE = re.compile(
        r"\\begin\s*\{figure\}(?:\[[^\]]*\])?(?P<body>.*?)"
        r"(?P<end>\\end\s*\{figure\})",
        re.IGNORECASE | re.DOTALL,
    )
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
        self._layout: list[dict[str, object]] = []
        self._image_signatures: dict[Path, tuple[int, int]] = {}
        self._layout_viewport_width = -1
        self._native_horizontal_maximum = 0
        self._horizontal_overflow_active = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(self._REFRESH_DELAY_MS)
        self._refresh_timer.timeout.connect(self._rebuild_layout)

        self._image_poll_timer = QTimer(self)
        self._image_poll_timer.setInterval(self._IMAGE_POLL_MS)
        self._image_poll_timer.timeout.connect(self._poll_images)
        self._image_poll_timer.start()

        self._editor_panel.current_document_changed.connect(
            lambda *_args: self.schedule_layout_refresh()
        )
        self._editor_panel.current_content_changed.connect(
            lambda *_args: self.schedule_layout_refresh()
        )
        self._editor_panel.current_view_changed.connect(
            lambda *_args: self.refresh_positions()
        )
        QTimer.singleShot(0, self._rebuild_layout)

    def eventFilter(self, watched, event) -> bool:
        editor = self._active_editor
        if (
            editor is not None
            and watched is editor.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.schedule_layout_refresh()
        return super().eventFilter(watched, event)

    def schedule_layout_refresh(self) -> None:
        """Coalesce source/image/resize changes into one presentation rebuild."""
        self._refresh_timer.start()

    def refresh_positions(self) -> None:
        """Move visible image widgets without changing QTextDocument geometry."""
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
            return
        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            self._hide_unused(0)
            return
        if editor.viewport().width() != self._layout_viewport_width:
            self.schedule_layout_refresh()
            return
        if not self._layout and "\\includegraphics" in editor.toPlainText():
            self.schedule_layout_refresh()
            return

        viewport_height = editor.viewport().height()
        horizontal = editor.horizontalScrollBar().value()
        used = 0
        for item in self._layout:
            block = editor.document().findBlock(int(item["end_position"]))
            if not block.isValid():
                continue
            end_rect = editor.cursorRect(QTextCursor(block))
            distance_from_end = int(item["distance_from_end"])
            image_height = int(item["height"])
            y = int(end_rect.top()) - distance_from_end
            if y > viewport_height or y + image_height < 0:
                continue

            widget = self._widget(used, editor.viewport())
            x = self._image_left(editor, int(item["outer_width"])) - horizontal
            if widget.display_image(
                Path(item["path"]),
                target_width=int(item["target_width"]),
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
                    self._on_scroll_value_changed
                )
                self._active_editor.horizontalScrollBar().valueChanged.connect(
                    self._on_scroll_value_changed
                )

        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            self._clear_layout_margins(editor if isinstance(editor, LatexEditor) else None)
            self._layout = []
            self._image_signatures = {}
            self._restore_horizontal_scroll(editor if isinstance(editor, LatexEditor) else None)
            self._hide_unused(0)
            return

        source = editor.toPlainText()
        viewport_width = max(editor.viewport().width(), 1)
        anchor = self._capture_vertical_anchor(editor)
        self._clear_layout_margins(editor)

        layout: list[dict[str, object]] = []
        signatures: dict[Path, tuple[int, int]] = {}
        end_reservations: dict[int, int] = {}
        available_width = self._available_source_width(editor)
        max_image_width = 0

        for figure_match in self._FIGURE.finditer(source):
            body = figure_match.group("body")
            includes = list(self._INCLUDEGRAPHICS.finditer(body))
            if not includes:
                continue
            end_position = figure_match.start("end")
            figure_items: list[dict[str, object]] = []
            reserved_height = self._IMAGE_GAP_PX
            for include in includes:
                image_path = self._resolve_image_path(
                    editor.source_path.parent,
                    include.group("path"),
                )
                if image_path is None:
                    continue
                ratio = self._width_ratio(include.group("options") or "")
                width = max(
                    self._MIN_IMAGE_WIDTH_PX,
                    int(round(available_width * ratio)),
                )
                height = self._scaled_outer_height(image_path, width)
                if height <= 0:
                    continue
                try:
                    stat = image_path.stat()
                    signatures[image_path] = (int(stat.st_mtime_ns), int(stat.st_size))
                except OSError:
                    continue
                figure_items.append(
                    {
                        "path": image_path,
                        "end_position": end_position,
                        "target_width": width,
                        "outer_width": width + 6,
                        "height": height,
                        "distance_from_end": 0,
                    }
                )
                reserved_height += height + self._IMAGE_GAP_PX
                max_image_width = max(max_image_width, width + 6)

            if not figure_items:
                continue
            end_reservations[end_position] = reserved_height
            offset = self._IMAGE_GAP_PX
            for item in figure_items:
                item["distance_from_end"] = reserved_height - offset
                offset += int(item["height"]) + self._IMAGE_GAP_PX
                layout.append(item)

        self._apply_end_block_margins(editor, end_reservations)
        self._layout = layout
        self._image_signatures = signatures
        self._layout_viewport_width = viewport_width
        self._configure_horizontal_scroll(editor, max_image_width, available_width)
        self._restore_vertical_anchor(editor, anchor)
        self.refresh_positions()

    def _on_scroll_value_changed(self, _value: int) -> None:
        self.refresh_positions()

    def _detach_editor(self) -> None:
        editor = self._active_editor
        if editor is None:
            return
        self._clear_layout_margins(editor)
        self._restore_horizontal_scroll(editor)
        try:
            editor.viewport().removeEventFilter(self)
            editor.verticalScrollBar().valueChanged.disconnect(
                self._on_scroll_value_changed
            )
            editor.horizontalScrollBar().valueChanged.disconnect(
                self._on_scroll_value_changed
            )
        except (RuntimeError, TypeError):
            pass
        self._layout = []
        self._image_signatures = {}
        self._layout_viewport_width = -1
        self._clear_widgets()

    @staticmethod
    def _capture_vertical_anchor(editor: LatexEditor) -> tuple[int, int]:
        cursor = editor.cursorForPosition(QPoint(2, 2))
        return cursor.position(), editor.cursorRect(cursor).top()

    @staticmethod
    def _restore_vertical_anchor(editor: LatexEditor, anchor: tuple[int, int]) -> None:
        position, old_y = anchor
        cursor = QTextCursor(editor.document())
        cursor.setPosition(
            max(0, min(int(position), max(editor.document().characterCount() - 1, 0)))
        )
        new_y = editor.cursorRect(cursor).top()
        if new_y == old_y:
            return
        scrollbar = editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + new_y - old_y)

    @staticmethod
    def _clear_layout_margins(editor: LatexEditor | None) -> None:
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
                if block_format.topMargin() > 0.0 and bool(
                    block_format.property(SourceGraphicPreviewController._BLOCK_IMAGE_SPACE_PROPERTY)
                ):
                    block_format.setTopMargin(0.0)
                    block_format.clearProperty(SourceGraphicPreviewController._BLOCK_IMAGE_SPACE_PROPERTY)
                    cursor = QTextCursor(block)
                    cursor.setBlockFormat(block_format)
                block = block.next()
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

    @staticmethod
    def _apply_end_block_margins(
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
            for source_position, height in reservations.items():
                block = document.findBlock(max(int(source_position), 0))
                if not block.isValid():
                    continue
                block_format = block.blockFormat()
                block_format.setTopMargin(float(max(int(height), 0)))
                block_format.setProperty(
                    SourceGraphicPreviewController._BLOCK_IMAGE_SPACE_PROPERTY,
                    True,
                )
                cursor = QTextCursor(block)
                cursor.setBlockFormat(block_format)
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

    @staticmethod
    def _available_source_width(editor: LatexEditor) -> int:
        return max(editor.viewport().width() - 32, 120)

    @staticmethod
    def _image_left(editor: LatexEditor, image_width: int) -> int:
        available = SourceGraphicPreviewController._available_source_width(editor)
        return max((available - int(image_width)) // 2 + 16, 16)

    def _configure_horizontal_scroll(
        self,
        editor: LatexEditor,
        max_image_width: int,
        available_width: int,
    ) -> None:
        scrollbar = editor.horizontalScrollBar()
        if not self._horizontal_overflow_active:
            self._native_horizontal_maximum = max(int(scrollbar.maximum()), 0)
        overflow = max(int(max_image_width) - int(available_width), 0)
        if overflow <= 0:
            self._restore_horizontal_scroll(editor)
            return
        self._horizontal_overflow_active = True
        scrollbar.setPageStep(max(int(available_width), 1))
        scrollbar.setRange(0, max(self._native_horizontal_maximum, overflow))
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _restore_horizontal_scroll(self, editor: LatexEditor | None) -> None:
        if editor is None or not self._horizontal_overflow_active:
            return
        scrollbar = editor.horizontalScrollBar()
        scrollbar.setRange(0, max(int(self._native_horizontal_maximum), 0))
        scrollbar.setValue(min(scrollbar.value(), scrollbar.maximum()))
        self._horizontal_overflow_active = False

    def _poll_images(self) -> None:
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
            return
        if not isinstance(editor, LatexEditor) or editor.edit_mode != "source":
            return
        if editor.viewport().width() != self._layout_viewport_width:
            self.schedule_layout_refresh()
            return
        for path, old_signature in list(self._image_signatures.items()):
            try:
                stat = path.stat()
                signature = (int(stat.st_mtime_ns), int(stat.st_size))
            except OSError:
                signature = (-1, -1)
            if signature != old_signature:
                self.schedule_layout_refresh()
                return
        self.refresh_positions()

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
            return max(0.05, min(float(match.group("ratio")), cls._MAX_WIDTH_RATIO))
        except (TypeError, ValueError):
            return 0.90

    @staticmethod
    def _scaled_outer_height(image_path: Path, target_width: int) -> int:
        reader = QImageReader(str(image_path))
        size = reader.size()
        if not size.isValid() or size.width() <= 0 or size.height() <= 0:
            return 0
        return max(int(round(size.height() * int(target_width) / size.width())) + 6, 7)

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
