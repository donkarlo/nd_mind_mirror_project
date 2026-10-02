from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_source_and_visual_share_scroll_past_end_controller() -> None:
    source_editor = _read(
        "src/nd_mind_mirror/ui/editor/base/text_editor.py"
    )
    visual_editor = _read(
        "src/nd_mind_mirror/ui/editor/latex/latex_visual_editor.py"
    )

    assert "CaretScrollMarginController" in source_editor
    assert "_caret_scroll_margin = CaretScrollMarginController(self)" in source_editor
    assert "CaretScrollMarginController" in visual_editor
    assert "_caret_scroll_margin = CaretScrollMarginController(self)" in visual_editor


def test_scroll_margin_is_visual_only_and_keeps_caret_above_bottom() -> None:
    controller = _read(
        "src/nd_mind_mirror/ui/editor/cursor/"
        "caret_scroll_margin_controller.py"
    )

    assert "_BOTTOM_SPACE_RATIO = 0.35" in controller
    assert "_CARET_RESERVE_RATIO = 0.22" in controller
    assert "frame_format.setBottomMargin(target_margin)" in controller
    assert "QSignalBlocker(editor)" in controller
    assert "QSignalBlocker(document)" in controller
    assert "document.setModified(was_modified)" in controller
    assert "cursor_rect.bottom() - lower_limit" in controller
    assert "scrollbar.setValue(target)" in controller
    assert "not editor.isVisible() or not editor.hasFocus()" in controller
