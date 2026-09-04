from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class LatexStructureItem:
    kind: str
    title: str
    line_number: int
    level: int
    source_position: int


class LatexStructureParser:
    """Extract LaTeX headings and graphics in linear-time source passes.

    Large documents previously recomputed line numbers with ``str.count`` from
    the beginning of the source for every heading/image. That becomes
    quadratic as the file grows. This parser builds one line-start index and
    reuses it for every structural item.
    """

    _HEADING_ORDER = {
        "part": 0,
        "chapter": 1,
        "section": 2,
        "subsection": 3,
        "subsubsection": 4,
        "paragraph": 5,
        "subparagraph": 6,
    }
    _HEADING_PATTERN = re.compile(
        r"\\(?P<kind>part|chapter|section|subsection|subsubsection|"
        r"paragraph|subparagraph)"
        r"(?P<star>\*)?(?![A-Za-z@])"
    )
    _IMAGE_PATTERN = re.compile(
        r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^{}]+)\}"
    )
    _FIGURE_BEGIN_PATTERN = re.compile(r"\\begin\s*\{figure\*?\}")
    _FIGURE_END_PATTERN = re.compile(r"\\end\s*\{figure\*?\}")
    _CAPTION_PATTERN = re.compile(r"\\caption(?:\s*\[[^\]]*\])?\s*")
    _LITERAL_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{(?P<name>verbatim|Verbatim|lstlisting|minted)\}"
    )

    def parse(self, source: str) -> list[LatexStructureItem]:
        value = str(source)
        structural = self._mask_comments_and_literal_environments(value)
        line_starts = self._line_starts(structural)
        result: list[LatexStructureItem] = []

        for match in self._HEADING_PATTERN.finditer(structural):
            cursor = self._skip_space(structural, match.end())
            optional_title = None

            if cursor < len(structural) and structural[cursor] == "[":
                parsed = self._balanced_argument(structural, cursor, "[", "]")
                if parsed is None:
                    continue
                optional_title, cursor = parsed
                cursor = self._skip_space(structural, cursor)

            if cursor >= len(structural) or structural[cursor] != "{":
                continue

            parsed = self._balanced_argument(structural, cursor, "{", "}")
            if parsed is None:
                continue

            required_title, _ = parsed
            raw_title = (
                optional_title
                if optional_title is not None and optional_title.strip()
                else required_title
            )
            display_title = self._display_title(raw_title) or "(untitled)"
            kind = match.group("kind")
            result.append(
                LatexStructureItem(
                    kind=kind,
                    title=display_title,
                    line_number=self._line_number(line_starts, match.start()),
                    level=self._HEADING_ORDER[kind],
                    source_position=match.start(),
                )
            )

        headings = list(result)
        heading_positions = [item.source_position for item in headings]
        figure_ranges = self._figure_ranges(value, structural)
        figure_index = 0

        for match in self._IMAGE_PATTERN.finditer(structural):
            position = match.start()
            heading_index = bisect_right(heading_positions, position) - 1
            previous_heading = (
                headings[heading_index]
                if 0 <= heading_index < len(headings)
                else None
            )
            image_level = (
                min(previous_heading.level + 1, 7)
                if previous_heading is not None
                else 7
            )

            while (
                figure_index < len(figure_ranges)
                and figure_ranges[figure_index][1] < position
            ):
                figure_index += 1

            caption = ""
            if figure_index < len(figure_ranges):
                start, end, candidate_caption = figure_ranges[figure_index]
                if start <= position <= end:
                    caption = candidate_caption

            raw_path = value[match.start("path"):match.end("path")]
            title = caption or self._image_file_name(raw_path)
            result.append(
                LatexStructureItem(
                    kind="image",
                    title=title or "(image)",
                    line_number=self._line_number(line_starts, position),
                    level=image_level,
                    source_position=position,
                )
            )

        result.sort(key=lambda item: item.source_position)
        return result

    @staticmethod
    def _line_starts(source: str) -> list[int]:
        starts = [0]
        starts.extend(
            index + 1
            for index, character in enumerate(source)
            if character == "\n"
        )
        return starts

    @staticmethod
    def _line_number(line_starts: list[int], position: int) -> int:
        return max(bisect_right(line_starts, max(int(position), 0)), 1)

    def _figure_ranges(
        self,
        source: str,
        structural: str,
    ) -> list[tuple[int, int, str]]:
        """Return figure spans and captions in one forward pass."""
        ranges: list[tuple[int, int, str]] = []
        cursor = 0
        while True:
            begin = self._FIGURE_BEGIN_PATTERN.search(structural, cursor)
            if begin is None:
                break
            end = self._FIGURE_END_PATTERN.search(structural, begin.end())
            if end is None:
                break

            caption = ""
            caption_match = self._CAPTION_PATTERN.search(
                structural,
                begin.end(),
                end.start(),
            )
            if caption_match is not None:
                argument_start = self._skip_space(
                    structural,
                    caption_match.end(),
                )
                if (
                    argument_start < len(structural)
                    and structural[argument_start] == "{"
                ):
                    parsed = self._balanced_argument(
                        source,
                        argument_start,
                        "{",
                        "}",
                    )
                    if parsed is not None:
                        caption = self._display_title(parsed[0])

            ranges.append((begin.start(), end.end(), caption))
            cursor = end.end()
        return ranges

    @staticmethod
    def _image_file_name(raw_path: str) -> str:
        text = raw_path.strip()
        text = re.sub(r"\\[A-Za-z@]+", "", text)
        text = text.replace("{", "").replace("}", "").strip()
        if not text:
            return raw_path.strip()
        normalized = text.replace("\\", "/")
        return Path(normalized).name or normalized

    def _display_title(self, raw: str) -> str:
        text = raw.strip()
        pdf_title = self._texorpdfstring_pdf_title(text)
        if pdf_title is not None:
            text = pdf_title

        text = re.sub(r"\\protect\b\s*", "", text)
        text = re.sub(
            r"\\hypertarget\s*\{[^{}]*\}\s*\{[^{}]*\}",
            "",
            text,
        )
        text = re.sub(
            r"\\(?:label|index)\s*\{[^{}]*\}",
            "",
            text,
        )

        for _ in range(5):
            updated = re.sub(
                r"\\(?:textbf|textit|emph|texttt|textrm|textsf|underline)"
                r"\s*\{([^{}]*)\}",
                r"\1",
                text,
            )
            if updated == text:
                break
            text = updated

        replacements = {
            r"\&": "&",
            r"\%": "%",
            r"\_": "_",
            r"\#": "#",
            r"\$": "$",
            "~": " ",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        text = re.sub(r"\\[A-Za-z@]+\*?", "", text)
        text = text.replace("{", "").replace("}", "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _texorpdfstring_pdf_title(self, text: str) -> str | None:
        match = re.search(r"\\texorpdfstring\b", text)
        if match is None:
            return None

        cursor = self._skip_space(text, match.end())
        if cursor >= len(text) or text[cursor] != "{":
            return None
        first = self._balanced_argument(text, cursor, "{", "}")
        if first is None:
            return None

        _, cursor = first
        cursor = self._skip_space(text, cursor)
        if cursor >= len(text) or text[cursor] != "{":
            return None
        second = self._balanced_argument(text, cursor, "{", "}")
        if second is None:
            return None

        return second[0]

    def _mask_comments_and_literal_environments(self, source: str) -> str:
        output: list[str] = []
        literal_environment: str | None = None

        for line in source.splitlines(keepends=True):
            ending = "\n" if line.endswith("\n") else ""
            body = line[:-1] if ending else line

            if literal_environment is not None:
                end_pattern = re.compile(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}"
                )
                if end_pattern.search(body):
                    literal_environment = None
                output.append(" " * len(body) + ending)
                continue

            begin = self._LITERAL_BEGIN_PATTERN.search(body)
            if begin is not None:
                prefix = self._mask_comment(body[:begin.start()])
                output.append(
                    prefix
                    + " " * (len(body) - len(prefix))
                    + ending
                )
                name = begin.group("name")
                if re.search(
                    rf"\\end\s*\{{{re.escape(name)}\}}",
                    body[begin.end():],
                ) is None:
                    literal_environment = name
                continue

            output.append(self._mask_comment(body) + ending)

        return "".join(output)

    @staticmethod
    def _mask_comment(line: str) -> str:
        for index, character in enumerate(line):
            if character != "%":
                continue

            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1

            if backslashes % 2 == 0:
                return line[:index] + " " * (len(line) - index)

        return line

    def _balanced_argument(
        self,
        source: str,
        opening_index: int,
        opening: str,
        closing: str,
    ) -> tuple[str, int] | None:
        if opening_index >= len(source) or source[opening_index] != opening:
            return None

        depth = 0
        escaped = False
        for index in range(opening_index, len(source)):
            character = source[index]
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth == 0:
                    return source[opening_index + 1:index], index + 1
        return None

    @staticmethod
    def _skip_space(source: str, index: int) -> int:
        while index < len(source) and source[index].isspace():
            index += 1
        return index
