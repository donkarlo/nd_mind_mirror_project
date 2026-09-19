"""Regression checks for Source/Visual click-driven Navigator selection."""

from pathlib import Path


ROOT = Path(__file__).parent.parent
STRICT_CONTROLLER_PATH = (
    ROOT
    / "src/nd_mind_mirror/ui/window/main/navigator_strict_active_selection_controller.py"
)
STRICT_CONTROLLER = STRICT_CONTROLLER_PATH.read_text(encoding="utf-8")


def test_every_source_visual_click_uses_event_driven_centered_reveal() -> None:
    """Clicks must reveal even when QFileSystemModel has not loaded ancestors yet."""
    assert "QEvent.Type.MouseButtonPress" in STRICT_CONTROLLER
    assert "watched in {self._source_viewport, self._visual_viewport}" in STRICT_CONTROLLER
    assert "NavigatorPathRevealController(" in STRICT_CONTROLLER
    assert "self._path_reveal_controller.reveal(path)" in STRICT_CONTROLLER
    assert "_center_index_horizontally(index)" in STRICT_CONTROLLER


def test_source_graphic_click_resolves_actual_reference_target() -> None:
    """Source includegraphics/includepdf clicks must select the resource file."""
    assert '_GRAPHIC_COMMANDS = {"includegraphics", "includepdf"}' in STRICT_CONTROLLER
    assert "WorkspaceReferenceResolver(" in STRICT_CONTROLLER
    assert "occurrence.command_start <= position <= occurrence.command_end" in STRICT_CONTROLLER
    assert "return occurrence.target_path" in STRICT_CONTROLLER


def test_visual_graphic_click_prefers_image_resource_then_block_reference() -> None:
    """Visual image clicks must select the image instead of the surrounding .tex file."""
    assert 'prefix = "ndgraphic:"' in STRICT_CONTROLLER
    assert 'getattr(metadata, "kind", "") != "graphic"' in STRICT_CONTROLLER
    assert 'getattr(metadata, "display", "")' in STRICT_CONTROLLER
    assert 'command="includegraphics"' in STRICT_CONTROLLER


def test_non_graphic_click_falls_back_to_current_editor_file() -> None:
    """Ordinary Source/Visual clicks continue selecting the active source file."""
    assert "return Path(current_path).expanduser().resolve(strict=False)" in STRICT_CONTROLLER
