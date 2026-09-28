"""LaTeX editor that performs presentation work only for the active edit mode."""

from __future__ import annotations

from PySide6.QtGui import QTextCursor

from nd_mind_mirror.ui.editor.latex.core.latex_editor_core import (
    LatexEditor as CoreLatexEditor,
)


class ModeIsolatedLatexEditor(CoreLatexEditor):
    """Keep hidden Source/Visual projections dormant until their mode is activated."""

    def __init__(self, *args, **kwargs) -> None:
        self._visual_source_cache: str | None = None
        super().__init__(*args, **kwargs)

    def toPlainText(self) -> str:
        """Return the cached canonical source in Visual mode without serializing hidden Source."""
        if getattr(self, "_edit_mode", "source") == "visual" and self._visual_source_cache is not None:
            return self._visual_source_cache
        return super().toPlainText()

    def set_content(self, content: str) -> None:
        """Replace canonical content while keeping the Visual source cache coherent."""
        self._visual_source_cache = None
        super().set_content(content)
        if self.edit_mode == "visual":
            self._visual_source_cache = str(content)

    def set_edit_mode(self, mode: str) -> None:
        """Switch modes and attach expensive Source presentation only when Source is visible."""
        requested = "visual" if str(mode).strip().lower() == "visual" else "source"
        previous = self.edit_mode
        if requested == "visual" and previous != "visual":
            self._visual_source_cache = self._canonical_source_text()
        super().set_edit_mode(requested)
        if requested == previous:
            return
        if requested == "visual":
            self._suspend_source_presentation()
        else:
            self._visual_source_cache = None
            self._resume_source_presentation()

    def _suspend_source_presentation(self) -> None:
        """Suspend Source-only presentation and maintenance while Visual is active."""
        self._bookmark_relocation_timer.stop()
        highlighter = getattr(self, "_highlighter", None)
        if highlighter is not None:
            highlighter.setDocument(None)
        line_numbers = getattr(self, "_nd_logical_line_numbers", None)
        if line_numbers is not None:
            line_numbers.set_active(False)

    def _resume_source_presentation(self) -> None:
        """Resume Source-only presentation after an explicit switch back to Source."""
        highlighter = getattr(self, "_highlighter", None)
        if highlighter is not None and highlighter.document() is not self.document():
            highlighter.setDocument(self.document())
        line_numbers = getattr(self, "_nd_logical_line_numbers", None)
        if line_numbers is not None:
            line_numbers.set_active(True)
        self._schedule_bookmark_relocation()

    def _schedule_bookmark_relocation(self) -> None:
        """Relocate Source bookmarks only while Source mode is active."""
        if getattr(self, "_edit_mode", "source") != "source":
            return
        super()._schedule_bookmark_relocation()

    def _on_source_cursor_changed(self) -> None:
        """Emit Source cursor state without updating the hidden Visual cursor."""
        if self._syncing_cursor_views or self.edit_mode != "source":
            return
        self.active_cursor_changed.emit()

    def _on_visual_cursor_changed(self) -> None:
        """Emit Visual cursor state without updating the hidden Source cursor."""
        if self._syncing_cursor_views or self.edit_mode != "visual":
            return
        self.active_cursor_changed.emit()

    def _apply_visual_source(self, source: str) -> None:
        """Apply a Visual edit incrementally without formatting or rebuilding all Source text."""
        if self._syncing_from_visual:
            return

        updated = str(source)
        current = self._visual_source_cache
        if current is None:
            current = self._canonical_source_text()
        if updated == current:
            return

        prefix = self._common_prefix_length(current, updated)
        suffix = self._common_suffix_length(current, updated, prefix)
        current_end = len(current) - suffix
        updated_end = len(updated) - suffix

        self._syncing_from_visual = True
        self._syncing_cursor_views = True
        try:
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            cursor.setPosition(prefix)
            cursor.setPosition(current_end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(updated[prefix:updated_end])
            cursor.endEditBlock()
            self.document().setModified(True)
            self._visual_source_cache = updated
            self._visual_dirty = False
        finally:
            self._syncing_cursor_views = False
            self._syncing_from_visual = False

        if self.edit_mode == "visual":
            # The hidden Source cursor is intentionally left untouched. Cursor
            # alignment happens once, when the user explicitly switches modes.
            self.active_cursor_changed.emit()

    def _flush_content(self) -> None:
        """Emit the complete canonical source even when Source is virtualized."""
        if self.edit_mode == "visual":
            self.content_changed.emit(self._canonical_source_text())
            return
        super()._flush_content()

    def _canonical_source_text(self) -> str:
        """Return the complete source without bypassing a large editor's buffer."""
        provider = getattr(self, "canonical_source", None)
        if callable(provider):
            try:
                return str(provider())
            except (AttributeError, RuntimeError):
                pass
        if self.edit_mode == "visual" and self._visual_source_cache is not None:
            return str(self._visual_source_cache)
        return str(super().toPlainText())

    @staticmethod
    def _common_prefix_length(left: str, right: str) -> int:
        """Return the unchanged prefix length using bounded chunk comparisons."""
        limit = min(len(left), len(right))
        index = 0
        chunk = 4096
        while index + chunk <= limit and left[index : index + chunk] == right[index : index + chunk]:
            index += chunk
        while index < limit and left[index] == right[index]:
            index += 1
        return index

    @staticmethod
    def _common_suffix_length(left: str, right: str, prefix: int) -> int:
        """Return the unchanged suffix length without overlapping the common prefix."""
        left_remaining = len(left) - int(prefix)
        right_remaining = len(right) - int(prefix)
        limit = min(left_remaining, right_remaining)
        index = 0
        chunk = 4096
        while (
            index + chunk <= limit
            and left[len(left) - index - chunk : len(left) - index]
            == right[len(right) - index - chunk : len(right) - index]
        ):
            index += chunk
        while index < limit and left[-index - 1] == right[-index - 1]:
            index += 1
        return index
