"""Regular LaTeX editor with selection-aware bookmarks."""

from nd_mind_mirror.ui.editor.latex.latex_editor import LatexEditor
from nd_mind_mirror.ui.editor.bookmark.selection_bookmark_editor_mixin import (
    SelectionBookmarkEditorMixin,
)


class SelectionLatexEditor(SelectionBookmarkEditorMixin, LatexEditor):
    """Use the regular Source implementation with persistent range bookmarks."""

    pass
