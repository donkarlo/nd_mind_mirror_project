"""Visual context menu for native LaTeX, spelling, and image actions."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject


class RangeBookmarkVisualContextController(QObject):
    """Provide Visual editing actions without legacy bookmark commands."""

    _INSTALLED_PROPERTY = "nd_range_bookmark_visual_context"

    def __init__(self, editor, parent=None) -> None:
        super().__init__(parent)
        self._editor = editor
        visual = editor._visual_editor
        visual.setProperty(self._INSTALLED_PROPERTY, True)
        visual.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() != QEvent.Type.ContextMenu
            or not bool(watched.property(self._INSTALLED_PROPERTY))
        ):
            return super().eventFilter(watched, event)

        click_cursor = watched.cursorForPosition(event.pos())
        click_location = watched.source_location_for_position(click_cursor.position())
        click_position = self._editor._canonical_offset_for_location(click_location)
        source_position = self._editor._source_position_for_location(click_location)
        source = self._editor._range_bookmark_source_text()
        graphic_reference = self._editor._graphic_manager.find_reference(
            source,
            self._editor.source_path,
            source_position,
        )
        tikz_reference = self._editor._tikz_document_manager.find_reference(
            source,
            self._editor.source_path,
            source_position,
        )

        menu = watched.createStandardContextMenu()
        spell_controller = getattr(self._editor, "_spell_check_controller", None)
        spell_actions = []
        if spell_controller is not None:
            spell_actions = spell_controller.append_context_actions(
                menu,
                watched,
                click_cursor.position(),
                source_mode=False,
            )

        menu.addSeparator()
        click_meta = click_cursor.block().userData()
        raw = str(getattr(click_meta, "raw", "") or "")
        is_existing_graphic = graphic_reference is not None or (
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
        update_action.setEnabled(watched.textCursor().hasSelection())
        insert_action = menu.addAction("Insert raw LaTeX here…")

        decorate_menu = getattr(watched.window(), "decorate_editor_menu", None)
        if callable(decorate_menu):
            menu.addSeparator()
            decorate_menu(menu, self._editor.source_path)

        chosen = menu.exec(event.globalPos())
        if (
            spell_controller is not None
            and spell_controller.execute_context_action(chosen, spell_actions)
        ):
            event.accept()
            return True
        if chosen == graphic_action:
            if graphic_reference is not None:
                self._editor._edit_graphic_image_in_ipad(
                    graphic_reference.image_path
                )
            else:
                if not watched.textCursor().hasSelection():
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
