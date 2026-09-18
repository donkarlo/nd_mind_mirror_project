"""Large LaTeX editor using the exact same range-bookmark model."""

from nd_mind_mirror.ui.editor.latex.large.large_latex_editor import LargeLatexEditor
from nd_mind_mirror.ui.editor.latex.tikz_targeted_visual_refresh_mixin import (
    TikZTargetedVisualRefreshMixin,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_editor_mixin import (
    RangeBookmarkEditorMixin,
)


class SelectionLargeLatexEditor(
    RangeBookmarkEditorMixin,
    TikZTargetedVisualRefreshMixin,
    LargeLatexEditor,
):
    """Virtualized Source/Visual editor sharing the regular bookmark mechanism."""

    pass
