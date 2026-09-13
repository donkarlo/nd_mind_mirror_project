"""Regression checks for Visual existing-image iPad context detection."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = (
    ROOT
    / "src/nd_mind_mirror/ui/editor/latex/visual_graphic_context_controller.py"
).read_text(encoding="utf-8")
VISUAL_EDITOR = (
    ROOT / "src/nd_mind_mirror/ui/editor/latex/latex_visual_editor.py"
).read_text(encoding="utf-8")


def test_visual_graphic_context_normalizes_metadata_to_menu_contract() -> None:
    assert "from nd_mind_mirror.ui.editor.latex.latex_visual_editor import _BlockMeta" in CONTROLLER
    assert "block.setUserData(" in CONTROLLER
    assert "self._graphic_metadata(" in CONTROLLER
    assert 'kind="graphic"' in CONTROLLER
    assert "if block_data is not None and" not in CONTROLLER


def test_visual_graphic_context_preserves_source_location_for_edit_lookup() -> None:
    assert "_source_line_for_graphic(" in CONTROLLER
    assert 'getattr(block_data, "source_line", 0)' in CONTROLLER
    assert 'getattr(watched, "source_location_for_position", None)' in CONTROLLER
    assert "source_line=max(int(source_line), 0)" in CONTROLLER


def test_visual_context_menu_still_uses_existing_graphic_contract() -> None:
    assert "isinstance(click_meta, _BlockMeta)" in VISUAL_EDITOR
    assert 'click_meta.kind == "graphic"' in VISUAL_EDITOR
    assert '"Edit image in iPad…"' in VISUAL_EDITOR
    assert '"Insert image in iPad…"' in VISUAL_EDITOR
