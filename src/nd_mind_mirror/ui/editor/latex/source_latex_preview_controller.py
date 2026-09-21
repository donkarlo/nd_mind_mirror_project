"""Mode-aware Source formula/table preview controller."""

from __future__ import annotations

from nd_mind_mirror.ui.editor.latex.source_preview.latex.source_latex_preview_controller_core import (
    SourceLatexPreviewController as CoreSourceLatexPreviewController,
)


class SourceLatexPreviewController(CoreSourceLatexPreviewController):
    """Run formula/table preview work only while the active LaTeX view is Source."""

    def schedule_refresh(self) -> None:
        """Avoid extraction/render timers when Source is not the active view."""
        editor = self._current_live_editor()
        if editor is None or editor.edit_mode != "source":
            self._cancel_inactive_refresh()
            return
        super().schedule_refresh()

    def _start_render(self, generation: int, snippets: list[str]) -> None:
        """Start LuaLaTeX work only for a still-active Source editor."""
        editor = self._current_live_editor()
        if editor is None or editor is not self._active_editor or editor.edit_mode != "source":
            return
        super()._start_render(generation, snippets)

    def _on_view_changed(self, *_args) -> None:
        """Cancel hidden Source work or rebuild once Source becomes visible again."""
        editor = self._current_live_editor()
        if editor is None or editor.edit_mode != "source":
            self._cancel_inactive_refresh()
            return
        super()._on_view_changed(*_args)

    def _cancel_inactive_refresh(self) -> None:
        """Drop queued Source requests without disturbing the canonical document."""
        try:
            self._refresh_timer.stop()
        except RuntimeError:
            pass
        self._request_generation += 1
        self._latest_request = None
        worker = getattr(self, "_render_worker", None)
        if worker is not None:
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                cancel()
        self._hide_unused(0)
