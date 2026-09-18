"""Per-tab Source/Visual state preservation for LaTeX editors."""

from __future__ import annotations

from nd_mind_mirror.ui.editor.cursor.cursor_appearance_controller import (
    CursorAppearanceController,
)


class LatexTabViewStateMixin:
    """Preserve the active LaTeX view, caret and visible source anchor per tab."""

    def apply_cursor_preferences(
        self,
        *,
        color: str,
        size_percent: int,
        thickness: int,
    ) -> None:
        super().apply_cursor_preferences(
            color=color,
            size_percent=size_percent,
            thickness=thickness,
        )
        visual_editor = getattr(self, "_visual_editor", None)
        if visual_editor is None:
            return
        controller = getattr(
            self,
            "_visual_cursor_appearance_controller",
            None,
        )
        if controller is None:
            controller = CursorAppearanceController(visual_editor)
            self._visual_cursor_appearance_controller = controller
        controller.apply(
            color=color,
            size_percent=size_percent,
            thickness=thickness,
        )

    def view_state(self) -> dict[str, object]:
        state: dict[str, object] = dict(super().view_state())
        state["edit_mode"] = str(self.edit_mode)
        cursor_line, cursor_column = self.active_source_location()
        view_line, view_column = self.first_visible_source_position()
        state["active_source_line"] = int(cursor_line)
        state["active_source_column"] = int(cursor_column)
        state["visible_source_line"] = int(view_line)
        state["visible_source_column"] = int(view_column)
        return state

    def restore_view_state(self, state: dict | None) -> None:
        if not isinstance(state, dict):
            return

        # Always restore the canonical Source QTextEdit state first. This also
        # preserves Source position when the saved active view was Visual.
        super().restore_view_state(state)

        mode = (
            "visual"
            if str(state.get("edit_mode", "source")).strip().lower() == "visual"
            else "source"
        )
        self.set_edit_mode(mode)

        if mode != "visual":
            # Source vertical/horizontal scrollbar values were restored by the
            # base class and must not be disturbed by an extra navigation call.
            return

        try:
            visible_line = max(int(state.get("visible_source_line", 1)), 1)
            visible_column = max(int(state.get("visible_source_column", 1)), 1)
            cursor_line = max(int(state.get("active_source_line", 1)), 1)
            cursor_column = max(int(state.get("active_source_column", 1)), 1)
        except (TypeError, ValueError):
            return

        # Recreate the viewport anchor first, then restore the caret. The caret
        # was visible when captured, so ensure-visible should not move the page.
        self.go_to_source_location(
            visible_line,
            visible_column,
            align_top=True,
        )
        self.go_to_source_location(
            cursor_line,
            cursor_column,
            align_top=False,
        )
