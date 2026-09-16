"""Canonical windowed Visual LaTeX editor."""

from __future__ import annotations

from pathlib import Path

from nd_mind_mirror.ui.editor.latex.visual.windowed_latex_visual_editor_with_resources import (
    WindowedLatexVisualEditor as ResourceWindowedLatexVisualEditor,
)


class WindowedLatexVisualEditor(ResourceWindowedLatexVisualEditor):
    """Preload display mathematics before building the Visual QTextDocument."""

    def load_source(
        self,
        source: str,
        source_path: str | Path | None = None,
    ) -> None:
        self._math_visual_preview_service.preload_display_math(str(source))
        super().load_source(source, source_path)
