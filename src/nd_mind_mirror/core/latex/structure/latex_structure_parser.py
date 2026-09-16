"""Parse LaTeX headings, figures, images, and tables into semantic tree nodes."""

from bisect import bisect_right
from dataclasses import replace
from pathlib import Path
import re

from nd_mind_mirror.core.latex.structure.latex_structure_item import (
    LatexStructureItem,
)


class LatexStructureParser:
    """Extract source-ordered LaTeX nodes with explicit parents and movable spans."""

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
        r"paragraph|subparagraph)(?P<star>\*)?(?![A-Za-z@])"
    )
    _IMAGE_PATTERN = re.compile(
        r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^{}]+)\}"
    )
    _FIGURE_BEGIN_PATTERN = re.compile(r"\\begin\s*\{figure\*?\}")
    _FIGURE_END_PATTERN = re.compile(r"\\end\s*\{figure\*?\}")
    _TABLE_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{(?P<name>table\*?|longtable|tabular\*?|tabularx)\}"
    )
    _TABLE_END_TEMPLATE = r"\\end\s*\{%s\}"
    _CAPTION_PATTERN = re.compile(r"\\caption(?:\s*\[[^\]]*\])?\s*")
    _DOCUMENT_END_PATTERN = re.compile(r"\\end\s*\{document\}")
    _LITERAL_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{(?P<name>verbatim|Verbatim|lstlisting|minted)\}"
    )

    def parse(self, source: str) -> list[LatexStructureItem]:
        """Return a semantic tree flattened in source order."""
        value = str(source)
        structural = self._mask_comments_and_literal_environments(value)
        line_starts = self._line_starts(structural)

        headings = self._parse_headings(value, structural, line_starts)
        result = list(headings)

        figure_ranges = self._environment_ranges(
            value,
            structural,
            self._FIGURE_BEGIN_PATTERN,
            lambda _match: self._FIGURE_END_PATTERN,
        )
        table_ranges = self._table_ranges(value, structural)

        emitted_figure_spans: set[tuple[int, int]] = set()
        for match in self._IMAGE_PATTERN.finditer(structural):
            position = match.start()
            containing_figure = self._containing_range(figure_ranges, position)
            if containing_figure is not None:
                start, end, caption = containing_figure
                figure_span = (start, end)
                if figure_span in emitted_figure_spans:
                    continue
                emitted_figure_spans.add(figure_span)
            else:
                start, end, caption = match.start(), match.end(), ""

            raw_path = value[match.start("path"):match.end("path")]
            title = caption or self._image_file_name(raw_path) or "(image)"
            result.append(
                self._leaf_item(
                    headings,
                    kind="image",
                    title=title,
                    line_number=self._line_number(line_starts, start),
                    source_position=start,
                    source_end=end,
                )
            )

        occupied_table_ranges: list[tuple[int, int]] = []
        for start, end, caption, environment in table_ranges:
            if environment in {"tabular", "tabular*", "tabularx"} and any(
                outer_start <= start and end <= outer_end
                for outer_start, outer_end in occupied_table_ranges
            ):
                continue
            if environment in {"table", "table*", "longtable"}:
                occupied_table_ranges.append((start, end))
            result.append(
                self._leaf_item(
                    headings,
                    kind="table",
                    title=caption or f"({environment})",
                    line_number=self._line_number(line_starts, start),
                    source_position=start,
                    source_end=end,
                )
            )

        result.sort(key=lambda item: (item.source_position, item.level))
        return self._assign_sibling_indexes(result)

    def _parse_headings(
        self,
        source: str,
        structural: str,
        line_starts: list[int],
    ) -> list[LatexStructureItem]:
        """Parse heading commands and assign explicit semantic parents."""
        raw: list[LatexStructureItem] = []
        heading_stack: list[LatexStructureItem] = []

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
            title = optional_title if optional_title and optional_title.strip() else required_title
            kind = match.group("kind")
            rank = self._HEADING_ORDER[kind]

            while (
                heading_stack
                and self._HEADING_ORDER[heading_stack[-1].kind] >= rank
            ):
                heading_stack.pop()

            parent = heading_stack[-1] if heading_stack else None
            item = LatexStructureItem(
                kind=kind,
                title=self._display_title(title) or "(untitled)",
                line_number=self._line_number(line_starts, match.start()),
                level=self._HEADING_ORDER[kind],
                source_position=match.start(),
                source_end=len(source),
                parent_source_position=(
                    parent.source_position if parent is not None else None
                ),
            )
            raw.append(item)
            heading_stack.append(item)

        document_end_match = self._DOCUMENT_END_PATTERN.search(structural)
        document_end = document_end_match.start() if document_end_match else len(source)
        complete: list[LatexStructureItem] = []
        for index, item in enumerate(raw):
            end = document_end
            item_rank = self._HEADING_ORDER[item.kind]
            for candidate in raw[index + 1:]:
                if self._HEADING_ORDER[candidate.kind] <= item_rank:
                    end = candidate.source_position
                    break
            complete.append(
                replace(
                    item,
                    source_end=max(end, item.source_position),
                )
            )
        return complete

    def _leaf_item(
        self,
        headings: list[LatexStructureItem],
        *,
        kind: str,
        title: str,
        line_number: int,
        source_position: int,
        source_end: int,
    ) -> LatexStructureItem:
        parent = self._parent_heading_for_position(headings, source_position)
        return LatexStructureItem(
            kind=kind,
            title=title,
            line_number=line_number,
            # Leaves are never structural parents. Keep them below every
            # heading rank so the legacy stack renderer always pops a leaf
            # before attaching the next heading.
            level=7,
            source_position=source_position,
            source_end=source_end,
            parent_source_position=(
                parent.source_position if parent is not None else None
            ),
        )

    @staticmethod
    def _parent_heading_for_position(
        headings: list[LatexStructureItem],
        position: int,
    ) -> LatexStructureItem | None:
        for heading in reversed(headings):
            if heading.source_position < position < heading.source_end:
                return heading
        return None

    @staticmethod
    def _assign_sibling_indexes(
        structure: list[LatexStructureItem],
    ) -> list[LatexStructureItem]:
        counters: dict[int | None, int] = {}
        result: list[LatexStructureItem] = []
        for item in structure:
            parent = item.parent_source_position
            index = counters.get(parent, 0)
            result.append(replace(item, sibling_index=index))
            counters[parent] = index + 1
        return result

    def _table_ranges(
        self,
        source: str,
        structural: str,
    ) -> list[tuple[int, int, str, str]]:
        ranges: list[tuple[int, int, str, str]] = []
        cursor = 0
        while True:
            begin = self._TABLE_BEGIN_PATTERN.search(structural, cursor)
            if begin is None:
                break
            environment = begin.group("name")
            end_pattern = re.compile(
                self._TABLE_END_TEMPLATE % re.escape(environment)
            )
            end = end_pattern.search(structural, begin.end())
            if end is None:
                cursor = begin.end()
                continue
            caption = self._caption_in_range(
                source,
                structural,
                begin.end(),
                end.start(),
            )
            ranges.append((begin.start(), end.end(), caption, environment))
            cursor = begin.end()
        return ranges

    def _environment_ranges(
        self,
        source: str,
        structural: str,
        begin_pattern: re.Pattern[str],
        end_pattern_factory,
    ) -> list[tuple[int, int, str]]:
        ranges: list[tuple[int, int, str]] = []
        cursor = 0
        while True:
            begin = begin_pattern.search(structural, cursor)
            if begin is None:
                break
            end_pattern = end_pattern_factory(begin)
            end = end_pattern.search(structural, begin.end())
            if end is None:
                break
            caption = self._caption_in_range(
                source,
                structural,
                begin.end(),
                end.start(),
            )
            ranges.append((begin.start(), end.end(), caption))
            cursor = end.end()
        return ranges

    def _caption_in_range(
        self,
        source: str,
        structural: str,
        start: int,
        end: int,
    ) -> str:
        caption_match = self._CAPTION_PATTERN.search(structural, start, end)
        if caption_match is None:
            return ""
        argument_start = self._skip_space(structural, caption_match.end())
        if argument_start >= len(structural) or structural[argument_start] != "{":
            return ""
        parsed = self._balanced_argument(source, argument_start, "{", "}")
        return self._display_title(parsed[0]) if parsed is not None else ""

    @staticmethod
    def _containing_range(
        ranges: list[tuple[int, int, str]],
        position: int,
    ) -> tuple[int, int, str] | None:
        for start, end, caption in ranges:
            if start <= position <= end:
                return start, end, caption
        return None

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
        text = re.sub(r"\\(?:label|index)\s*\{[^{}]*\}", "", text)
        for _ in range(5):
            updated = re.sub(
                r"\\(?:textbf|textit|emph|texttt|textrm|textsf|underline)\s*\{([^{}]*)\}",
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
        return re.sub(r"\s+", " ", text).strip()

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
        return second[0] if second is not None else None

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
                output.append(prefix + " " * (len(body) - len(prefix)) + ending)
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
