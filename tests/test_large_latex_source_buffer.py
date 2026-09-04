from nd_mind_mirror.core.document.latex.large.latex_source_buffer import (
    LatexSourceBuffer,
)


def _source(line_count: int = 12000) -> str:
    return "".join(f"line {index:05d} Persian prose متن\n" for index in range(line_count))


def test_large_source_buffer_keeps_full_source_outside_edit_window():
    source = _source()
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=8000)
    buffer.set_source(source, focus_position=len(source) // 2)

    assert buffer.is_windowed
    assert len(buffer.window_text) < len(source)
    assert buffer.source == source


def test_window_edit_is_spliced_once_without_duplicate_tail():
    source = _source()
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=8000)
    buffer.set_source(source, focus_position=len(source) // 2)

    before = buffer.source[: buffer.window_start]
    old_window = buffer.window_text
    after = buffer.source[buffer.window_end :]
    replacement = old_window.replace("Persian prose", "edited prose", 1)

    buffer.replace_window(replacement)

    assert buffer.source == before + replacement + after
    assert buffer.source.endswith(after)
    assert len(buffer.source) == len(source) + len(replacement) - len(old_window)


def test_line_mapping_remains_global_after_window_edit():
    source = _source()
    buffer = LatexSourceBuffer(threshold_chars=1000, window_chars=8000)
    target_line = 9000
    target_position = buffer.full_position_for_location(target_line, 1)
    buffer.select_around_position(target_position)

    replacement = "new first line\n" + buffer.window_text
    buffer.replace_window(replacement)

    mapped_line, mapped_column = buffer.location_for_full_position(
        buffer.window_start + len("new first line\n")
    )
    original_window_line, _ = buffer.location_for_full_position(buffer.window_start)
    assert mapped_line == original_window_line + 1
    assert mapped_column == 1


def test_editor_panel_uses_large_latex_editor_without_runtime_method_patch():
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    panel = (
        project_root
        / "src/nd_mind_mirror/ui/panel/editor/editor_panel.py"
    ).read_text(encoding="utf-8")
    large_editor = (
        project_root
        / "src/nd_mind_mirror/ui/editor/latex/large/large_latex_editor.py"
    ).read_text(encoding="utf-8")

    assert "LargeLatexEditor(" in panel
    assert "class LargeLatexEditor(LatexEditor)" in large_editor
    assert "MethodType" not in large_editor
    assert ".__class__" not in large_editor
