from pathlib import Path

from nd_mind_mirror.ui.editor.latex.visual_source_window import VisualSourceWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _large_document(line_count: int = 70000) -> tuple[str, str, str, str]:
    prefix = "\\documentclass{article}\n\\begin{document}\n"
    body = "".join(
        f"Persian story prose line {index:05d} with enough text for windowing.\n"
        for index in range(line_count)
    )
    suffix = "\\end{document}\n"
    return prefix + body + suffix, prefix, body, suffix


def test_large_visual_projection_is_bounded_and_full_source_is_preserved():
    full_source, prefix, body, suffix = _large_document()
    window = VisualSourceWindow()
    window.configure(
        threshold_chars=120000,
        pages_above=2,
        pages_below=2,
        estimated_chars_per_page=2400,
        min_lines_per_page=12,
        max_lines_per_page=45,
        max_window_chars=40000,
    )

    projected = window.select(
        full_source=full_source,
        prefix=prefix,
        body=body,
        suffix=suffix,
        focus_line=35000,
    )

    assert len(full_source) > 3_000_000
    assert window.virtualized is True
    assert len(projected) <= 40000
    assert window.splice(projected) == full_source


def test_distant_structure_navigation_selects_a_different_visual_window():
    full_source, prefix, body, suffix = _large_document()
    window = VisualSourceWindow()
    window.configure(
        threshold_chars=120000,
        pages_above=2,
        pages_below=2,
        estimated_chars_per_page=2400,
        min_lines_per_page=12,
        max_lines_per_page=45,
        max_window_chars=40000,
    )
    first = window.select(
        full_source=full_source,
        prefix=prefix,
        body=body,
        suffix=suffix,
        focus_line=1000,
    )
    first_bounds = (window.window_start_line, window.window_end_line)
    second = window.select(
        full_source=full_source,
        prefix=prefix,
        body=body,
        suffix=suffix,
        focus_line=60000,
    )
    second_bounds = (window.window_start_line, window.window_end_line)

    assert first_bounds != second_bounds
    assert first != second
    assert window.contains_line(60000)


def test_active_visual_architecture_has_no_runtime_method_patch():
    enhanced = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/window/main/enhanced_main_window.py"
    ).read_text(encoding="utf-8")
    windowed = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/editor/latex/windowed_latex_visual_editor.py"
    ).read_text(encoding="utf-8")
    editor = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/editor/latex/latex_editor.py"
    ).read_text(encoding="utf-8")

    assert "VisualWindowController" not in enhanced
    assert "MethodType" not in enhanced
    assert "MethodType" not in windowed
    assert "WindowedLatexVisualEditor" in editor


def test_structure_keeps_parsing_the_complete_canonical_source():
    panel = (
        PROJECT_ROOT
        / "src/nd_mind_mirror/ui/panel/structure/latex_structure_panel.py"
    ).read_text(encoding="utf-8")

    assert "self._source = source" in panel
    assert "self._latex_parser.parse(self._source)" in panel
    assert "VisualSourceWindow" not in panel
    assert "window_start" not in panel
