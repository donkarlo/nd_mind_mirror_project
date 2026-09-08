"""Regression checks for Preview handle visibility and ordered large-file typing."""

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREVIEW_PANEL = (
    PROJECT_ROOT / "src/nd_mind_mirror/ui/panel/preview/preview_panel.py"
)
LARGE_EDITOR = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
)
TYPING_CONTROLLER = (
    PROJECT_ROOT
    / "src/nd_mind_mirror/ui/editor/latex/large/source_typing_burst_controller.py"
)


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1:node.end_lineno])
    raise AssertionError(f"{name} not found in {path}")


def test_preview_splitter_has_dark_idle_handle() -> None:
    source = PREVIEW_PANEL.read_text(encoding="utf-8")
    assert "background: #5f6368;" in source
    assert "QSplitter::handle:vertical:hover" in source
    assert "QSplitter::handle:vertical:pressed" in source


def test_character_edits_mark_typing_burst() -> None:
    source = _function_source(LARGE_EDITOR, "_synchronize_visible_change")
    assert "super()._synchronize_visible_change" in source
    assert "_typing_burst_controller.note_activity()" in source


def test_rewindow_is_blocked_during_typing_and_resumed_after_idle() -> None:
    maybe_shift = _function_source(LARGE_EDITOR, "_maybe_shift_source_window")
    apply_shift = _function_source(LARGE_EDITOR, "_apply_pending_source_window_shift")
    resume = _function_source(LARGE_EDITOR, "_resume_deferred_source_window_shift")
    controller = TYPING_CONTROLLER.read_text(encoding="utf-8")

    assert "_typing_burst_controller.is_active" in maybe_shift
    assert "_typing_burst_controller.is_active" in apply_shift
    assert "became_idle = Signal()" in controller
    assert "super()._apply_pending_source_window_shift()" in resume
