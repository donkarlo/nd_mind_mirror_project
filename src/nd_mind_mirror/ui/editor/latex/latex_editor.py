"""Public LaTeX editor class with strict mode isolation and multi-image drop support."""

from nd_mind_mirror.ui.editor.latex.multi_image_drop_latex_editor import (
    MultiImageDropLatexEditor,
)


LatexEditor = MultiImageDropLatexEditor

__all__ = ["LatexEditor"]
