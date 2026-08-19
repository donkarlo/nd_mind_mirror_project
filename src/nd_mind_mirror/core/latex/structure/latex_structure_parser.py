from dataclasses import dataclass
import re


@dataclass(frozen=True)
class LatexStructureItem:
    kind: str
    title: str
    line_number: int
    level: int
    source_position: int


class LatexStructureParser:
    """Extract LaTeX structural headings without modifying source text."""

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
    _LITERAL_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{(?P<name>verbatim|Verbatim|lstlisting|minted)\}"
    )

    def parse(self, source: str) -> list[LatexStructureItem]:
        structural = self._mask_comments_and_literal_environments(source)
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
            display_title = self._display_title(raw_title)
            if not display_title:
                display_title = "(untitled)"

            kind = match.group("kind")
            result.append(
                LatexStructureItem(
                    kind=kind,
                    title=display_title,
                    line_number=structural.count("\n", 0, match.start()) + 1,
                    level=self._HEADING_ORDER[kind],
                    source_position=match.start(),
                )
            )

        return result

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

        # Preserve the visible argument of common inline formatting commands.
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

        # Keep accent sequences such as M\"obius readable rather than trying
        # to execute TeX. Remove remaining control-word syntax only.
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
                if re.search(rf"\\end\s*\{{{re.escape(name)}\}}", body[begin.end():]) is None:
                    literal_environment = name
                continue

            output.append(self._mask_comment(body) + ending)

        return "".join(output)

    def _mask_comment(self, line: str) -> str:
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

    def _skip_space(self, source: str, index: int) -> int:
        while index < len(source) and source[index].isspace():
            index += 1
        return index
