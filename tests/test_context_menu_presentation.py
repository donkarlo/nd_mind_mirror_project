from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/nd_mind_mirror"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_context_menu_presenter_maps_common_actions_to_semantic_icons() -> None:
    source = _read("ui/menu/context_menu_presenter.py")
    for icon_name in (
        "edit-copy",
        "edit-cut",
        "edit-paste",
        "edit-delete",
        "edit-rename",
        "folder-new",
        "document-open",
        "bookmark-new",
        "image-x-generic",
    ):
        assert icon_name in source
    assert "action.setIconVisibleInMenu(True)" in source
    assert "cls.decorate(submenu)" in source


def test_primary_right_click_menus_use_shared_presenter() -> None:
    files = (
        "ui/window/main/navigator_multi_path_context_controller.py",
        "ui/window/main/navigator_context_controller.py",
        "ui/panel/file_system/file_system_panel.py",
        "ui/editor/latex/core/latex_editor_core.py",
        "ui/editor/latex/latex_visual_editor.py",
        "ui/editor/latex/visual/windowed_latex_visual_editor_with_resources.py",
        "ui/editor/latex/source_graphic_preview_controller.py",
        "ui/editor/bookmark/bookmark_gutter.py",
        "ui/window/main/pinned_tab_controller.py",
    )
    for relative in files:
        source = _read(relative)
        assert "ContextMenuPresenter" in source
        assert "ContextMenuPresenter.decorate(menu)" in source


def test_navigator_child_indentation_is_slightly_wider() -> None:
    panel = _read("ui/panel/file_system/file_system_panel.py")
    assert "self._tree.setIndentation(14)" in panel
    assert "self._tree.setIndentation(10)" not in panel
