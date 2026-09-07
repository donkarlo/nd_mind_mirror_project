"""Regression checks for Navigator filesystem refresh and menu ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROXY = (
    ROOT
    / "src/nd_mind_mirror/ui/model/file_system/ignored_file_system_proxy_model.py"
).read_text(encoding="utf-8")
INTERACTION = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace_interaction_controller.py"
).read_text(encoding="utf-8")
FILESYSTEM = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/workspace/filesystem_operation_controller.py"
).read_text(encoding="utf-8")
CONTEXT = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_multi_path_context_controller.py"
).read_text(encoding="utf-8")


def test_explicit_filesystem_mutations_rebuild_proxy_mappings() -> None:
    assert "def refresh_after_filesystem_change" in PROXY
    assert "super().invalidateFilter()" in PROXY
    assert "self.invalidate()" in PROXY
    assert "def invalidateFilter" in PROXY
    assert "self.refresh_after_filesystem_change()" in PROXY


def test_completed_move_and_delete_already_request_navigator_refresh() -> None:
    assert "def _complete_move" in FILESYSTEM
    assert "def _complete_delete" in FILESYSTEM
    assert FILESYSTEM.count("self._panel._proxy_model.invalidateFilter()") >= 2


def test_workspace_interaction_does_not_reown_context_menu() -> None:
    assert "_install_context_menu" not in INTERACTION
    assert "customContextMenuRequested.disconnect" not in INTERACTION
    assert "customContextMenuRequested.connect" not in INTERACTION


def test_multi_path_context_menu_exposes_copy_from_default_path() -> None:
    assert 'copy_menu.addAction(' in CONTEXT
    assert '"Copy from Default Path"' in CONTEXT
    assert "_copy_selected_default_rooted_paths" in CONTEXT
    assert 'f"/{relative_text}"' in CONTEXT
