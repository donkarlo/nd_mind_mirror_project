from pathlib import Path


def test_obsolete_bookmark_selection_menu_is_not_installed() -> None:
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
    assert "BookmarkSelectionMenuController(" not in window
    assert "self._toggle_bookmark_action" not in window
    main_window = (project_root / "src/nd_mind_mirror/ui/window/main/main_window.py").read_text(encoding="utf-8")
    assert 'addMenu("Bookmarks")' not in main_window
    assert 'Ctrl+Shift+B' not in main_window
    source_context = (project_root / "src/nd_mind_mirror/ui/editor/bookmark/range/range_bookmark_source_context_controller.py").read_text(encoding="utf-8")
    visual_context = (project_root / "src/nd_mind_mirror/ui/editor/bookmark/range/range_bookmark_visual_context_controller.py").read_text(encoding="utf-8")
    assert 'menu.addAction(str(state["label"]))' not in source_context
    assert 'menu.addAction(str(state["label"]))' not in visual_context
