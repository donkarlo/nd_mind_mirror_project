import re


class LatexIndentationEngine:
    _DOCUMENT_CLASS_PATTERN = re.compile(
        r"\\documentclass(?:\[[^\]]*\])?\{(?P<name>[^}]+)\}"
    )
    _TOKEN_PATTERN = re.compile(
        r"\\(?:(?P<heading>part|chapter|section|subsection|"
        r"subsubsection|paragraph|subparagraph)\*?(?![A-Za-z@])|"
        r"begin\s*\{(?P<begin>[^}]+)\}|"
        r"end\s*\{(?P<end>[^}]+)\})"
    )
    _BOOK_LIKE_CLASSES = {
        "book",
        "report",
        "memoir",
        "scrbook",
        "scrreprt",
        "extbook",
        "extreport",
        "tufte-book",
    }
    _LITERAL_ENVIRONMENTS = {
        "verbatim",
        "Verbatim",
        "lstlisting",
        "minted",
    }
    _LIST_ENVIRONMENTS = {"itemize", "enumerate", "description"}

    def __init__(self, indent_size: int = 4) -> None:
        self._indent_size = max(int(indent_size), 1)

    @property
    def indent_unit(self) -> str:
        return " " * self._indent_size

    def set_indent_size(self, indent_size: int) -> None:
        self._indent_size = max(int(indent_size), 1)

    def indent_for_new_line(
        self,
        document_text: str,
        cursor_position: int,
    ) -> str:
        position = max(
            0,
            min(cursor_position, len(document_text)),
        )
        prefix = document_text[:position]
        current_line = self._current_line(
            document_text,
            position,
        )
        leading = self.leading_whitespace(current_line)
        code = self._remove_comment(current_line).strip()

        logical_units = self._logical_indent_units(prefix)

        if re.match(r"\\item\b", code):
            logical_units += 1

        logical_indent = self.indent_unit * logical_units

        if len(leading) > len(logical_indent):
            return leading

        return logical_indent


    def list_item_continuation(
        self,
        document_text: str,
        cursor_position: int,
    ) -> str | None:
        r"""Return the next ``\item`` prefix when Enter continues a list item.

        Only the current source line and environments that are actually open at
        the cursor are considered. The source itself is never rewritten here.
        """
        position = max(0, min(int(cursor_position), len(document_text)))
        line_start = document_text.rfind("\n", 0, position) + 1
        current_prefix = document_text[line_start:position]
        leading = self.leading_whitespace(current_prefix)
        code = self._remove_comment(current_prefix).strip()
        if not re.match(r"^\\item(?:\s*\[[^\]]*\])?(?:\s|$)", code):
            return None

        structural_source = self._structural_source(document_text[:position])
        environment_stack: list[str] = []
        for match in self._TOKEN_PATTERN.finditer(structural_source):
            begin = match.group("begin")
            end = match.group("end")
            if begin is not None:
                if begin != "document":
                    environment_stack.append(begin)
                continue
            if end is not None and end != "document":
                self._pop_environment(environment_stack, end)

        if not any(
            environment in self._LIST_ENVIRONMENTS
            for environment in environment_stack
        ):
            return None
        return f"{leading}\\item "

    def indentation_at_cursor(
        self,
        document_text: str,
        cursor_position: int,
    ) -> str:
        position = max(
            0,
            min(cursor_position, len(document_text)),
        )
        current_line = self._current_line(
            document_text,
            position,
        )
        leading = self.leading_whitespace(current_line)
        logical = self.indent_unit * self._logical_indent_units(
            document_text[:position]
        )

        return leading if len(leading) > len(logical) else logical

    def leading_whitespace(self, line: str) -> str:
        match = re.match(r"^[ \t]*", line)
        return match.group(0) if match else ""

    def _logical_indent_units(self, prefix: str) -> int:
        document_class = self._document_class(prefix)
        structural_source = self._structural_source(prefix)
        environment_stack: list[str] = []
        document_open = False
        heading_units = 0

        for match in self._TOKEN_PATTERN.finditer(
            structural_source
        ):
            heading = match.group("heading")
            begin = match.group("begin")
            end = match.group("end")

            if heading is not None:
                heading_units = self._heading_content_units(
                    document_class,
                    heading,
                )
                continue

            if begin is not None:
                if begin == "document":
                    document_open = True
                    heading_units = max(
                        heading_units,
                        1,
                    )
                else:
                    environment_stack.append(begin)
                continue

            if end is not None:
                if end == "document":
                    document_open = False
                    environment_stack.clear()
                    heading_units = 0
                    continue

                self._pop_environment(
                    environment_stack,
                    end,
                )

        if not document_open:
            return 0

        return max(heading_units, 1) + len(
            environment_stack
        )

    def _heading_content_units(
        self,
        document_class: str,
        heading: str,
    ) -> int:
        if document_class in self._BOOK_LIKE_CLASSES:
            depth_map = {
                "part": 2,
                "chapter": 2,
                "section": 3,
                "subsection": 4,
                "subsubsection": 5,
                "paragraph": 6,
                "subparagraph": 7,
            }
        else:
            depth_map = {
                "part": 2,
                "chapter": 2,
                "section": 2,
                "subsection": 3,
                "subsubsection": 4,
                "paragraph": 5,
                "subparagraph": 6,
            }

        return depth_map.get(heading, 1)

    def _document_class(self, document_text: str) -> str:
        match = self._DOCUMENT_CLASS_PATTERN.search(document_text)

        if match is None:
            return "article"

        return match.group("name").strip().lower()

    def _current_line(
        self,
        document_text: str,
        cursor_position: int,
    ) -> str:
        start = document_text.rfind(
            "\n",
            0,
            cursor_position,
        ) + 1
        return document_text[start:cursor_position]

    def _structural_source(self, source: str) -> str:
        output = []
        literal_environment: str | None = None

        for line in source.splitlines(keepends=True):
            if literal_environment is not None:
                if re.search(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                    line,
                ):
                    literal_environment = None

                output.append("\n")
                continue

            clean_line = self._remove_comment(line)
            literal_match = re.search(
                r"\\begin\s*\{(?P<name>verbatim|Verbatim|lstlisting|minted)\}",
                clean_line,
            )

            if literal_match is None:
                output.append(clean_line)
                continue

            output.append(
                clean_line[:literal_match.start()] + "\n"
            )
            literal_environment = literal_match.group("name")

            if re.search(
                rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                clean_line[literal_match.end():],
            ):
                literal_environment = None

        return "".join(output)

    def _remove_comment(self, line: str) -> str:
        for index, character in enumerate(line):
            if character != "%":
                continue

            backslashes = 0
            cursor = index - 1

            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1

            if backslashes % 2 == 0:
                return line[:index]

        return line

    def _pop_environment(
        self,
        environment_stack: list[str],
        environment: str,
    ) -> None:
        for index in range(
            len(environment_stack) - 1,
            -1,
            -1,
        ):
            if environment_stack[index] == environment:
                del environment_stack[index:]
                return
