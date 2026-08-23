"""Bound Visual virtualization to five pages around the active source location."""

from __future__ import annotations

from nd_mind_mirror.ui.window.main.visual_window_controller import (
    VisualWindowController as _BaseVisualWindowController,
)


class VisualWindowController(_BaseVisualWindowController):
    """Keep a small five-page buffer above and below the active Visual location."""

    _PAGES_ABOVE = 5
    _PAGES_BELOW = 5
    _MIN_VIRTUAL_SOURCE_CHARS = 24_000
    _MIN_VIRTUAL_BODY_LINES = 220

    @classmethod
    def _should_virtualize(cls, source: str, body_lines: list[str]) -> bool:
        """Virtualize whenever the document exceeds the eleven-page active window."""
        del source
        line_count = len(body_lines)
        if line_count <= 1:
            return False
        average_chars = max(
            sum(len(line) for line in body_lines) / max(line_count, 1),
            1.0,
        )
        lines_per_page = int(cls._ESTIMATED_CHARS_PER_PAGE / average_chars)
        lines_per_page = max(
            cls._MIN_LINES_PER_PAGE,
            min(lines_per_page, cls._MAX_LINES_PER_PAGE),
        )
        active_window_lines = (cls._PAGES_ABOVE + cls._PAGES_BELOW + 1) * lines_per_page
        return line_count > active_window_lines

    @classmethod
    def _compute_window_bounds(
        cls,
        body_lines: list[str],
        focus_index: int,
    ) -> tuple[int, int]:
        """Return a bounded cursor-centered window without splitting nearby environments."""
        line_count = len(body_lines)
        if line_count == 0:
            return 0, 0
        focus = max(0, min(int(focus_index), line_count - 1))
        average_chars = max(
            sum(len(line) for line in body_lines) / max(line_count, 1),
            1.0,
        )
        lines_per_page = int(cls._ESTIMATED_CHARS_PER_PAGE / average_chars)
        lines_per_page = max(
            cls._MIN_LINES_PER_PAGE,
            min(lines_per_page, cls._MAX_LINES_PER_PAGE),
        )
        start = max(0, focus - cls._PAGES_ABOVE * lines_per_page)
        end = min(
            line_count,
            focus + cls._PAGES_BELOW * lines_per_page + 1,
        )

        boundary_extension = max(lines_per_page, cls._MIN_LINES_PER_PAGE)
        start, end = cls._expand_plain_paragraph_bounds(
            body_lines,
            start,
            end,
            max_extension=boundary_extension,
        )
        start, end = cls._expand_environment_bounds(
            body_lines,
            start,
            end,
        )
        start, end = cls._expand_plain_paragraph_bounds(
            body_lines,
            start,
            end,
            max_extension=boundary_extension,
        )

        while start < focus and not body_lines[start].strip():
            start += 1
        while end > focus + 1 and not body_lines[end - 1].strip():
            end -= 1
        return max(start, 0), min(max(end, start + 1), line_count)

    @classmethod
    def _expand_plain_paragraph_bounds(
        cls,
        lines: list[str],
        start: int,
        end: int,
        *,
        max_extension: int,
    ) -> tuple[int, int]:
        """Prefer prose boundaries but cap expansion so virtualization stays bounded."""
        original_start = int(start)
        original_end = int(end)
        extension = max(int(max_extension), 0)

        while (
            start > 0
            and original_start - start < extension
            and start < len(lines)
            and cls._is_plain_prose_line(lines[start])
            and cls._is_plain_prose_line(lines[start - 1])
        ):
            start -= 1

        while (
            end > 0
            and end < len(lines)
            and end - original_end < extension
            and cls._is_plain_prose_line(lines[end - 1])
            and cls._is_plain_prose_line(lines[end])
        ):
            end += 1

        return start, end
