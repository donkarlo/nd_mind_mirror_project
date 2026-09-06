from pathlib import Path


def _project_file(relative: str) -> Path:
    return Path(__file__).resolve().parent.parent / relative


def test_source_ctrl_shift_d_deletes_current_line() -> None:
    source_editor = _project_file(
        "src/nd_mind_mirror/ui/editor/base/text_editor.py"
    ).read_text(encoding="utf-8")

    assert "event.key() == Qt.Key.Key_D" in source_editor
    assert "Qt.KeyboardModifier.ControlModifier" in source_editor
    assert "Qt.KeyboardModifier.ShiftModifier" in source_editor
    assert "self._delete_current_line()" in source_editor
    assert "def _delete_current_line" in source_editor
    assert "edit.beginEditBlock()" in source_editor


def test_visual_ctrl_shift_d_deletes_current_visual_line() -> None:
    visual_editor = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor.py"
    ).read_text(encoding="utf-8")
    visual_core = _project_file(
        "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor_core.py"
    )

    assert visual_core.is_file()
    assert "event.key() == Qt.Key.Key_D" in visual_editor
    assert "Qt.KeyboardModifier.ControlModifier" in visual_editor
    assert "Qt.KeyboardModifier.ShiftModifier" in visual_editor
    assert "self._delete_current_visual_line()" in visual_editor
    assert "def _delete_current_visual_line" in visual_editor
    assert "self._copy_block_meta(next_block.userData())" in visual_editor
