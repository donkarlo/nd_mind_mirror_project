from __future__ import annotations


class VisualSourceWindow:
    """Select and splice a bounded source window for the LaTeX Visual editor.

    The complete LaTeX source remains canonical.  This class only chooses the
    small body slice rendered by Visual mode and later splices edits from that
    slice back into the untouched full source.
    """

    def __init__(self) -> None:
        self.configure(
            threshold_chars=120_000,
            pages_above=4,
            pages_below=4,
            estimated_chars_per_page=2_400,
            min_lines_per_page=12,
            max_lines_per_page=45,
            max_window_chars=40_000,
        )
        self.reset()

    def configure(
        self,
        *,
        threshold_chars: int,
        pages_above: int,
        pages_below: int,
        estimated_chars_per_page: int,
        min_lines_per_page: int,
        max_lines_per_page: int,
        max_window_chars: int,
    ) -> None:
        self.threshold_chars = max(int(threshold_chars), 10_000)
        self.pages_above = max(int(pages_above), 0)
        self.pages_below = max(int(pages_below), 0)
        self.estimated_chars_per_page = max(int(estimated_chars_per_page), 200)
        self.min_lines_per_page = max(int(min_lines_per_page), 1)
        self.max_lines_per_page = max(
            int(max_lines_per_page),
            self.min_lines_per_page,
        )
        self.max_window_chars = max(int(max_window_chars), 4_000)

    def reset(self) -> None:
        self.full_source = ""
        self.source_path = None
        self.virtualized = False
        self.body_start_line = 1
        self.body_last_line = 1
        self.window_start_line = 1
        self.window_end_line = 1
        self.before = ""
        self.after = ""
        self.window_source = ""
        self.leading_newlines = ""
        self.trailing_newlines = ""

    def select(
        self,
        *,
        full_source: str,
        prefix: str,
        body: str,
        suffix: str,
        focus_line: int,
        source_path=None,
    ) -> str:
        """Return either the complete source or a bounded Visual body slice."""
        source = str(full_source)
        lines = body.splitlines(keepends=True)
        body_start_line = prefix.count("\n") + 1
        body_last_line = body_start_line + max(len(lines) - 1, 0)

        self.full_source = source
        if source_path is not None:
            self.source_path = source_path
        self.body_start_line = body_start_line
        self.body_last_line = body_last_line

        if len(source) < self.threshold_chars or len(lines) <= 1:
            self.virtualized = False
            self.window_start_line = body_start_line
            self.window_end_line = body_last_line
            self.before = ""
            self.after = ""
            self.window_source = source
            self.leading_newlines = ""
            self.trailing_newlines = ""
            return source

        focus_index = max(
            0,
            min(int(focus_line) - body_start_line, len(lines) - 1),
        )
        start, end = self._window_bounds(lines, focus_index)
        window = "".join(lines[start:end])

        self.virtualized = True
        self.window_start_line = body_start_line + start
        self.window_end_line = body_start_line + max(end - 1, start)
        self.before = prefix + "".join(lines[:start])
        self.after = "".join(lines[end:]) + suffix
        self.window_source = window
        self.leading_newlines = self._leading_newlines(window)
        self.trailing_newlines = self._trailing_newlines(window)
        return window

    def contains_line(self, line_number: int) -> bool:
        if not self.virtualized:
            return True
        line = max(int(line_number), 1)
        return self.window_start_line <= line <= self.window_end_line

    def splice(self, serialized_window: str) -> str:
        """Return complete source after replacing only the loaded Visual slice."""
        if not self.virtualized:
            return str(serialized_window)

        window = str(serialized_window)
        if self.leading_newlines and not window.startswith("\n"):
            window = self.leading_newlines + window
        if self.trailing_newlines and not window.endswith("\n"):
            window += self.trailing_newlines
        return self.before + window + self.after

    def _window_bounds(
        self,
        lines: list[str],
        focus_index: int,
    ) -> tuple[int, int]:
        line_count = len(lines)
        if line_count == 0:
            return 0, 0

        focus = max(0, min(int(focus_index), line_count - 1))
        average_chars = max(
            sum(len(line) for line in lines) / line_count,
            1.0,
        )
        lines_per_page = int(self.estimated_chars_per_page / average_chars)
        lines_per_page = max(
            self.min_lines_per_page,
            min(lines_per_page, self.max_lines_per_page),
        )

        start = max(0, focus - self.pages_above * lines_per_page)
        end = min(
            line_count,
            focus + self.pages_below * lines_per_page + 1,
        )
        start, end = self._trim_to_character_cap(lines, start, end, focus)

        while start < focus and not lines[start].strip():
            start += 1
        while end > focus + 1 and not lines[end - 1].strip():
            end -= 1
        return max(start, 0), min(max(end, start + 1), line_count)

    def _trim_to_character_cap(
        self,
        lines: list[str],
        start: int,
        end: int,
        focus: int,
    ) -> tuple[int, int]:
        """Enforce a hard window cap without expanding prose/environments."""
        total = sum(len(line) for line in lines[start:end])
        while total > self.max_window_chars and end - start > 1:
            left_distance = focus - start
            right_distance = (end - 1) - focus
            if right_distance >= left_distance and end - 1 > focus:
                end -= 1
                total -= len(lines[end])
                continue
            if start < focus:
                total -= len(lines[start])
                start += 1
                continue
            break
        return start, end

    @staticmethod
    def _leading_newlines(text: str) -> str:
        index = 0
        while index < len(text) and text[index] in {"\r", "\n"}:
            index += 1
        return text[:index]

    @staticmethod
    def _trailing_newlines(text: str) -> str:
        index = len(text)
        while index > 0 and text[index - 1] in {"\r", "\n"}:
            index -= 1
        return text[index:]
