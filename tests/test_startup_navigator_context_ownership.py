"""Regression checks for startup-safe Navigator context-menu ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLBAR = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/special_latex_toolbar.py"
).read_text(encoding="utf-8")
MULTI = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")
WORKSPACE = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace_interaction_controller.py"
).read_text(encoding="utf-8")
SEARCH = (
    ROOT
    / "src/nd_mind_mirror/ui/search/thread/file_search_thread.py"
).read_text(encoding="utf-8")


def test_toolbar_does_not_install_runtime_class_patches() -> None:
    assert "Fix11DesktopController" not in TOOLBAR
    assert "Fix11DesktopController.install()" not in TOOLBAR


def test_multi_path_controller_is_the_image_context_menu_owner() -> None:
    assert 'copy_item = menu.addAction("Copy")' in MULTI
    assert 'cut_item = menu.addAction("Cut")' in MULTI
    assert 'paste_item = menu.addAction("Paste")' in MULTI
    assert 'edit_ipad = open_menu.addAction("Edit image in iPad…")' in MULTI
    assert 'path.suffix.lower() in cls._IMAGE_SUFFIXES' in MULTI


def test_workspace_interaction_delegates_to_canonical_context_controller() -> None:
    assert "self._context_controller.show_menu" in WORKSPACE
    assert "def _show_navigator_menu" not in WORKSPACE


def test_explicit_hierarchy_search_is_native_not_runtime_patched() -> None:
    assert 'raw_query.split(">")' in SEARCH
    assert "def _score_explicit_hierarchy" in SEARCH
