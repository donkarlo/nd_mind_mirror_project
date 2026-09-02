"""Regression checks for migration 9 Source layout, line deletion, and iPad undo fixes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_source_graphic_preview_uses_stable_end_figure_reservations() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
    )
    assert "_reserve_preview_lane" not in source
    assert "_apply_end_block_margins" in source
    assert "setTopMargin" in source
    assert "figure_match.start(\"end\")" in source
    assert "refresh_positions" in source


def test_source_graphic_preview_width_can_overflow_for_horizontal_scroll() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/editor/latex/source_graphic_preview_controller.py"
    )
    assert "_MAX_WIDTH_RATIO = 4.0" in source
    assert "_configure_horizontal_scroll" in source
    assert "scrollbar.setRange" in source


def test_ctrl_shift_d_handles_both_source_and_visual_editors() -> None:
    source = _read(
        "src/nd_mind_mirror/ui/window/main/source_edit_command_controller.py"
    )
    assert "isinstance(watched, LatexEditor)" in source
    assert "isinstance(watched, LatexVisualEditor)" in source
    assert "delete_current_source_line" in source
    assert "delete_current_visual_line" in source
    assert "current_source_location" in source


def test_ipad_undo_filters_delayed_programmatic_callbacks_before_local_state() -> None:
    content_view = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Views/ContentView.swift"
    )
    guard_call = content_view.index("programmaticDrawingChanges.matches(drawing)")
    local_assignment = content_view.index("localDrawing = drawing", guard_call)
    assert guard_call < local_assignment
    assert "programmaticDrawingChanges.register(snapshot.drawing)" in content_view
    assert "programmaticDrawingChanges.reset()" in content_view


def test_ipad_programmatic_guard_keeps_multiple_recent_states() -> None:
    source = _read(
        "src/nd_mind_mirror/graphic/ipad/nd_graphic.swiftpm/Services/ProgrammaticDrawingChangeGuard.swift"
    )
    assert "expectedStates" in source
    assert "maximumCount" in source
    assert "expiresAt" in source
    assert "expectedStates.contains" in source
