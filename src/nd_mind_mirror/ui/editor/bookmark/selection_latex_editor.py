"""Compatibility name for the canonical selection-only LaTeX editor."""

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor


class SelectionLatexEditor(LatexEditor):
    """Retain the historical class name without installing a second bookmark mixin."""

    pass
