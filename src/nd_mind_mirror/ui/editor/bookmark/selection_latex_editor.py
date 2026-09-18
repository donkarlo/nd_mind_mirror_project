"""Regular LaTeX editor using the unified canonical range-bookmark model."""

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.tikz_targeted_visual_refresh_mixin import (
    TikZTargetedVisualRefreshMixin,
)
from nd_mind_mirror.ui.editor.bookmark.range.range_bookmark_editor_mixin import (
    RangeBookmarkEditorMixin,
)


class SelectionLatexEditor(
    RangeBookmarkEditorMixin,
    TikZTargetedVisualRefreshMixin,
    LatexEditor,
):
    """Regular Source/Visual editor with canonical character-range bookmarks."""

    pass
