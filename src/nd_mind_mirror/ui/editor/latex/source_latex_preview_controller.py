"""Live graphical formula and table projections for LaTeX Source mode."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QSignalBlocker, QThread, QTimer
from PySide6.QtGui import QImage, QTextCursor, QTextFormat
from shiboken6 import isValid

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.source_latex_preview_extractor import (
    SourceLatexPreviewExtractor,
)
from nd_mind_mirror.ui.editor.latex.source_latex_preview_render_worker import (
    SourceLatexPreviewRenderWorker,
)
from nd_mind_mirror.ui.editor.latex.source_latex_preview_widget import (
    SourceLatexPreviewWidget,
)


class SourceLatexPreviewController(QObject):
    """Keep non-destructive rendered previews attached to canonical Source text.

    Extraction and layout coordination stay on the GUI thread. LuaLaTeX and PDF
    rasterization run in a short-lived worker thread. While rendering is active,
    newer edits replace the pending request instead of queuing another expensive
    compile. Existing preview margins remain in place until the replacement is
    ready, which keeps Source scrolling stable near the end of a document.
    """

    _REFRESH_DELAY_MS = 340
    _GAP_PX = 7
    _BLOCK_SPACE_PROPERTY = int(QTextFormat.Property.UserProperty) + 2441
    _CACHE_LIMIT = 512

    def __init__(self, editor_panel, parent=None) -> None:
        super().__init__(parent)
        self._editor_panel = editor_panel
        self._extractor = SourceLatexPreviewExtractor()
        self._widgets: list[SourceLatexPreviewWidget] = []
        self._active_editor: LatexEditor | None = None
        self._layout: list[dict[str, object]] = []
        self._layout_viewport_width = -1
        self._reserved_blocks: list[object] = []

        self._image_cache: dict[str, QImage] = {}
        self._failed_snippets: set[str] = set()
        self._request_generation = 0
        self._latest_request: dict[str, object] | None = None
        self._render_thread: QThread | None = None
        self._render_worker: SourceLatexPreviewRenderWorker | None = None

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

    def schedule_refresh(self) -> None:
        """Coalesce Source preview rebuild requests while the user is typing."""
        if isValid(self._refresh_timer):
            self._refresh_timer.start()

    def eventFilter(self, watched, event) -> bool:
        """Schedule a rebuild when the active Source viewport resizes."""
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
        """Reposition visible preview overlays without recompiling snippets."""
        editor = self._current_live_editor()
        if editor is not self._active_editor:
            self.schedule_refresh()
            return
        if editor is None or editor.edit_mode != "source":
            self._hide_unused(0)
            return

        viewport = self._viewport(editor)
        document = editor.document()
        if viewport is None or not isValid(document):
            self._reset_dead_editor()
            return
        if viewport.width() != self._layout_viewport_width:
            self.schedule_refresh()
            return

        viewport_height = viewport.height()
        used = 0
        for item in self._layout:
            block = document.findBlock(int(item["block_position"]))
            if not block.isValid():
                continue
            block_rect = editor.cursorRect(QTextCursor(block))
            height = int(item["height"])
            y = int(block_rect.bottom()) + self._GAP_PX + int(item["offset_y"])
            if y > viewport_height or y + height < 0:
                continue

            width = int(item["width"])
            if bool(item["inline"]):
                anchor = QTextCursor(document)
                anchor.setPosition(
                    max(
                        0,
                        min(
                            int(item["anchor_position"]),
                            document.characterCount() - 1,
                        ),
                    )
                )
                anchor_rect = editor.cursorRect(anchor)
                x = int(anchor_rect.right()) + self._GAP_PX
                x = min(x, max(viewport.width() - width - 10, 0))
            else:
                x = max((viewport.width() - width) // 2, 0)

            widget = self._widget(used, viewport)
            if widget.display_image(
                QImage(item["image"]),
                target_width=width,
                x=x,
                y=y,
            ):
                used += 1
        self._hide_unused(used)

    def _rebuild_layout(self) -> None:
        """Extract the latest Source request and resolve it from cache or worker."""
        editor = self._current_live_editor()
        if editor is not self._active_editor:
            self._detach_editor()
            if editor is not None:
                self._attach_editor(editor)

        editor = self._active_editor
        if editor is None:
            self._latest_request = None
            self._clear_state()
            return
        if editor.edit_mode != "source":
            self._request_generation += 1
            self._latest_request = None
            self._clear_reserved_space(editor)
            self._clear_state()
            return

        viewport = self._viewport(editor)
        document = editor.document()
        if viewport is None or not isValid(document):
            self._reset_dead_editor()
            return

        source = editor.toPlainText()
        spans = self._extractor.extract(source)
        self._request_generation += 1
        generation = self._request_generation
        request: dict[str, object] = {
            "generation": generation,
            "editor": editor,
            "source": source,
            "spans": spans,
            "viewport_width": int(viewport.width()),
        }
        self._latest_request = request

        if not spans:
            self._commit_request(request)
            return

        self._resolve_latest_request()

    def _resolve_latest_request(self) -> None:
        """Commit the newest request or start one background render batch."""
        request = self._latest_request
        if request is None:
            return
        editor = request.get("editor")
        if not isinstance(editor, LatexEditor) or not self._editor_is_alive(editor):
            return
        if editor is not self._active_editor or editor.edit_mode != "source":
            return

        spans = request.get("spans")
        if not isinstance(spans, list):
            return

        missing: list[str] = []
        seen: set[str] = set()
        for span in spans:
            raw = str(span.raw).strip()
            if (
                not raw
                or raw in seen
                or raw in self._image_cache
                or raw in self._failed_snippets
            ):
                continue
            seen.add(raw)
            missing.append(raw)

        if missing:
            if self._render_thread is None:
                self._start_render(int(request["generation"]), missing)
            return

        self._commit_request(request)

    def _start_render(self, generation: int, snippets: list[str]) -> None:
        """Run one snippet batch on a worker thread without blocking typing."""
        if self._render_thread is not None or not snippets:
            return

        application = QCoreApplication.instance()
        thread = QThread(application)
        worker = SourceLatexPreviewRenderWorker(generation, snippets)
        worker.moveToThread(thread)

        thread.started.connect(worker.render)
        worker.completed.connect(self._on_render_completed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_render_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._render_thread = thread
        self._render_worker = worker
        thread.start()

    def _on_render_completed(
        self,
        _generation: int,
        images: object,
        attempted: object,
    ) -> None:
        """Merge background results into the bounded preview cache."""
        valid_images = images if isinstance(images, dict) else {}
        attempted_snippets = tuple(attempted) if isinstance(attempted, tuple) else ()

        for raw, image in valid_images.items():
            if isinstance(image, QImage) and not image.isNull():
                self._remember_image(str(raw), image)
                self._failed_snippets.discard(str(raw))

        for raw in attempted_snippets:
            key = str(raw).strip()
            if key and key not in valid_images:
                self._failed_snippets.add(key)
        self._trim_failed_cache()

    def _on_render_thread_finished(self) -> None:
        """Release the finished worker and immediately resolve only the newest edit."""
        self._render_thread = None
        self._render_worker = None
        self._resolve_latest_request()

    def _commit_request(self, request: dict[str, object]) -> None:
        """Build overlays from cached images and atomically update Source margins."""
        if request is not self._latest_request:
            return
        editor = request.get("editor")
        if not isinstance(editor, LatexEditor) or not self._editor_is_alive(editor):
            return
        if editor is not self._active_editor or editor.edit_mode != "source":
            return

        expected_source = str(request.get("source", ""))
        if editor.toPlainText() != expected_source:
            self.schedule_refresh()
            return

        viewport = self._viewport(editor)
        document = editor.document()
        if viewport is None or not isValid(document):
            self._reset_dead_editor()
            return

        spans = request.get("spans")
        if not isinstance(spans, list):
            return
        if not spans:
            self._update_reserved_space(editor, {})
            self._clear_state(viewport_width=viewport.width())
            return

        available = max(viewport.width() - 32, 120)
        line_height = max(editor.fontMetrics().height(), 18)
        layout: list[dict[str, object]] = []
        reservations: dict[int, int] = {}
        offsets: dict[int, int] = {}

        for span in spans:
            key = str(span.raw).strip()
            image = self._image_cache.get(key)
            if image is None or image.isNull():
                continue

            anchor_position = max(span.end - 1, span.start)
            block = document.findBlock(anchor_position)
            if not block.isValid():
                continue

            width, height = self._logical_size(
                image,
                kind=span.kind,
                display=span.display,
                line_height=line_height,
                available=available,
            )
            block_position = block.position()
            offset_y = offsets.get(block_position, 0)
            offsets[block_position] = offset_y + height + self._GAP_PX
            reservations[block_position] = offsets[block_position] + self._GAP_PX
            layout.append(
                {
                    "block_position": block_position,
                    "anchor_position": span.end,
                    "image": QImage(image),
                    "width": width,
                    "height": height,
                    "offset_y": offset_y,
                    "inline": span.kind == "math" and not span.display,
                }
            )

        generation = int(request.get("generation", 0))
        self._update_reserved_space(editor, reservations, generation=generation)
        if not self._editor_is_alive(editor):
            self._reset_dead_editor()
            return
        self._layout = layout
        self._layout_viewport_width = viewport.width()
        self.refresh_positions()

    @staticmethod
    def _logical_size(
        image: QImage,
        *,
        kind: str,
        display: bool,
        line_height: int,
        available: int,
    ) -> tuple[int, int]:
        """Compute readable preview dimensions for inline math, display math, or tables."""
        ratio = float(image.width()) / max(float(image.height()), 1.0)
        if kind == "table":
            target_width = min(
                max(int(round(image.width() / 2.6)), 220),
                int(available * 0.92),
            )
            target_width = max(target_width, min(available, 120))
            return (
                target_width,
                max(int(round(target_width / max(ratio, 0.01))), 1),
            )

        if display:
            target_height = max(int(round(line_height * 2.05)), 42)
            target_width = max(int(round(target_height * ratio)), 1)
            if target_width > int(available * 0.9):
                target_width = max(int(available * 0.9), 1)
                target_height = max(
                    int(round(target_width / max(ratio, 0.01))),
                    1,
                )
            return target_width, target_height

        target_height = max(int(round(line_height * 1.12)), 18)
        target_width = max(int(round(target_height * ratio)), 1)
        target_width = min(target_width, max(int(available * 0.45), 40))
        target_height = max(
            int(round(target_width / max(ratio, 0.01))),
            1,
        )
        return target_width, target_height

    def _attach_editor(self, editor: LatexEditor) -> None:
        """Attach viewport and scroll listeners to one live LaTeX editor."""
        if not self._editor_is_alive(editor):
            return
        viewport = self._viewport(editor)
        if viewport is None:
            return
        self._active_editor = editor
        viewport.installEventFilter(self)
        editor.verticalScrollBar().valueChanged.connect(self._on_scroll)
        editor.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        editor.active_view_changed.connect(self._on_view_changed)
        editor.destroyed.connect(self._on_active_editor_destroyed)

    def _detach_editor(self) -> None:
        """Detach listeners and remove Source margins from the previous editor."""
        editor = self._active_editor
        if self._editor_is_alive(editor):
            self._clear_reserved_space(editor)
        self._active_editor = None
        self._latest_request = None
        self._request_generation += 1
        self._layout = []
        self._layout_viewport_width = -1

        if not self._editor_is_alive(editor):
            self._reserved_blocks.clear()
            self._clear_widgets()
            return
        viewport = self._viewport(editor)
        try:
            if viewport is not None:
                viewport.removeEventFilter(self)
            editor.verticalScrollBar().valueChanged.disconnect(self._on_scroll)
            editor.horizontalScrollBar().valueChanged.disconnect(self._on_scroll)
            editor.active_view_changed.disconnect(self._on_view_changed)
            editor.destroyed.disconnect(self._on_active_editor_destroyed)
        except (RuntimeError, TypeError):
            pass
        self._clear_widgets()

    def _on_view_changed(self, *_args) -> None:
        """Rebuild previews when the editor switches Source/Visual view state."""
        self.schedule_refresh()

    def _on_scroll(self, _value: int) -> None:
        """Reposition overlays after Source scrolling."""
        self.refresh_positions()

    def _on_active_editor_destroyed(self, *_args) -> None:
        """Drop references after Qt destroys the active editor."""
        self._active_editor = None
        self._latest_request = None
        self._request_generation += 1
        self._reserved_blocks.clear()
        self._clear_state()

    def _reset_dead_editor(self) -> None:
        """Clear state when the active editor wrapper is no longer valid."""
        self._active_editor = None
        self._latest_request = None
        self._request_generation += 1
        self._reserved_blocks.clear()
        self._clear_state()

    def _clear_state(self, viewport_width: int = -1) -> None:
        """Reset cached layout state and hide unused overlays."""
        self._layout = []
        self._layout_viewport_width = int(viewport_width)
        self._hide_unused(0)

    def _current_live_editor(self) -> LatexEditor | None:
        """Return the current valid LaTeX editor, if one exists."""
        try:
            editor = self._editor_panel.current_editor()
        except RuntimeError:
            return None
        if not isinstance(editor, LatexEditor):
            return None
        return editor if self._editor_is_alive(editor) else None

    @staticmethod
    def _editor_is_alive(editor: LatexEditor | None) -> bool:
        """Return whether a LaTeX editor still has a valid Qt object."""
        if editor is None:
            return False
        try:
            return bool(isValid(editor))
        except RuntimeError:
            return False

    @staticmethod
    def _viewport(editor: LatexEditor):
        """Return the valid viewport for a live LaTeX editor."""
        if not SourceLatexPreviewController._editor_is_alive(editor):
            return None
        try:
            viewport = editor.viewport()
        except RuntimeError:
            return None
        return viewport if isValid(viewport) else None

    def _update_reserved_space(
        self,
        editor: LatexEditor,
        reservations: dict[int, int],
        *,
        generation: int = 0,
    ) -> None:
        """Update only changed preview margins and preserve the visible Source anchor."""
        if not self._editor_is_alive(editor):
            return
        document = editor.document()
        if not isValid(document):
            return

        scroll_anchor = self._capture_scroll_anchor(editor)
        old_blocks = [
            block
            for block in self._reserved_blocks
            if block is not None and block.isValid()
        ]
        old_by_position = {block.position(): block for block in old_blocks}
        new_blocks: list[object] = []

        was_modified = document.isModified()
        editor_blocker = QSignalBlocker(editor)
        document_blocker = QSignalBlocker(document)
        try:
            for position, block in old_by_position.items():
                if position in reservations:
                    continue
                block_format = block.blockFormat()
                if bool(block_format.property(self._BLOCK_SPACE_PROPERTY)):
                    block_format.setBottomMargin(0.0)
                    block_format.clearProperty(self._BLOCK_SPACE_PROPERTY)
                    QTextCursor(block).setBlockFormat(block_format)

            for position, height in reservations.items():
                block = document.findBlock(int(position))
                if not block.isValid():
                    continue
                target = float(max(int(height), 0))
                block_format = block.blockFormat()
                current = float(block_format.bottomMargin())
                owned = bool(block_format.property(self._BLOCK_SPACE_PROPERTY))
                if not owned or abs(current - target) > 0.5:
                    block_format.setBottomMargin(target)
                    block_format.setProperty(self._BLOCK_SPACE_PROPERTY, True)
                    QTextCursor(block).setBlockFormat(block_format)
                new_blocks.append(block)
            document.setModified(was_modified)
        finally:
            del document_blocker
            del editor_blocker

        self._reserved_blocks = new_blocks
        self._restore_scroll_anchor(editor, scroll_anchor)
        QTimer.singleShot(
            0,
            lambda e=editor, a=scroll_anchor, g=int(generation): self._restore_scroll_anchor_if_current(
                e,
                a,
                g,
            ),
        )

    def _clear_reserved_space(self, editor: LatexEditor | None) -> None:
        """Remove only margins owned by this controller, without scanning the document."""
        if not self._editor_is_alive(editor):
            self._reserved_blocks.clear()
            return
        self._update_reserved_space(editor, {})

    @staticmethod
    def _capture_scroll_anchor(editor: LatexEditor) -> dict[str, int | bool]:
        """Capture the top visible source anchor and whether the viewport is at bottom."""
        scrollbar = editor.verticalScrollBar()
        maximum = int(scrollbar.maximum())
        value = int(scrollbar.value())
        cursor = editor.cursorForPosition(QPoint(2, 2))
        return {
            "value": value,
            "maximum": maximum,
            "at_bottom": maximum - value <= 2,
            "position": int(cursor.position()),
            "y": int(editor.cursorRect(cursor).top()),
        }

    def _restore_scroll_anchor_if_current(
        self,
        editor: LatexEditor,
        anchor: dict[str, int | bool],
        generation: int,
    ) -> None:
        """Restore the anchor after Qt has recalculated document geometry."""
        if generation and generation != self._request_generation:
            return
        self._restore_scroll_anchor(editor, anchor)

    def _restore_scroll_anchor(
        self,
        editor: LatexEditor,
        anchor: dict[str, int | bool],
    ) -> None:
        """Keep bottom pinned or keep the same top source position stationary."""
        if not self._editor_is_alive(editor) or editor is not self._active_editor:
            return
        scrollbar = editor.verticalScrollBar()
        if bool(anchor.get("at_bottom", False)):
            scrollbar.setValue(scrollbar.maximum())
            return

        document = editor.document()
        if not isValid(document):
            return
        cursor = QTextCursor(document)
        cursor.setPosition(
            max(
                0,
                min(
                    int(anchor.get("position", 0)),
                    max(document.characterCount() - 1, 0),
                ),
            )
        )
        anchor_y = int(anchor.get("y", 0))
        current_y = int(editor.cursorRect(cursor).top())
        current_value = int(scrollbar.value())
        scrollbar.setValue(
            self._anchored_scroll_value(
                current_value,
                anchor_y,
                current_y,
            )
        )

    @staticmethod
    def _anchored_scroll_value(
        current_value: int,
        anchor_y: int,
        current_y: int,
    ) -> int:
        """Return an idempotent scroll correction for a preserved source anchor."""
        return int(current_value) + int(current_y) - int(anchor_y)

    def _remember_image(self, raw: str, image: QImage) -> None:
        """Keep a bounded insertion-ordered cache of successfully rendered snippets."""
        key = str(raw).strip()
        if not key:
            return
        self._image_cache.pop(key, None)
        self._image_cache[key] = QImage(image)
        while len(self._image_cache) > self._CACHE_LIMIT:
            oldest = next(iter(self._image_cache))
            self._image_cache.pop(oldest, None)

    def _trim_failed_cache(self) -> None:
        """Bound failed-snippet memory while preserving recent invalid edits."""
        while len(self._failed_snippets) > self._CACHE_LIMIT:
            self._failed_snippets.pop()

    def _widget(self, index: int, parent) -> SourceLatexPreviewWidget:
        """Return or create the overlay widget for a preview index."""
        while len(self._widgets) <= index:
            self._widgets.append(SourceLatexPreviewWidget(parent))
        widget = self._widgets[index]
        if not isValid(widget):
            widget = SourceLatexPreviewWidget(parent)
            self._widgets[index] = widget
        elif widget.parent() is not parent:
            widget.setParent(parent)
        return widget

    def _hide_unused(self, used: int) -> None:
        """Hide overlay widgets that are not used by the current layout."""
        for widget in self._widgets[max(int(used), 0) :]:
            try:
                if isValid(widget):
                    widget.hide()
            except RuntimeError:
                pass

    def _clear_widgets(self) -> None:
        """Destroy all overlay widgets owned by the controller."""
        for widget in self._widgets:
            try:
                if isValid(widget):
                    widget.hide()
                    widget.deleteLater()
            except RuntimeError:
                pass
        self._widgets.clear()

