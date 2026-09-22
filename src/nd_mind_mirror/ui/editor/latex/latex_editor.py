"""Public LaTeX editor with exact-selection bookmarks and multi-image drop support."""

from nd_mind_mirror.ui.editor.bookmark.range.selection_range_bookmark_editor_mixin import (
    SelectionRangeBookmarkEditorMixin,
)
from nd_mind_mirror.ui.editor.latex.multi_image_drop_latex_editor import (
    MultiImageDropLatexEditor,
)


class LatexEditor(
    SelectionRangeBookmarkEditorMixin,
    MultiImageDropLatexEditor,
):
    """Canonical LaTeX editor where a bookmark is exactly the selected character range."""

    # Large-editor subclasses may call toPlainText() through cooperative mixin
    # initialization before their own __init__ body runs.
    _force_visible_plain_text = False

    pass


__all__ = ["LatexEditor"]
