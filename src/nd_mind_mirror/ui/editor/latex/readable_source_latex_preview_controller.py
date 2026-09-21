"""Readable Source LaTeX previews with settled geometry-cached scrolling."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage, QTextCursor
from shiboken6 import isValid

from nd_mind_mirror.ui.editor.latex.source_latex_preview_controller import (
    SourceLatexPreviewController,
)
from nd_mind_mirror.ui.editor.latex.source_latex_preview_size_policy import (
    SourceLatexPreviewSizePolicy,
)
from nd_mind_mirror.ui.editor.latex.source_preview_geometry_index import (
    SourcePreviewGeometryIndex,
)


class ReadableSourceLatexPreviewController(SourceLatexPreviewController):
    """Keep readable Source previews while removing QTextDocument work from scrolling."""

    _SCROLL_REFRESH_MS = 0
    _GEOMETRY_SETTLE_MS = 16

    def __init__(self, editor_panel, parent=None) -> None:
        """Initialize cached geometry and defer geometry reads until layout has settled."""
        self._geometry_index = SourcePreviewGeometryIndex()
        self._geometry_ready = False
        self._caching_geometry = False
        super().__init__(editor_panel, parent)

        self._scroll_refresh_timer = QTimer(self)
        self._scroll_refresh_timer.setSingleShot(True)
        self._scroll_refresh_timer.setInterval(self._SCROLL_REFRESH_MS)
        self._scroll_refresh_timer.timeout.connect(self.refresh_positions)

        self._geometry_settle_timer = QTimer(self)
        self._geometry_settle_timer.setSingleShot(True)
        self._geometry_settle_timer.setInterval(self._GEOMETRY_SETTLE_MS)
        self._geometry_settle_timer.timeout.connect(self._settle_layout_geometry)

    @staticmethod
    def _logical_size(
        image: QImage,
        *,
        kind: str,
        display: bool,
        line_height: int,
        available: int,
    ) -> tuple[int, int]:
        """Delegate preview sizing to the shared readable size policy."""
        return SourceLatexPreviewSizePolicy.logical_size(
            image_width=image.width(),
            image_height=image.height(),
            kind=kind,
            display=display,
            line_height=line_height,
            available=available,
        )

    def _commit_request(self, request: dict[str, object]) -> None:
        """Invalidate pixel geometry before Source margins are changed by a new layout."""
        self._invalidate_geometry()
        super()._commit_request(request)

    def refresh_positions(self) -> None:
        """Position visible formula/table overlays only from settled cached geometry."""
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
        if not self._layout:
            self._hide_unused(0)
            return

        if not self._geometry_ready:
            self._schedule_geometry_settle()
            self._hide_unused(0)
            return

        vertical = int(editor.verticalScrollBar().value())
        horizontal = int(editor.horizontalScrollBar().value())
        viewport_height = int(viewport.height())
        viewport_width = int(viewport.width())
        used = 0

        for index in self._geometry_index.candidate_indices(
            vertical,
            viewport_height,
        ):
            item = self._layout[index]
            height = int(item["height"])
            y = int(item["document_y"]) - vertical
            if y > viewport_height or y + height < 0:
                continue

            width = int(item["width"])
            if bool(item["inline"]):
                x = int(item["document_x"]) - horizontal
            else:
                x = max((viewport_width - width) // 2, 0)

            widget = self._widget(used, viewport)
            if widget.display_image(
                item["image"],
                target_width=width,
                x=x,
                y=y,
            ):
                used += 1
        self._hide_unused(used)

    def _schedule_geometry_settle(self) -> None:
        """Wait one frame after QTextBlock margin/scroll-anchor updates before caching."""
        if not self._geometry_settle_timer.isActive():
            self._geometry_settle_timer.start()

    def _settle_layout_geometry(self) -> None:
        """Cache geometry only after Qt has applied Source margins and anchor restoration."""
        editor = self._current_live_editor()
        if editor is None or editor is not self._active_editor or editor.edit_mode != "source":
            return
        viewport = self._viewport(editor)
        if viewport is None or viewport.width() != self._layout_viewport_width:
            self.schedule_refresh()
            return
        if not self._layout:
            self._hide_unused(0)
            return
        self._cache_layout_geometry(editor)
        if self._geometry_ready:
            self.refresh_positions()

    def _cache_layout_geometry(self, editor) -> None:
        """Resolve Source preview block/cursor geometry once per settled rebuilt layout."""
        if self._caching_geometry:
            return

        self._caching_geometry = True
        self._geometry_ready = False
        self._geometry_index.clear()
        try:
            document = editor.document()
            viewport = self._viewport(editor)
            if viewport is None:
                return

            vertical = int(editor.verticalScrollBar().value())
            horizontal = int(editor.horizontalScrollBar().value())
            geometry: list[tuple[int, int, int]] = []

            for index, item in enumerate(self._layout):
                block = document.findBlock(int(item["block_position"]))
                if not block.isValid():
                    continue

                block_rect = editor.cursorRect(QTextCursor(block))
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
                    document_y = (
                        int(anchor_rect.top())
                        + (int(anchor_rect.height()) - int(item["height"])) // 2
                        + vertical
                    )
                    reserved_width = int(item.get("reserved_width", 0))
                    item["document_x"] = (
                        int(anchor_rect.left())
                        - reserved_width
                        + self._GAP_PX
                        + horizontal
                    )
                else:
                    document_y = (
                        int(block_rect.bottom())
                        + self._GAP_PX
                        + int(item["offset_y"])
                        + vertical
                    )
                item["document_y"] = document_y

                geometry.append((index, document_y, int(item["height"])))

            self._geometry_index.rebuild(geometry)
            self._geometry_ready = True
        finally:
            self._caching_geometry = False

    def _on_scroll(self, _value: int) -> None:
        """Coalesce Source scroll events; geometry lookup is intentionally absent."""
        try:
            if not self._scroll_refresh_timer.isActive():
                self._scroll_refresh_timer.start()
        except RuntimeError:
            self._reset_dead_editor()

    def _invalidate_geometry(self) -> None:
        """Drop geometry whenever Source block margins or layout contents change."""
        self._geometry_index.clear()
        self._geometry_ready = False
        if hasattr(self, "_geometry_settle_timer"):
            try:
                self._geometry_settle_timer.stop()
            except RuntimeError:
                pass

    def _detach_editor(self) -> None:
        """Drop geometry cached for the previous Source editor."""
        try:
            if hasattr(self, "_scroll_refresh_timer"):
                self._scroll_refresh_timer.stop()
            if hasattr(self, "_geometry_settle_timer"):
                self._geometry_settle_timer.stop()
        except RuntimeError:
            pass
        self._geometry_index.clear()
        self._geometry_ready = False
        super()._detach_editor()

    def _clear_state(self, viewport_width: int = -1) -> None:
        """Clear overlay and geometry state together."""
        self._invalidate_geometry()
        super()._clear_state(viewport_width)
