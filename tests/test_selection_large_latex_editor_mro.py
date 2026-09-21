"""Regression check for the large LaTeX editor class hierarchy."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTION_LARGE = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/bookmark/selection_large_latex_editor.py"
).read_text(encoding="utf-8")
LARGE = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor_incremental_core.py"
).read_text(encoding="utf-8")
PUBLIC = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
).read_text(encoding="utf-8")


def test_large_editor_does_not_repeat_selection_bookmark_mixin_in_mro() -> None:
    assert "class LargeLatexEditor(LatexEditor)" in LARGE
    assert "SelectionRangeBookmarkEditorMixin" in PUBLIC
    assert "SelectionRangeBookmarkEditorMixin" not in SELECTION_LARGE
    assert "LatexTabViewStateMixin" in SELECTION_LARGE
    assert "TikZTargetedVisualRefreshMixin" in SELECTION_LARGE
    assert "LargeLatexEditor," in SELECTION_LARGE
