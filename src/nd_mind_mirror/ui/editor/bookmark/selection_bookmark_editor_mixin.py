"""Add persistent selection-aware bookmarks and TikZ context actions to LaTeX."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.selection_bookmark_relocator import (
    SelectionBookmarkRelocator,
)
from nd_mind_mirror.graphic.tikz.tikz_bridge_notifier import TikZBridgeNotifier
from nd_mind_mirror.graphic.tikz.tikz_document_manager import (
    TikZDocumentManager,
    TikZReference,
)
from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_context_controller import (
    SelectionBookmarkContextController,
)
from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_visual_context_controller import (
    SelectionBookmarkVisualContextController,
)


class SelectionBookmarkEditorMixin:
    """Extend Source/Visual bookmarks and context menus over canonical LaTeX source."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._bookmark_relocator = SelectionBookmarkRelocator()
        self._selection_bookmark_context = SelectionBookmarkContextController(self)
        self._tikz_document_manager = TikZDocumentManager(
            self._app_settings.search_default_path
        )
        self._tikz_bridge_notifier = TikZBridgeNotifier(
            workspace_root=self._app_settings.search_default_path
        )
        self._selection_bookmark_visual_context = (
            SelectionBookmarkVisualContextController(
                self,
                self._selection_bookmark_context,
                self,
            )
        )

    def set_bookmarks(self, bookmarks: list[dict[str, object]] | None) -> None:
        normalized: list[dict[str, object]] = []
        for raw in bookmarks or []:
            if not isinstance(raw, dict):
                continue
            try:
                line = max(int(raw.get("line", 1)), 1)
            except (TypeError, ValueError):
                line = 1
            try:
                column = max(int(raw.get("column", 1)), 1)
            except (TypeError, ValueError):
                column = 1

            item: dict[str, object] = {
                "line": line,
                "column": column,
                "name": str(raw.get("name", "")).strip(),
                "anchor": str(raw.get("anchor", "")),
            }
            selection = SelectionBookmarkRelocator.normalize_selection(
                raw.get("selection"),
                self.toPlainText(),
            )
            if selection is not None:
                item["selection"] = selection
            normalized.append(item)

        self._bookmarks, _changed = self._bookmark_relocator.relocate(
            normalized,
            self.toPlainText(),
        )
        self._update_bookmark_gutters()

    def toggle_bookmark_at_cursor(self) -> None:
        """Use the active selection when present, otherwise preserve line bookmarks."""
        captured = self._selection_bookmark_context.capture_selection()
        if captured is None:
            super().toggle_bookmark_at_cursor()
            return
        self._toggle_selection_bookmark(*captured)

    def toggle_bookmark_selection(self) -> bool:
        captured = self._selection_bookmark_context.capture_selection()
        if captured is None:
            return False
        self._selection_bookmark_context.toggle_captured_selection(*captured)
        return True

    def restore_bookmark_selection(self, bookmark: dict[str, object]) -> bool:
        selection = SelectionBookmarkRelocator.normalize_selection(
            bookmark.get("selection"),
            self.toPlainText(),
        )
        if selection is None:
            return False

        anchor = tuple(selection["anchor"])
        position = tuple(selection["position"])
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
        return True

    def contextMenuEvent(self, event) -> None:
        """Expose bookmark, image, and context-sensitive TikZ actions on Source."""
        click_cursor = self.cursorForPosition(event.pos())
        click_position = click_cursor.position()
        selection_cursor = self.textCursor()

        captured = None
        if (
            selection_cursor.hasSelection()
            and selection_cursor.selectionStart()
            <= click_position
            <= selection_cursor.selectionEnd()
        ):
            captured = self._selection_bookmark_context.capture_selection()

        source = self.toPlainText()
        existing = self._graphic_manager.find_reference(
            source,
            self._source_path,
            click_position,
        )
        tikz_reference = self._tikz_document_manager.find_reference(
            source,
            self._source_path,
            click_position,
        )

        menu = self.createStandardContextMenu()
        self._remove_legacy_bookmark_actions(menu)
        menu.addSeparator()
        bookmark_action = menu.addAction(
            "Bookmark Selection"
            if captured is not None
            else "Toggle Bookmark Here"
        )
        menu.addSeparator()
        graphic_action = menu.addAction(
            "Edit image in iPad…"
            if existing is not None
            else "Insert image in iPad…"
        )
        tikz_action = menu.addAction(
            "Edit TikZ in iPad…"
            if tikz_reference is not None
            else "Create TikZ in iPad…"
        )

        chosen = menu.exec(event.globalPos())
        if chosen == bookmark_action:
            if captured is not None:
                self._selection_bookmark_context.toggle_captured_selection(
                    *captured
                )
            else:
                line, column = self._source_location_for_position(click_position)
                self._toggle_bookmark(line, column)
            return
        if chosen == tikz_action:
            self._handle_tikz_context_request(click_position, tikz_reference)
            return
        if chosen != graphic_action:
            return

        current = self.textCursor()
        if not current.hasSelection():
            self.setTextCursor(click_cursor)
        line, column = self.active_source_location()
        self._handle_graphic_request(line, column)

    def _handle_tikz_context_request(
        self,
        position: int,
        reference: TikZReference | None = None,
    ) -> None:
        """Open an existing TikZ child or create and insert a new TikZ input."""
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
        cursor.setPosition(position)
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

    @staticmethod
    def _tikz_insertion_text(source: str, position: int, tex_reference: str) -> str:
        """Place a generated TikZ input on its own line at the clicked source position."""
        position = max(0, min(int(position), len(source)))
        prefix = "" if position == 0 or source[position - 1] == "\n" else "\n"
        suffix = "" if position >= len(source) or source[position] == "\n" else "\n"
        return f"{prefix}{tex_reference}\n{suffix}"

    @staticmethod
    def _remove_legacy_bookmark_actions(menu) -> None:
        """Remove runtime-patched bookmark items so only the canonical action remains."""
        legacy_labels = {
            "Bookmark Here",
            "Bookmark Selection",
            "Toggle Bookmark Here",
        }
        for action in list(menu.actions()):
            label = action.text().replace("&", "").strip()
            if label not in legacy_labels:
                continue
            menu.removeAction(action)
            if action.parent() is menu:
                action.deleteLater()

    def _toggle_selection_bookmark(
        self,
        anchor: tuple[int, int],
        position: tuple[int, int],
    ) -> None:
        start, _end = self._ordered_source_locations(anchor, position)
        line, column = start
        existing = self._bookmark_for_location(line, column)
        if existing is not None:
            self._bookmarks.remove(existing)
            self._emit_bookmarks_changed()
            return

        source = self.toPlainText()
        source_lines = source.splitlines() or [""]
        line = max(1, min(int(line), len(source_lines)))
        column = max(1, min(int(column), len(source_lines[line - 1]) + 1))
        self._bookmarks.append(
            {
                "line": line,
                "column": column,
                "name": "",
                "anchor": self._bookmark_relocator.normalize_line(
                    source_lines[line - 1]
                ),
                "selection": {
                    "anchor": [int(anchor[0]), int(anchor[1])],
                    "position": [int(position[0]), int(position[1])],
                    "text": self._selected_bookmark_text(),
                },
            }
        )
        self._bookmarks.sort(
            key=lambda item: (
                int(item.get("line", 1)),
                int(item.get("column", 1)),
            )
        )
        self._emit_bookmarks_changed()

    def _ordered_source_locations(
        self,
        first: tuple[int, int],
        second: tuple[int, int],
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        first_position = self._source_position_for_location(first)
        second_position = self._source_position_for_location(second)
        if first_position <= second_position:
            return first, second
        return second, first

    def _selected_bookmark_text(self) -> str:
        cursor = (
            self._visual_editor.textCursor()
            if self._edit_mode == "visual"
            else self.textCursor()
        )
        if not cursor.hasSelection():
            return ""
        return (
            cursor.selectedText()
            .replace("\u2029", "\n")
            .replace("\u2028", "\n")
            .strip()
        )[:480]
