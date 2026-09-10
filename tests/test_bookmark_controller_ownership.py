from pathlib import Path


def test_special_toolbar_does_not_own_bookmark_selection_menu_controller() -> None:
    project_root = Path(__file__).resolve().parents[1]
    toolbar = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "window"
        / "main"
        / "special_latex_toolbar.py"
    ).read_text(encoding="utf-8")
    window = (
        project_root
        / "src"
        / "nd_mind_mirror"
        / "ui"
        / "window"
        / "main"
        / "enhanced_main_window.py"
    ).read_text(encoding="utf-8")

    assert "BookmarkSelectionMenuController(" not in toolbar
    assert "BookmarkSelectionMenuController(" in window
    assert "self._toggle_bookmark_action" in window
