"""Regression tests for cursor-centered Visual virtualization bounds."""

from nd_mind_mirror.ui.window.main.persistent_editor_visuals import PersistentEditorVisuals
from nd_mind_mirror.ui.window.main.visual_window_controller import VisualWindowController


def test_large_window_contains_focus_and_is_bounded() -> None:
    """A long prose document should load only a bounded region around the focus."""
    lines = [f"سطر آزمایشی {index}\n" for index in range(6000)]
    focus = 3000

    start, end = VisualWindowController._compute_window_bounds(lines, focus)

    assert start <= focus < end
    assert start > 0
    assert end < len(lines)
    assert end - start < len(lines) // 2


def test_long_persian_paragraph_lines_use_character_budget() -> None:
    """Two Visual pages must not become dozens of screen pages for long Persian lines."""
    previous_pages_above = VisualWindowController._PAGES_ABOVE
    previous_pages_below = VisualWindowController._PAGES_BELOW
    previous_chars_per_page = VisualWindowController._ESTIMATED_CHARS_PER_PAGE
    previous_max_lines = VisualWindowController._MAX_LINES_PER_PAGE
    try:
        VisualWindowController._PAGES_ABOVE = 2
        VisualWindowController._PAGES_BELOW = 2
        VisualWindowController._ESTIMATED_CHARS_PER_PAGE = 2400
        VisualWindowController._MAX_LINES_PER_PAGE = 45
        lines = []
        for index in range(101):
            lines.append(("متن فارسی بلند " + ("ک" * 1700) + f" {index}\n"))
            lines.append("\n")
        focus = 100

        start, end = PersistentEditorVisuals._compute_visual_window_bounds(
            VisualWindowController,
            lines,
            focus,
        )

        assert start <= focus < end
        assert end - start <= 15
        assert sum(len(line) for line in lines[start:end]) < 15000
    finally:
        VisualWindowController._PAGES_ABOVE = previous_pages_above
        VisualWindowController._PAGES_BELOW = previous_pages_below
        VisualWindowController._ESTIMATED_CHARS_PER_PAGE = previous_chars_per_page
        VisualWindowController._MAX_LINES_PER_PAGE = previous_max_lines


def test_window_expands_to_keep_environment_whole() -> None:
    """A virtual boundary must not split a LaTeX environment around its edge."""
    lines = [f"line {index}\n" for index in range(2500)]
    lines[400] = "\\begin{itemize}\n"
    for index in range(401, 1300):
        lines[index] = f"\\item item {index}\n"
    lines[1300] = "\\end{itemize}\n"

    start, end = VisualWindowController._compute_window_bounds(lines, 1000)

    assert start <= 400
    assert end >= 1301


def test_short_source_does_not_virtualize() -> None:
    """Ordinary documents should stay on the existing full Visual rendering path."""
    source = "\n".join(f"line {index}" for index in range(100))
    lines = source.splitlines(keepends=True)

    assert not VisualWindowController._should_virtualize(source, lines)
