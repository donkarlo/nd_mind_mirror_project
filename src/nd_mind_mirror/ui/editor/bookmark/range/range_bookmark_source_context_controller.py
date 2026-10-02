"""Source context menu for canonical range bookmarks and graphic actions."""

from __future__ import annotations


class RangeBookmarkSourceContextController:
    """Expose Add/Remove Bookmark according to the right-clicked canonical range."""

    def __init__(self, editor) -> None:
        self._editor = editor

    def show(self, event) -> None:
        editor = self._editor
        click_cursor = editor.cursorForPosition(event.pos())
        click_position = editor._canonical_offset_for_source_position(
            click_cursor.position()
        )
        state = editor.range_bookmark_context_at(click_position)

        source = editor.toPlainText()
        existing = editor._graphic_manager.find_reference(
            source,
            editor._source_path,
            click_position,
        )
        tikz_reference = editor._tikz_document_manager.find_reference(
            source,
            editor._source_path,
            click_position,
        )

        menu = editor.createStandardContextMenu()
        editor._remove_legacy_bookmark_actions(menu)
        bookmark_action = None
        if state["action"] != "none":
            menu.addSeparator()
            bookmark_action = menu.addAction(str(state["label"]))

        spell_controller = getattr(editor, "_spell_check_controller", None)
        spell_actions = []
        if spell_controller is not None:
            spell_actions = spell_controller.append_context_actions(
                menu,
                editor,
                click_cursor.position(),
                source_mode=True,
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

        decorate_menu = getattr(editor.window(), "decorate_editor_menu", None)
        if callable(decorate_menu):
            menu.addSeparator()
            decorate_menu(menu, editor._source_path)

        chosen = menu.exec(event.globalPos())
        if (
            spell_controller is not None
            and spell_controller.execute_context_action(chosen, spell_actions)
        ):
            return
        if bookmark_action is not None and chosen == bookmark_action:
            editor.execute_range_bookmark_state(state)
            return
        if chosen == tikz_action:
            editor._handle_tikz_context_request(click_position, tikz_reference)
            return
        if chosen != graphic_action:
            return
        if existing is not None:
            editor._edit_graphic_image_in_ipad(existing.image_path)
            return

        current = editor.textCursor()
        if not current.hasSelection():
            editor.setTextCursor(click_cursor)
        line, column = editor.active_source_location()
        editor._handle_graphic_request(line, column)
