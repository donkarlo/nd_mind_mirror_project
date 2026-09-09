"""Large LaTeX editor with selection-aware bookmarks."""

from nd_mind_mirror.ui.editor.latex.large.large_latex_editor import LargeLatexEditor
from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_editor_mixin import (
    SelectionBookmarkEditorMixin,
)


class SelectionLargeLatexEditor(SelectionBookmarkEditorMixin, LargeLatexEditor):
    """Keep range bookmarks available in the virtualized large Source editor."""

    pass
