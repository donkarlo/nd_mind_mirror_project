from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PANEL = PROJECT_ROOT / "src/nd_mind_mirror/ui/panel/preview/preview_panel.py"
ERROR_PANEL = PROJECT_ROOT / "src/nd_mind_mirror/ui/preview/latex/error/latex_error_panel.py"
NAV_REFRESH = PROJECT_ROOT / "src/nd_mind_mirror/ui/window/main/navigator_filesystem_model_refresh_controller.py"
PERSISTENT_VISUALS = PROJECT_ROOT / "src/nd_mind_mirror/ui/window/main/persistent_editor_visuals.py"


def test_preview_splitter_has_visible_resize_handle() -> None:
    source = PREVIEW_PANEL.read_text(encoding="utf-8")
    assert "setHandleWidth(12)" in source
    assert "QSplitter::handle:vertical" in source
    assert "SizeVerCursor" in source


def test_error_panel_exposes_text_and_yaml_copy() -> None:
    source = ERROR_PANEL.read_text(encoding="utf-8")
    assert "Copy as text" in source
    assert "Copy as YAML" in source
    assert "QApplication.clipboard().setText(text)" in source


def test_navigator_rename_rebinds_qfilesystemmodel_root() -> None:
    source = NAV_REFRESH.read_text(encoding="utf-8")
    assert 'model.setRootPath("")' in source
    assert "model.setRootPath(root_path)" in source
    assert "path_renamed.connect" in source
    assert "restore_state(expanded_paths" in source


def test_context_bookmark_routes_through_captured_selection_controller() -> None:
    source = PERSISTENT_VISUALS.read_text(encoding="utf-8")
    assert "SelectionBookmarkContextController(editor)" in source
    assert "item.toggle_captured_selection" in source
    assert 'menu.addAction("Bookmark Selection")' in source
