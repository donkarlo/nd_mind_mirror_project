"""Regression checks for startup-safe Navigator image editing and multi-path menu ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIX11 = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/fix11_desktop_controller.py"
).read_text(encoding="utf-8")
MULTI = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")
WORKSPACE = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace_interaction_controller.py"
).read_text(encoding="utf-8")


def test_fix11_no_longer_depends_on_removed_workspace_menu_method() -> None:
    assert "WorkspaceInteractionController._show_navigator_menu" not in FIX11
    assert "WorkspaceInteractionController" not in FIX11
    assert "_install_navigator_behavior()" in FIX11
    assert "WorkspaceInteractionController" not in FIX11


def test_multi_path_controller_is_the_image_context_menu_owner() -> None:
    assert 'copy_item = menu.addAction("Copy")' in MULTI
    assert 'cut_item = menu.addAction("Cut")' in MULTI
    assert 'paste_item = menu.addAction("Paste")' in MULTI
    assert 'edit_ipad = open_menu.addAction("Edit image in iPad…")' in MULTI
    assert 'path.suffix.lower() in cls._IMAGE_SUFFIXES' in MULTI


def test_workspace_interaction_delegates_to_canonical_context_controller() -> None:
    assert "self._context_controller.show_menu" in WORKSPACE
    assert "def _show_navigator_menu" not in WORKSPACE
