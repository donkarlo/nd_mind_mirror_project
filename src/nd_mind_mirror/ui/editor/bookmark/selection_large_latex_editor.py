"""Large LaTeX editor with selection-only canonical range bookmarks."""

from nd_mind_mirror.ui.editor.latex.large.large_latex_editor import LargeLatexEditor
from nd_mind_mirror.ui.editor.latex.latex_tab_view_state_mixin import (
    LatexTabViewStateMixin,
)
from nd_mind_mirror.ui.editor.latex.tikz_targeted_visual_refresh_mixin import (
    TikZTargetedVisualRefreshMixin,
)
from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_editor_mixin import (
    SelectionRangeBookmarkEditorMixin,
)


class SelectionLargeLatexEditor(
    SelectionRangeBookmarkEditorMixin,
    LatexTabViewStateMixin,
    TikZTargetedVisualRefreshMixin,
    LargeLatexEditor,
):
    """Large Source/Visual editor where only selected text can be bookmarked."""

    pass
