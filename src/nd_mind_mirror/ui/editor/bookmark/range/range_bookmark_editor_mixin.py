"""Unified canonical range bookmarks for regular and large LaTeX editors."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.range.range_bookmark_position_mapper import (
    RangeBookmarkPositionMapper,
)
from nd_mind_mirror.core.bookmark.range.range_bookmark_tracker import (
    RangeBookmarkTracker,
)
from nd_mind_mirror.graphic.tikz.tikz_bridge_notifier import TikZBridgeNotifier
from nd_mind_mirror.graphic.tikz.tikz_document_manager import (
    TikZDocumentManager,
    TikZReference,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_context_state_resolver import (
    RangeBookmarkContextStateResolver,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_highlighter import (
    RangeBookmarkHighlighter,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_source_context_controller import (
    RangeBookmarkSourceContextController,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_visual_context_controller import (
    RangeBookmarkVisualContextController,
)


class RangeBookmarkEditorMixin:
    """Use one character-range mechanism for normal and virtualized large text."""

    def __init__(self, *args, **kwargs) -> None:
        self._range_bookmark_suppress_document_change = True
        super().__init__(*args, **kwargs)

        self._range_bookmark_tracker = RangeBookmarkTracker(self.toPlainText())
        self._range_bookmark_state_resolver = RangeBookmarkContextStateResolver()
        self._range_bookmark_highlighter = RangeBookmarkHighlighter(self)
        self._range_bookmark_source_context = RangeBookmarkSourceContextController(self)

        self._tikz_document_manager = TikZDocumentManager(
            self._app_settings.search_default_path
        )
        self._tikz_bridge_notifier = TikZBridgeNotifier(
            workspace_root=self._app_settings.search_default_path
        )
        self._range_bookmark_visual_context = RangeBookmarkVisualContextController(
            self,
            self,
        )

        # The old gutter represented line bookmarks. Range bookmarks are shown
        # directly on the text, so both legacy bookmark gutters stay hidden.
        for gutter_name in ("_source_bookmark_gutter", "_visual_bookmark_gutter"):
            gutter = getattr(self, gutter_name, None)
            if gutter is not None:
                gutter.hide()

        self._range_bookmark_suppress_document_change = False

        # Regular and large Source editors share this same model. Large Source
        # already connects contentsChange to _synchronize_visible_change, where
        # this mixin intercepts the canonical position. Regular Source needs one
        # direct connection.
        if not hasattr(self, "_source_buffer"):
            self.document().contentsChange.connect(
                self._on_range_bookmark_document_change
            )

        self.cursorPositionChanged.connect(self._range_bookmark_highlighter.refresh)
        self._visual_editor.cursorPositionChanged.connect(
            self._range_bookmark_highlighter.refresh
        )
        self.active_view_changed.connect(self._range_bookmark_highlighter.refresh)

    def set_bookmarks(self, bookmarks: list[dict[str, object]] | None) -> None:
        self._range_bookmark_tracker.load(bookmarks, self.toPlainText())
        self._range_bookmark_highlighter.refresh()

    def bookmarks(self) -> list[dict[str, object]]:
        return self._range_bookmark_tracker.serialize()

    def toggle_bookmark_at_cursor(self) -> None:
        self.execute_range_bookmark_state(self.range_bookmark_menu_context())

    def toggle_bookmark_selection(self) -> bool:
        state = self.range_bookmark_menu_context()
        if state["action"] == "none":
            return False
        self.execute_range_bookmark_state(state)
        return True

    def range_bookmark_menu_context(self) -> dict[str, object]:
        selection = self._active_canonical_selection()
        if selection is not None:
            start, end = selection
            existing = self._range_bookmark_tracker.collection.overlapping(start, end)
            if existing is not None:
                return {
                    "action": "remove",
                    "label": "Remove Bookmark",
                    "bookmark_id": existing.id,
                }
            return {
                "action": "add",
                "label": "Add Bookmark",
                "bookmark_id": "",
            }

        position = self._active_canonical_cursor_offset()
        existing = self._range_bookmark_tracker.collection.at_position(position)
        if existing is None:
            return {"action": "none", "label": "Add Bookmark", "bookmark_id": ""}
        return {
            "action": "remove",
            "label": "Remove Bookmark",
            "bookmark_id": existing.id,
        }

    def range_bookmark_context_at(self, click_position: int) -> dict[str, object]:
        selection = self._active_canonical_selection()
        start = selection[0] if selection is not None else None
        end = selection[1] if selection is not None else None
        return self._range_bookmark_state_resolver.resolve(
            self._range_bookmark_tracker.collection,
            click_position=click_position,
            selection_start=start,
            selection_end=end,
        )

    def execute_range_bookmark_state(self, state: dict[str, object]) -> None:
        action = str(state.get("action", "none"))
        changed = False
        if action == "remove":
            changed = self._range_bookmark_tracker.collection.remove(
                str(state.get("bookmark_id", ""))
            )
        elif action == "add":
            selection = self._active_canonical_selection()
            if selection is not None:
                changed = (
                    self._range_bookmark_tracker.collection.add(
                        selection[0],
                        selection[1],
                        self.toPlainText(),
                    )
                    is not None
                )

        if changed:
            self._range_bookmark_model_changed()

    def remove_range_bookmark(self, bookmark_id: str) -> bool:
        changed = self._range_bookmark_tracker.collection.remove(bookmark_id)
        if changed:
            self._range_bookmark_model_changed()
        return changed

    def clear_range_bookmarks(self) -> bool:
        changed = self._range_bookmark_tracker.collection.clear()
        if changed:
            self._range_bookmark_model_changed()
        return changed

    def activate_range_bookmark(self, bookmark_id: str) -> bool:
        bookmark = self._range_bookmark_tracker.collection.by_id(bookmark_id)
        if bookmark is None:
            return False

        mapper = RangeBookmarkPositionMapper(self.toPlainText())
        anchor = mapper.location_for_offset(bookmark.start_char)
        position = mapper.location_for_offset(bookmark.end_char)

        if self._edit_mode == "visual":
            self._visual_editor.set_selection_from_source_locations(
                anchor,
                position,
                ensure_visible=True,
            )
            self._visual_editor.setFocus()
        else:
            self._set_source_selection_from_locations(anchor, position)
            self.ensureCursorVisible()
            self.setFocus()

        self.active_cursor_changed.emit()
        self.active_view_changed.emit()
        self._range_bookmark_highlighter.refresh()
        return True

    def contextMenuEvent(self, event) -> None:
        self._range_bookmark_source_context.show(event)

    def set_content(self, content: str) -> None:
        tracker = getattr(self, "_range_bookmark_tracker", None)
        old_source = tracker.source if tracker is not None else ""
        self._range_bookmark_suppress_document_change = True
        try:
            super().set_content(content)
        finally:
            self._range_bookmark_suppress_document_change = False

        if tracker is not None:
            changed = tracker.replace_source(str(content))
            if changed:
                self._range_bookmark_model_changed()
            else:
                self._range_bookmark_highlighter.refresh()

    def _apply_visual_source(self, source: str) -> None:
        tracker = getattr(self, "_range_bookmark_tracker", None)
        self._range_bookmark_suppress_document_change = True
        try:
            super()._apply_visual_source(source)
        finally:
            self._range_bookmark_suppress_document_change = False

        if tracker is not None:
            changed = tracker.replace_source(self.toPlainText())
            if changed:
                self._range_bookmark_model_changed()
            else:
                self._range_bookmark_highlighter.refresh()

    def _synchronize_visible_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        """Intercept the large editor's local window edit into the same tracker."""
        tracker = getattr(self, "_range_bookmark_tracker", None)
        suppressed = bool(
            getattr(self, "_range_bookmark_suppress_document_change", False)
        )
        window_loading = bool(getattr(self, "_source_window_loading", False))
        canonical_position = int(position)
        if bool(getattr(self, "source_is_windowed", False)):
            canonical_position += max(int(getattr(self, "source_window_start", 0)), 0)

        super()._synchronize_visible_change(
            position,
            chars_removed,
            chars_added,
        )

        if tracker is None or suppressed or window_loading:
            return
        changed = tracker.apply_edit(
            canonical_position,
            chars_removed,
            chars_added,
            self.toPlainText(),
        )
        if changed:
            self._range_bookmark_model_changed()
        else:
            self._range_bookmark_highlighter.refresh()

    def _on_range_bookmark_document_change(
        self,
        position: int,
        chars_removed: int,
        chars_added: int,
    ) -> None:
        if bool(getattr(self, "_range_bookmark_suppress_document_change", False)):
            return
        tracker = getattr(self, "_range_bookmark_tracker", None)
        if tracker is None:
            return
        changed = tracker.apply_edit(
            position,
            chars_removed,
            chars_added,
            self.toPlainText(),
        )
        if changed:
            self._range_bookmark_model_changed()
        else:
            self._range_bookmark_highlighter.refresh()

    def _range_bookmark_model_changed(self) -> None:
        self._range_bookmark_highlighter.refresh()
        self.bookmarks_changed.emit(self.bookmarks())

    def _active_canonical_selection(self) -> tuple[int, int] | None:
        if self._edit_mode == "visual":
            cursor = self._visual_editor.textCursor()
            if not cursor.hasSelection():
                return None
            anchor, position = self._visual_editor.source_selection_locations()
            first = self._canonical_offset_for_location(anchor)
            second = self._canonical_offset_for_location(position)
        else:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                return None
            first = self._canonical_offset_for_source_position(cursor.anchor())
            second = self._canonical_offset_for_source_position(cursor.position())

        start, end = sorted((first, second))
        return None if end <= start else (start, end)

    def _active_canonical_cursor_offset(self) -> int:
        if self._edit_mode == "visual":
            location = self._visual_editor.current_source_location()
            return self._canonical_offset_for_location(location)
        return self._canonical_offset_for_source_position(self.textCursor().position())

    def _canonical_offset_for_source_position(self, position: int) -> int:
        location = self._source_location_for_position(int(position))
        return self._canonical_offset_for_location(location)

    def _canonical_offset_for_location(self, location: tuple[int, int]) -> int:
        return RangeBookmarkPositionMapper(
            self.toPlainText()
        ).offset_for_location(location)

    def _handle_tikz_context_request(
        self,
        position: int,
        reference: TikZReference | None = None,
    ) -> None:
        if reference is None:
            reference = self._tikz_document_manager.find_reference(
                self.toPlainText(),
                self._source_path,
                position,
            )
        if reference is not None:
            self._tikz_bridge_notifier.open_on_ipad(reference.source_path)
            return

        document = self._tikz_document_manager.create_for_source(self._source_path)
        source = self.toPlainText()
        position = max(0, min(int(position), len(source)))
        cursor = self.textCursor()
        source_location = RangeBookmarkPositionMapper(source).location_for_offset(
            position
        )
        source_position = self._materialized_source_position_for_location(
            source_location
        )
        cursor.setPosition(source_position)
        cursor.insertText(
            self._tikz_insertion_text(
                source,
                position,
                document.tex_reference,
            )
        )
        self.setTextCursor(cursor)

        if self._edit_mode == "visual":
            self._visual_dirty = True
            self._refresh_visual_projection()

        self._tikz_bridge_notifier.open_on_ipad(document.source_path)

    def _materialized_source_position_for_location(
        self,
        location: tuple[int, int],
    ) -> int:
        """Return a position valid in the currently materialized Source widget."""
        if bool(getattr(self, "source_is_windowed", False)):
            local_provider = getattr(self, "_local_position_for_location", None)
            if callable(local_provider):
                local = local_provider(location)
                if local is not None:
                    return int(local)
        return int(self._source_position_for_location(location))

    @staticmethod
    def _tikz_insertion_text(source: str, position: int, tex_reference: str) -> str:
        position = max(0, min(int(position), len(source)))
        prefix = "" if position == 0 or source[position - 1] == "\n" else "\n"
        suffix = "" if position >= len(source) or source[position] == "\n" else "\n"
        return f"{prefix}{tex_reference}\n{suffix}"

    @staticmethod
    def _remove_legacy_bookmark_actions(menu) -> None:
        labels = {
            "Bookmark Here",
            "Bookmark Selection",
            "Toggle Bookmark Here",
            "Toggle Bookmark at Cursor",
            "Add Bookmark",
            "Remove Bookmark",
        }
        for action in list(menu.actions()):
            if action.text().replace("&", "").strip() not in labels:
                continue
            menu.removeAction(action)
            if action.parent() is menu:
                action.deleteLater()
