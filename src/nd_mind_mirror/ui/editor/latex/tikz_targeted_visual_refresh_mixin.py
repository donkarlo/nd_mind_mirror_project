"""Targeted Visual TikZ refresh behavior shared by regular and large editors."""

from __future__ import annotations

from pathlib import Path


class TikZTargetedVisualRefreshMixin:
    """Refresh one Visual TikZ dependency without rebuilding unrelated graphics."""

    def refresh_visual_tikz_path(self, path: str | Path) -> bool:
        self._visual_dirty = True
        if self._edit_mode != "visual":
            return False
        refresh = getattr(self._visual_editor, "refresh_tikz_path", None)
        if not callable(refresh):
            return False
        return bool(refresh(path))
