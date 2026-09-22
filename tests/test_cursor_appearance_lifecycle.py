"""Regression checks for cursor-controller editor lifetime ownership."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CURSOR = (
    ROOT / "src/nd_mind_mirror/ui/editor/cursor/cursor_appearance_controller.py"
).read_text(encoding="utf-8")


def test_cursor_controller_stops_using_editor_after_destroyed() -> None:
    assert "editor.destroyed.connect(self._on_editor_destroyed)" in CURSOR
    assert "self._editor = None" in CURSOR
    assert "self._viewport = None" in CURSOR
    assert "if editor is None or viewport is None:" in CURSOR
