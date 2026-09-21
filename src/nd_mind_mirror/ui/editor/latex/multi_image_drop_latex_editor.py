"""LaTeX editor that inserts every dragged local image as an original-file reference."""

from __future__ import annotations

from PySide6.QtCore import QMimeData

from nd_mind_mirror.ui.editor.latex.mode.mode_isolated_latex_editor import (
    ModeIsolatedLatexEditor,
)


class MultiImageDropLatexEditor(ModeIsolatedLatexEditor):
    """Handle local-image MIME references before pixel-image/text fallback."""

    def insertFromMimeData(self, source: QMimeData) -> None:
        reference_paths = self._image_saver.latex_reference_paths(
            source,
            self._source_path,
        )
        if not reference_paths:
            super().insertFromMimeData(source)
            return

        source_directory = self._source_path.parent
        for reference_path in reference_paths:
            try:
                relative_path = reference_path.relative_to(source_directory)
            except ValueError:
                relative_path = reference_path
            self._insert_figure(relative_path.as_posix())
