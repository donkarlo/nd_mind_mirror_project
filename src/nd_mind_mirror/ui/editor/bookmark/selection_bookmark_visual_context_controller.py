"""Add selection bookmarking to the Visual editor context menu."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject


class SelectionBookmarkVisualContextController(QObject):
    """Expose Bookmark Selection without removing Visual's existing actions."""

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

        captured = self._selection_controller.capture_selection()
        if captured is None:
            return super().eventFilter(watched, event)

        menu = watched.createStandardContextMenu()
        menu.addSeparator()
        bookmark_action = menu.addAction("Bookmark Selection")
        menu.addSeparator()

        click_cursor = watched.cursorForPosition(event.pos())
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
        update_action = menu.addAction("Update selected LaTeX source…")
        insert_action = menu.addAction("Insert raw LaTeX here…")

        chosen = menu.exec(event.globalPos())
        if chosen == bookmark_action:
            self._selection_controller.toggle_captured_selection(*captured)
        elif chosen == graphic_action:
            line, column = watched.current_source_location()
            watched.graphic_requested.emit(line, column)
        elif chosen == update_action:
            watched._edit_selected_latex_source()
        elif chosen == insert_action:
            watched._edit_raw_latex_at_cursor()

        event.accept()
        return True
