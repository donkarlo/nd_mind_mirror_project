"""Optimized Source graphic previews for ordinary and windowed LaTeX editors."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.latex.source_graphic_preview_controller_core import (
    SourceGraphicPreviewController as SourceGraphicPreviewControllerCore,
)
from nd_mind_mirror.ui.editor.latex.source_preview_geometry_index import (
    SourcePreviewGeometryIndex,
)


class SourceGraphicPreviewController(SourceGraphicPreviewControllerCore):
    """Keep Source image scrolling on cached document-space geometry."""

    _SCROLL_REFRESH_MS = 0

    def __init__(self, editor_panel, parent=None) -> None:
        """Initialize cached geometry and coalesced Source scrolling."""
        self._geometry_index = SourcePreviewGeometryIndex()
        self._geometry_ready = False
        self._rebuilding_layout = False
        super().__init__(editor_panel, parent)

        self._scroll_refresh_timer = QTimer(self)
        self._scroll_refresh_timer.setSingleShot(True)
        self._scroll_refresh_timer.setInterval(self._SCROLL_REFRESH_MS)
        self._scroll_refresh_timer.timeout.connect(self.refresh_positions)

    def eventFilter(self, watched, event) -> bool:
        """Keep deleted Qt wrappers from escaping through the preview event filter."""
        try:
            return super().eventFilter(watched, event)
        except RuntimeError:
            self._reset_deleted_editor()
            return False

    def refresh_positions(self) -> None:
        """Move visible images using cached geometry only."""
        if self._rebuilding_layout:
            return

        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
            return
        if editor is None or editor.edit_mode != "source":
            self._hide_unused(0)
            return

        try:
            viewport = editor.viewport()
            if viewport.width() != self._layout_viewport_width:
                self.schedule_layout_refresh()
                return
            if not self._layout:
                self._hide_unused(0)
                return
            if not self._geometry_ready:
                self._hide_unused(0)
                return

            vertical = int(editor.verticalScrollBar().value())
            horizontal = int(editor.horizontalScrollBar().value())
            viewport_height = int(viewport.height())
            used = 0

            for index in self._geometry_index.candidate_indices(
                vertical,
                viewport_height,
            ):
                item = self._layout[index]
                image_height = int(item["height"])
                y = int(item["document_y"]) - vertical
                if y > viewport_height or y + image_height < 0:
                    continue

                path = Path(item["path"])
                widget = self._widget(used, viewport)
                x = self._image_left(editor, int(item["outer_width"])) - horizontal
                if widget.display_image(
                    path,
                    target_width=int(item["target_width"]),
                    x=x,
                    y=y,
                    image_signature=self._image_signatures.get(path),
                ):
                    used += 1
            self._hide_unused(used)
        except RuntimeError:
            self._reset_deleted_editor()

    def _rebuild_layout(self) -> None:
        """Rebuild shared layout, then cache all expensive QTextDocument geometry once."""
        editor = self._editor_panel.current_editor()
        if editor is None:
            self._detach_editor()
            self._hide_unused(0)
            return

        self._geometry_ready = False
        self._geometry_index.clear()
        scope_factory = getattr(editor, "_visible_plain_text_scope", None)
        scope = scope_factory() if callable(scope_factory) else nullcontext()
        self._rebuilding_layout = True
        try:
            with scope:
                super()._rebuild_layout()
        except RuntimeError:
            self._reset_deleted_editor()
            return
        finally:
            self._rebuilding_layout = False

        self._cache_layout_geometry(editor)
        self.refresh_positions()

    def _cache_layout_geometry(self, editor) -> None:
        """Convert block-relative preview positions to stable document-space pixels."""
        try:
            document = editor.document()
            vertical = int(editor.verticalScrollBar().value())
            geometry: list[tuple[int, int, int]] = []

            for index, item in enumerate(self._layout):
                block = document.findBlock(int(item["end_position"]))
                if not block.isValid():
                    continue
                end_rect = editor.cursorRect(QTextCursor(block))
                document_y = (
                    int(end_rect.top())
                    + vertical
                    - int(item["distance_from_end"])
                )
                item["document_y"] = document_y
                geometry.append(
                    (index, document_y, int(item["height"]))
                )

            self._geometry_index.rebuild(geometry)
            self._geometry_ready = True
        except RuntimeError:
            self._geometry_index.clear()
            self._geometry_ready = False

    def _on_scroll_value_changed(self, _value: int) -> None:
        """Coalesce scrollbar signals without querying document geometry."""
        try:
            if not self._scroll_refresh_timer.isActive():
                self._scroll_refresh_timer.start()
        except RuntimeError:
            self._reset_deleted_editor()

    def _poll_images(self) -> None:
        """Poll raster signatures without repositioning overlays while idle."""
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
            return
        if editor is None or editor.edit_mode != "source":
            return
        try:
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
        except RuntimeError:
            self._reset_deleted_editor()

    def _detach_editor(self) -> None:
        """Detach preview geometry without moving the inactive tab's visible source anchor."""
        try:
            if hasattr(self, "_scroll_refresh_timer"):
                self._scroll_refresh_timer.stop()
        except RuntimeError:
            pass

        self._geometry_index.clear()
        self._geometry_ready = False
        editor = self._active_editor
        if editor is None:
            return

        try:
            anchor = self._capture_vertical_anchor(editor)
            super()._detach_editor()
            self._restore_vertical_anchor(editor, anchor)
            QTimer.singleShot(
                0,
                lambda item=editor, saved=anchor:
                self._restore_detached_vertical_anchor(item, saved),
            )
        except RuntimeError:
            self._reset_deleted_editor(clear_widgets=True)

    def _restore_detached_vertical_anchor(
        self,
        editor,
        anchor: tuple[int, int],
    ) -> None:
        """Restore an inactive tab after Qt finishes recalculating preview margins."""
        try:
            self._restore_vertical_anchor(editor, anchor)
        except RuntimeError:
            return

    @staticmethod
    def _clear_layout_margins(editor) -> None:
        """Clear owned layout margins while tolerating already-deleted Qt editors."""
        try:
            SourceGraphicPreviewControllerCore._clear_layout_margins(editor)
        except RuntimeError:
            return

    def _restore_horizontal_scroll(self, editor) -> None:
        """Restore the native horizontal range without leaking deleted wrappers."""
        try:
            super()._restore_horizontal_scroll(editor)
        except RuntimeError:
            self._horizontal_overflow_active = False

    def _reset_deleted_editor(self, clear_widgets: bool = False) -> None:
        """Drop all state referring to a Qt editor that no longer exists."""
        self._active_editor = None
        self._layout = []
        self._image_signatures = {}
        self._layout_viewport_width = -1
        self._horizontal_overflow_active = False
        self._geometry_index.clear()
        self._geometry_ready = False
        try:
            if hasattr(self, "_scroll_refresh_timer"):
                self._scroll_refresh_timer.stop()
        except RuntimeError:
            pass
        if clear_widgets:
            self._clear_widgets()
        else:
            self._hide_unused(0)
