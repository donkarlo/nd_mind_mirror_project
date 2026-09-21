"""Large LaTeX editor using the canonical selection-bookmark editor hierarchy."""

from nd_mind_mirror.ui.editor.latex.large.large_latex_editor import LargeLatexEditor
from nd_mind_mirror.ui.editor.latex.latex_tab_view_state_mixin import (
    LatexTabViewStateMixin,
)
from nd_mind_mirror.ui.editor.latex.tikz_targeted_visual_refresh_mixin import (
    TikZTargetedVisualRefreshMixin,
)


class SelectionLargeLatexEditor(
    LatexTabViewStateMixin,
    TikZTargetedVisualRefreshMixin,
    LargeLatexEditor,
):
    """Large Source/Visual editor with selection-only bookmarks and tab state."""

    pass
