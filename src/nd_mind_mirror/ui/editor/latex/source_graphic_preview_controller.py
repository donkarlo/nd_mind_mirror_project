"""Optimized Source graphic previews for ordinary and windowed LaTeX editors."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMenu

from nd_mind_mirror.ui.editor.latex.source_graphic_preview_controller_core import (
    SourceGraphicPreviewController as SourceGraphicPreviewControllerCore,
)
from nd_mind_mirror.ui.editor.latex.source_preview_geometry_index import (
    SourcePreviewGeometryIndex,
)


class SourceGraphicPreviewController(SourceGraphicPreviewControllerCore):
    """Keep Source image work dormant outside Source and scroll from settled geometry."""

    _SCROLL_REFRESH_MS = 0
    _GEOMETRY_SETTLE_MS = 16

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

        self._geometry_settle_timer = QTimer(self)
        self._geometry_settle_timer.setSingleShot(True)
        self._geometry_settle_timer.setInterval(self._GEOMETRY_SETTLE_MS)
        self._geometry_settle_timer.timeout.connect(self._settle_layout_geometry)
        self._sync_polling_state()

    def eventFilter(self, watched, event) -> bool:
        """Handle Source preview image context clicks and tolerate deleted Qt wrappers."""
        try:
            editor = self._active_editor
            if (
                editor is not None
                and watched is editor.viewport()
                and event.type() == QEvent.Type.ContextMenu
                and self._show_preview_image_context_menu(editor, event)
            ):
                return True
            return super().eventFilter(watched, event)
        except RuntimeError:
            self._reset_deleted_editor()
            return False

    def _show_preview_image_context_menu(self, editor, event) -> bool:
        """Offer iPad editing when the user right-clicks the rendered Source image."""
        position = event.pos()
        for widget in self._widgets:
            if not widget.isVisible() or not widget.geometry().contains(position):
                continue
            image_path = widget.image_path
            if image_path is None:
                return False
            menu = QMenu(editor)
            edit_action = menu.addAction("Edit image in iPad…")
            chosen = menu.exec(event.globalPos())
            if chosen == edit_action:
                editor._edit_graphic_image_in_ipad(image_path)
            event.accept()
            return True
        return False

    def schedule_layout_refresh(self) -> None:
        """Queue Source layout work only while Source is the active edit mode."""
        if not self._source_is_active():
            try:
                self._refresh_timer.stop()
            except RuntimeError:
                pass
            self._sync_polling_state()
            self._hide_unused(0)
            return
        self._sync_polling_state()
        super().schedule_layout_refresh()

    def refresh_positions(self) -> None:
        """Place figure previews from live Source geometry after ``\\end{figure}``."""
        if self._rebuilding_layout:
            return

        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
            return
        if editor is None or editor.edit_mode != "source":
            self._sync_polling_state()
            self._hide_unused(0)
            return

        self._sync_polling_state()
        try:
            viewport = editor.viewport()
            if viewport.width() != self._layout_viewport_width:
                self.schedule_layout_refresh()
                return
            if not self._layout:
                self._hide_unused(0)
                return

            document = editor.document()
            horizontal = int(editor.horizontalScrollBar().value())
            viewport_height = int(viewport.height())
            used = 0

            for item in self._layout:
                block = document.findBlock(int(item["end_position"]))
                if not block.isValid():
                    continue
                end_rect = editor.cursorRect(QTextCursor(block))
                image_height = int(item["height"])
                y = (
                    int(end_rect.bottom())
                    + self._IMAGE_GAP_PX
                    + int(item["offset_after_end"])
                )
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
        """Rebuild shared layout and defer geometry reads until Qt layout settles."""
        editor = self._editor_panel.current_editor()
        if editor is None:
            self._detach_editor()
            self._hide_unused(0)
            return
        if editor.edit_mode != "source":
            self._sync_polling_state()
            self._hide_unused(0)
            return

        self._invalidate_geometry()
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

        self._schedule_geometry_settle()

    def _schedule_geometry_settle(self) -> None:
        """Wait one frame after Source margins/anchors change before reading geometry."""
        if not self._geometry_settle_timer.isActive():
            self._geometry_settle_timer.start()

    def _settle_layout_geometry(self) -> None:
        """Cache layout geometry only for the still-active Source editor."""
        editor = self._editor_panel.current_editor()
        if editor is None or editor is not self._active_editor or editor.edit_mode != "source":
            return
        try:
            if editor.viewport().width() != self._layout_viewport_width:
                self.schedule_layout_refresh()
                return
        except RuntimeError:
            self._reset_deleted_editor()
            return
        self._cache_layout_geometry(editor)
        if self._geometry_ready:
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
                    int(end_rect.bottom())
                    + vertical
                    + self._IMAGE_GAP_PX
                    + int(item["offset_after_end"])
                )
                item["document_y"] = document_y
                geometry.append((index, document_y, int(item["height"])))

            self._geometry_index.rebuild(geometry)
            self._geometry_ready = True
        except RuntimeError:
            self._geometry_index.clear()
            self._geometry_ready = False

    def _on_scroll_value_changed(self, _value: int) -> None:
        """Coalesce scrollbar signals without querying document geometry."""
        if not self._source_is_active():
            return
        try:
            if not self._scroll_refresh_timer.isActive():
                self._scroll_refresh_timer.start()
        except RuntimeError:
            self._reset_deleted_editor()

    def _poll_images(self) -> None:
        """Poll raster signatures only while Source is visible."""
        if not self._source_is_active():
            self._sync_polling_state()
            return
        editor = self._editor_panel.current_editor()
        if editor is not self._active_editor:
            self.schedule_layout_refresh()
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

    def _source_is_active(self) -> bool:
        """Return whether the current editor is the Source view handled by this controller."""
        editor = self._editor_panel.current_editor()
        return bool(editor is not None and getattr(editor, "edit_mode", None) == "source")

    def _sync_polling_state(self) -> None:
        """Stop image polling completely outside Source instead of waking an idle timer."""
        timer = getattr(self, "_image_poll_timer", None)
        if timer is None:
            return
        try:
            if self._source_is_active():
                if not timer.isActive():
                    timer.start()
            elif timer.isActive():
                timer.stop()
        except RuntimeError:
            pass

    def _invalidate_geometry(self) -> None:
        """Drop cached geometry after any Source layout rebuild."""
        self._geometry_index.clear()
        self._geometry_ready = False
        timer = getattr(self, "_geometry_settle_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except RuntimeError:
                pass

    def _detach_editor(self) -> None:
        """Detach preview geometry without moving the inactive tab's visible source anchor."""
        try:
            if hasattr(self, "_scroll_refresh_timer"):
                self._scroll_refresh_timer.stop()
            if hasattr(self, "_geometry_settle_timer"):
                self._geometry_settle_timer.stop()
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
            if hasattr(self, "_geometry_settle_timer"):
                self._geometry_settle_timer.stop()
        except RuntimeError:
            pass
        self._sync_polling_state()
        if clear_widgets:
            self._clear_widgets()
        else:
            self._hide_unused(0)
