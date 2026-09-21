"""Regression checks for transient tab hover and exact public LaTeX bookmarks."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOVER = (
    ROOT / "src/nd_mind_mirror/ui/switcher/hover_proxy_tab_bar.py"
).read_text(encoding="utf-8")
STABLE = (
    ROOT / "src/nd_mind_mirror/ui/window/main/stable_pinned_tab_controller.py"
).read_text(encoding="utf-8")
LATEX = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
).read_text(encoding="utf-8")


def test_proxy_tab_hover_is_transient_and_light_purple() -> None:
    assert 'QColor("#eadfff")' in HOVER
    assert "def leaveEvent" in HOVER
    assert "self._hovered_index = -1" in HOVER
    assert "State_MouseOver" in HOVER
    assert "HoverProxyTabBar(container)" in STABLE


def test_public_latex_editor_owns_selection_only_bookmarks() -> None:
    assert "SelectionRangeBookmarkEditorMixin" in LATEX
    assert "MultiImageDropLatexEditor" in LATEX
    assert "class LatexEditor(" in LATEX
