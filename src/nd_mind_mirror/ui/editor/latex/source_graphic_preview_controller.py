from __future__ import annotations

from contextlib import nullcontext

from nd_mind_mirror.ui.editor.latex.source_graphic_preview_controller_core import (
    SourceGraphicPreviewController as SourceGraphicPreviewControllerCore,
)


class SourceGraphicPreviewController(SourceGraphicPreviewControllerCore):
    """Handle inline graphic previews for ordinary and windowed Source editors."""

    def eventFilter(self, watched, event) -> bool:
        try:
            return super().eventFilter(watched, event)
        except RuntimeError:
            self._reset_deleted_editor()
            return False

    def refresh_positions(self) -> None:
        """Never scan the full canonical source while a large Source is scrolling."""
        editor = self._editor_panel.current_editor()
        scope_factory = getattr(editor, "_visible_plain_text_scope", None)
        scope = scope_factory() if callable(scope_factory) else nullcontext()
        try:
            with scope:
                super().refresh_positions()
        except RuntimeError:
            self._reset_deleted_editor()

    def _rebuild_layout(self) -> None:
        editor = self._editor_panel.current_editor()
        if editor is None:
            self._detach_editor()
            self._hide_unused(0)
            return

        scope_factory = getattr(editor, "_visible_plain_text_scope", None)
        scope = scope_factory() if callable(scope_factory) else nullcontext()
        try:
            with scope:
                super()._rebuild_layout()
        except RuntimeError:
            self._reset_deleted_editor()

    def _detach_editor(self) -> None:
        editor = self._active_editor
        if editor is None:
            return
        try:
            super()._detach_editor()
        except RuntimeError:
            self._reset_deleted_editor(clear_widgets=True)

    @staticmethod
    def _clear_layout_margins(editor) -> None:
        try:
            SourceGraphicPreviewControllerCore._clear_layout_margins(editor)
        except RuntimeError:
            return

    def _restore_horizontal_scroll(self, editor) -> None:
        try:
            super()._restore_horizontal_scroll(editor)
        except RuntimeError:
            self._horizontal_overflow_active = False

    def _reset_deleted_editor(self, clear_widgets: bool = False) -> None:
        self._active_editor = None
        self._layout = []
        self._image_signatures = {}
        self._layout_viewport_width = -1
        self._horizontal_overflow_active = False
        if clear_widgets:
            self._clear_widgets()
        else:
            self._hide_unused(0)
