"""Add canonical bookmark, image, and TikZ commands to the Visual context menu."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject


class SelectionBookmarkVisualContextController(QObject):
    """Expose selection/bookmark and graphic commands without removing Visual actions."""

    _INSTALLED_PROPERTY = "nd_selection_bookmark_visual_context"

    def __init__(self, editor, selection_controller, parent=None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._selection_controller = selection_controller
        visual = editor._visual_editor
        if not bool(visual.property(self._INSTALLED_PROPERTY)):
            visual.setProperty(self._INSTALLED_PROPERTY, True)
            visual.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() != QEvent.Type.ContextMenu
            or not bool(watched.property(self._INSTALLED_PROPERTY))
        ):
            return super().eventFilter(watched, event)

        click_cursor = watched.cursorForPosition(event.pos())
        click_position = click_cursor.position()
        selection_cursor = watched.textCursor()

        captured = None
        if (
            selection_cursor.hasSelection()
            and selection_cursor.selectionStart()
            <= click_position
            <= selection_cursor.selectionEnd()
        ):
            captured = self._selection_controller.capture_selection()

        try:
            source_line, source_column = watched.source_location_for_position(
                click_position
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            source_line, source_column = watched.current_source_location()
        source_position = self._editor._source_position_for_location(
            (source_line, source_column)
        )
        tikz_reference = self._editor._tikz_document_manager.find_reference(
            self._editor.toPlainText(),
            self._editor.source_path,
            source_position,
        )

        menu = watched.createStandardContextMenu()
        self._remove_legacy_bookmark_actions(menu)
        menu.addSeparator()
        bookmark_action = menu.addAction(
            "Bookmark Selection"
            if captured is not None
            else "Toggle Bookmark Here"
        )
        menu.addSeparator()

        click_meta = click_cursor.block().userData()
        raw = str(getattr(click_meta, "raw", "") or "")
        is_existing_graphic = (
            str(getattr(click_meta, "kind", "") or "") == "graphic"
            or "\\includegraphics" in raw
            or click_cursor.charFormat().isImageFormat()
        )
        graphic_action = menu.addAction(
            "Edit image in iPad…"
            if is_existing_graphic
            else "Insert image in iPad…"
        )
        tikz_action = menu.addAction(
            "Edit TikZ in iPad…"
            if tikz_reference is not None
            else "Create TikZ in iPad…"
        )
        update_action = menu.addAction("Update selected LaTeX source…")
        update_action.setEnabled(selection_cursor.hasSelection())
        insert_action = menu.addAction("Insert raw LaTeX here…")

        chosen = menu.exec(event.globalPos())
        if chosen == bookmark_action:
            if captured is not None:
                self._selection_controller.toggle_captured_selection(*captured)
            else:
                self._editor._toggle_bookmark(source_line, source_column)
        elif chosen == graphic_action:
            if not selection_cursor.hasSelection():
                watched.setTextCursor(click_cursor)
            line, column = watched.current_source_location()
            watched.graphic_requested.emit(line, column)
        elif chosen == tikz_action:
            self._editor._handle_tikz_context_request(
                source_position,
                tikz_reference,
            )
        elif chosen == update_action:
            watched._edit_selected_latex_source()
        elif chosen == insert_action:
            watched._edit_raw_latex_at_cursor()

        event.accept()
        return True

    @staticmethod
    def _remove_legacy_bookmark_actions(menu) -> None:
        """Remove old runtime-added items before adding the canonical bookmark action."""
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
