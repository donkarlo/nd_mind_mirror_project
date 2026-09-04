from __future__ import annotations

import bisect
import re

from nd_mind_mirror.core.settings.visual.visual_window_settings import (
    VisualWindowSettings,
)


class VisualSourceWindow:
    """Bound one Visual projection while preserving the complete canonical source."""

    _DOCUMENT_BEGIN = re.compile(r"\\begin\s*\{document\}")
    _DOCUMENT_END = re.compile(r"\\end\s*\{document\}")

    def __init__(
        self,
        source: str,
        settings: VisualWindowSettings,
        focus_line: int = 1,
    ) -> None:
        self._source = str(source)
        self._settings = settings
        self._line_starts = self._build_line_starts(self._source)
        self._body_start, self._body_end = self._body_bounds(self._source)
        self._virtualized = (
            len(self._source) >= settings.large_document_threshold_chars
            and self._line_count_between(self._body_start, self._body_end) >= 300
        )
        self._window_start = 0
        self._window_end = len(self._source)
        self._window_start_line = 1
        self._window_end_line = max(len(self._line_starts), 1)
        self._select(max(int(focus_line), 1))

    @property
    def source(self) -> str:
        return self._source

    @property
    def virtualized(self) -> bool:
        return self._virtualized

    @property
    def window_source(self) -> str:
        return self._source[self._window_start:self._window_end]

    @property
    def window_start(self) -> int:
        return self._window_start

    @property
    def window_end(self) -> int:
        return self._window_end

    @property
    def window_start_line(self) -> int:
        return self._window_start_line

    @property
    def window_end_line(self) -> int:
        return self._window_end_line

    @property
    def line_delta(self) -> int:
        return self._window_start_line - 1 if self._virtualized else 0

    @property
    def window_char_count(self) -> int:
        return max(self._window_end - self._window_start, 0)

    def contains_line(self, line_number: int) -> bool:
        line = max(int(line_number), 1)
        return self._window_start_line <= line <= self._window_end_line

    def near_window_edge(self, line_number: int, ratio: float) -> bool:
        if not self._virtualized:
            return False
        line = max(int(line_number), 1)
        span = max(self._window_end_line - self._window_start_line + 1, 1)
        edge = max(int(span * max(0.05, min(float(ratio), 0.35))), 2)
        return (
            line <= self._window_start_line + edge
            or line >= self._window_end_line - edge
        )

    def normalized_window_source(self, serialized_source: str) -> str:
        """Keep boundary newlines that QTextDocument serialization may trim."""
        text = str(serialized_source)
        original = self.window_source
        leading = re.match(r"^(?:\r?\n)+", original)
        trailing = re.search(r"(?:\r?\n)+$", original)
        if leading is not None and not text.startswith(("\n", "\r\n")):
            text = leading.group(0) + text
        if trailing is not None and not text.endswith(("\n", "\r\n")):
            text += trailing.group(0)
        return text

    def splice(self, serialized_source: str) -> str:
        replacement = self.normalized_window_source(serialized_source)
        return (
            self._source[:self._window_start]
            + replacement
            + self._source[self._window_end:]
        )

    def _select(self, focus_line: int) -> None:
        if not self._virtualized:
            return

        body_start_line = self._line_for_position(self._body_start)
        body_end_line = self._line_for_position(max(self._body_end - 1, self._body_start))
        focus = max(body_start_line, min(int(focus_line), body_end_line))
        body_line_count = max(body_end_line - body_start_line + 1, 1)
        body_chars = max(self._body_end - self._body_start, 1)
        average_chars = max(body_chars / body_line_count, 1.0)
        lines_per_page = int(
            self._settings.estimated_chars_per_page / average_chars
        )
        lines_per_page = max(
            self._settings.min_lines_per_page,
            min(lines_per_page, self._settings.max_lines_per_page),
        )

        start_line = max(
            body_start_line,
            focus - self._settings.pages_above * lines_per_page,
        )
        end_line = min(
            body_end_line,
            focus + self._settings.pages_below * lines_per_page,
        )

        start_line = self._bounded_blank_boundary(
            start_line,
            body_start_line,
            direction=-1,
            max_steps=lines_per_page,
        )
        end_line = self._bounded_blank_boundary(
            end_line,
            body_end_line,
            direction=1,
            max_steps=lines_per_page,
        )

        start = max(self._position_for_line(start_line), self._body_start)
        end = min(self._position_after_line(end_line), self._body_end)
        start, end = self._enforce_hard_cap(start, end, focus)

        self._window_start = start
        self._window_end = max(end, start)
        self._window_start_line = self._line_for_position(start)
        self._window_end_line = self._line_for_position(max(end - 1, start))

    def _enforce_hard_cap(
        self,
        start: int,
        end: int,
        focus_line: int,
    ) -> tuple[int, int]:
        hard_cap = self._settings.hard_window_chars
        if end - start <= hard_cap:
            return start, end

        focus_start = self._position_for_line(focus_line)
        focus_end = self._position_after_line(focus_line)
        half = max(hard_cap // 2, 1)
        desired_start = max(self._body_start, focus_start - half)
        desired_end = min(self._body_end, focus_end + half)

        start_line = self._line_for_position(desired_start)
        end_line = self._line_for_position(max(desired_end - 1, desired_start))
        bounded_start = max(self._position_for_line(start_line), self._body_start)
        bounded_end = min(self._position_after_line(end_line), self._body_end)

        while bounded_end - bounded_start > hard_cap:
            left_distance = focus_start - bounded_start
            right_distance = bounded_end - focus_end
            if right_distance >= left_distance and end_line > focus_line:
                end_line -= 1
                bounded_end = min(
                    self._position_after_line(end_line),
                    self._body_end,
                )
            elif start_line < focus_line:
                start_line += 1
                bounded_start = max(
                    self._position_for_line(start_line),
                    self._body_start,
                )
            else:
                break
        return bounded_start, bounded_end

    def _bounded_blank_boundary(
        self,
        line_number: int,
        limit_line: int,
        *,
        direction: int,
        max_steps: int,
    ) -> int:
        line = int(line_number)
        for _ in range(max(int(max_steps), 0)):
            if line == limit_line:
                break
            text = self._text_for_line(line)
            if not text.strip():
                break
            candidate = line + (-1 if direction < 0 else 1)
            if direction < 0 and candidate < limit_line:
                break
            if direction > 0 and candidate > limit_line:
                break
            line = candidate
        return line

    @staticmethod
    def _build_line_starts(source: str) -> list[int]:
        starts = [0]
        for match in re.finditer("\n", source):
            starts.append(match.end())
        return starts

    @classmethod
    def _body_bounds(cls, source: str) -> tuple[int, int]:
        begin = cls._DOCUMENT_BEGIN.search(source)
        if begin is None:
            return 0, len(source)
        end_matches = list(cls._DOCUMENT_END.finditer(source, begin.end()))
        end = end_matches[-1].start() if end_matches else len(source)
        return begin.end(), max(end, begin.end())

    def _line_count_between(self, start: int, end: int) -> int:
        if end <= start:
            return 0
        return self._line_for_position(end - 1) - self._line_for_position(start) + 1

    def _line_for_position(self, position: int) -> int:
        pos = max(0, min(int(position), len(self._source)))
        return max(bisect.bisect_right(self._line_starts, pos), 1)

    def _position_for_line(self, line_number: int) -> int:
        index = max(min(int(line_number) - 1, len(self._line_starts) - 1), 0)
        return self._line_starts[index]

    def _position_after_line(self, line_number: int) -> int:
        index = max(int(line_number), 1)
        if index < len(self._line_starts):
            return self._line_starts[index]
        return len(self._source)

    def _text_for_line(self, line_number: int) -> str:
        start = self._position_for_line(line_number)
        end = self._position_after_line(line_number)
        return self._source[start:end]
