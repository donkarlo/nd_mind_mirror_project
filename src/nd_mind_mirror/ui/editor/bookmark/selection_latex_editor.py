"""Regular LaTeX editor with selection-only canonical range bookmarks."""

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.latex.latex_tab_view_state_mixin import (
    LatexTabViewStateMixin,
)
from nd_mind_mirror.ui.editor.latex.tikz_targeted_visual_refresh_mixin import (
    TikZTargetedVisualRefreshMixin,
)
from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_editor_mixin import (
    SelectionRangeBookmarkEditorMixin,
)


class SelectionLatexEditor(
    SelectionRangeBookmarkEditorMixin,
    LatexTabViewStateMixin,
    TikZTargetedVisualRefreshMixin,
    LatexEditor,
):
    """Regular Source/Visual editor where only selected text can be bookmarked."""

    pass
