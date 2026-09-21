"""Mode-aware Source TikZ preview controller."""

from __future__ import annotations

from nd_mind_mirror.ui.editor.latex.source_preview.tikz.source_tikz_preview_controller_core import (
    SourceTikZPreviewController as CoreSourceTikZPreviewController,
)


class SourceTikZPreviewController(CoreSourceTikZPreviewController):
    """Run TikZ Source projection work only while Source is the active edit mode."""

    def schedule_refresh(self) -> None:
        """Do not queue TikZ projection work for a hidden Source editor."""
        editor = self._current_live_editor()
        if editor is None or editor.edit_mode != "source":
            self._cancel_inactive_refresh()
            return
        super().schedule_refresh()

    def notify_tikz_changed(self, _path) -> None:
        """Ignore external TikZ refresh work until Source becomes visible."""
        self.schedule_refresh()

    def _cancel_inactive_refresh(self) -> None:
        """Drop queued hidden-view work and hide projection widgets."""
        try:
            self._refresh_timer.stop()
        except RuntimeError:
            pass
        self._hide_unused(0)
