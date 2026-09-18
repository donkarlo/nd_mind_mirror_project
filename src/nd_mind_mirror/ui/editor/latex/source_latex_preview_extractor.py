"""Extract renderable mathematics and tables from canonical LaTeX source."""

from __future__ import annotations

import re

from .source_latex_preview_span import SourceLatexPreviewSpan


class SourceLatexPreviewExtractor:
    """Locate formula/table spans without changing source character offsets."""

    _DISPLAY = re.compile(
        r"(?P<bracket>\\\[.*?\\\])"
        r"|(?P<dollars>\$\$.*?\$\$)"
        r"|(?P<environment>"
        r"\\begin\{(?P<name>equation\*?|align\*?|gather\*?|multline\*?)\}"
        r".*?"
        r"\\end\{(?P=name)\}"
        r")",
        re.DOTALL,
    )
    _TABLE = re.compile(
        r"\\begin\{tabular\}(?:\[[^\]]*\])?\s*\{.*?\}.*?\\end\{tabular\}",
        re.DOTALL,
    )

    def extract(self, source: str) -> list[SourceLatexPreviewSpan]:
        """Extract supported math and table spans while preserving canonical offsets."""
        original = str(source)
        masked = self._mask_comments(original)
        spans: list[SourceLatexPreviewSpan] = []

        for match in self._TABLE.finditer(masked):
            spans.append(self._span("table", match, original, display=True))
        for match in self._DISPLAY.finditer(masked):
            if not self._overlaps(match.start(), match.end(), spans):
                spans.append(self._span("math", match, original, display=True))

        occupied = sorted((item.start, item.end) for item in spans)
        spans.extend(self._inline_math(masked, original, occupied))
        return sorted(spans, key=lambda item: (item.start, item.end))

    def _inline_math(
        self,
        masked: str,
        original: str,
        occupied: list[tuple[int, int]],
    ) -> list[SourceLatexPreviewSpan]:
        """Extract inline math outside already occupied display/table ranges."""
        result: list[SourceLatexPreviewSpan] = []
        index = 0
        while index < len(masked):
            containing = self._containing_range(index, occupied)
            if containing is not None:
                index = containing[1]
                continue

            if masked.startswith(r"\(", index):
                end = self._find_unescaped(masked, r"\)", index + 2)
                if end >= 0 and not self._overlaps_range(index, end + 2, occupied):
                    result.append(
                        SourceLatexPreviewSpan(
                            kind="math",
                            start=index,
                            end=end + 2,
                            raw=original[index : end + 2],
                            display=False,
                        )
                    )
                    index = end + 2
                    continue

            if masked[index] == "$" and not self._escaped(masked, index):
                if masked.startswith("$$", index):
                    index += 2
                    continue
                end = self._inline_dollar_end(masked, index + 1)
                if end >= 0 and not self._overlaps_range(index, end + 1, occupied):
                    result.append(
                        SourceLatexPreviewSpan(
                            kind="math",
                            start=index,
                            end=end + 1,
                            raw=original[index : end + 1],
                            display=False,
                        )
                    )
                    index = end + 1
                    continue
            index += 1
        return result

    @staticmethod
    def _span(kind: str, match, source: str, *, display: bool) -> SourceLatexPreviewSpan:
        """Build one preview span from a regex match."""
        return SourceLatexPreviewSpan(
            kind=kind,
            start=match.start(),
            end=match.end(),
            raw=source[match.start() : match.end()],
            display=display,
        )

    @staticmethod
    def _overlaps(start: int, end: int, spans: list[SourceLatexPreviewSpan]) -> bool:
        """Return whether a candidate range overlaps an existing preview span."""
        return any(start < item.end and end > item.start for item in spans)

    @staticmethod
    def _overlaps_range(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
        """Return whether a candidate range overlaps any occupied range."""
        return any(start < right and end > left for left, right in ranges)

    @staticmethod
    def _containing_range(index: int, ranges: list[tuple[int, int]]) -> tuple[int, int] | None:
        """Return the occupied range containing an index, if any."""
        for left, right in ranges:
            if left <= index < right:
                return left, right
            if left > index:
                break
        return None

    @classmethod
    def _inline_dollar_end(cls, text: str, start: int) -> int:
        """Find the closing unescaped dollar for inline math on the same line."""
        index = start
        while index < len(text):
            if text[index] == "\n":
                return -1
            if text[index] == "$" and not cls._escaped(text, index):
                if index + 1 >= len(text) or text[index + 1] != "$":
                    return index
            index += 1
        return -1

    @classmethod
    def _find_unescaped(cls, text: str, token: str, start: int) -> int:
        """Find the next unescaped token starting at the requested offset."""
        index = text.find(token, start)
        while index >= 0:
            if not cls._escaped(text, index):
                return index
            index = text.find(token, index + len(token))
        return -1

    @staticmethod
    def _escaped(text: str, index: int) -> bool:
        """Return whether the character at an index is backslash-escaped."""
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        return bool(backslashes % 2)

    @classmethod
    def _mask_comments(cls, source: str) -> str:
        """Replace comment text with spaces so every source offset stays unchanged."""
        characters = list(source)
        line_start = 0
        while line_start < len(source):
            line_end = source.find("\n", line_start)
            if line_end < 0:
                line_end = len(source)
            for index in range(line_start, line_end):
                if source[index] == "%" and not cls._escaped(source, index):
                    for masked_index in range(index, line_end):
                        characters[masked_index] = " "
                    break
            line_start = line_end + 1
        return "".join(characters)
