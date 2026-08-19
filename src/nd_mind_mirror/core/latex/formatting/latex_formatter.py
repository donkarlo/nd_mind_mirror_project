import re


class LatexFormatter:
    _DOCUMENT_CLASS_PATTERN = re.compile(
        r"\\documentclass(?:\[[^\]]*\])?\{(?P<name>[^}]+)\}"
    )
    _HEADING_PATTERN = re.compile(
        r"^\\(?P<heading>"
        r"part|chapter|section|subsection|subsubsection|"
        r"paragraph|subparagraph"
        r")\*?(?![A-Za-z@])"
    )
    _BEGIN_PATTERN = re.compile(
        r"^\\begin\s*\{(?P<name>[^}]+)\}"
    )
    _END_PATTERN = re.compile(
        r"^\\end\s*\{(?P<name>[^}]+)\}"
    )
    _ITEM_PATTERN = re.compile(r"^\\item\b")
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

    def __init__(self, indent_size: int = 4) -> None:
        self._indent_size = max(int(indent_size), 1)

    def set_indent_size(self, indent_size: int) -> None:
        self._indent_size = max(int(indent_size), 1)

    def format(self, source: str) -> str:
        if not source:
            return source

        indent_unit = " " * self._indent_size
        document_class = self._document_class(source)
        document_open = False
        heading_content_units = 0
        environment_stack: list[str] = []
        literal_environment: str | None = None
        formatted_lines = []

        for original_line in source.splitlines():
            if literal_environment is not None:
                closing_environment = literal_environment
                closing_pattern = re.compile(
                    rf"^\\end\s*\{{{re.escape(closing_environment)}\}}"
                )
                stripped_literal = original_line.strip()

                if closing_pattern.match(stripped_literal):
                    literal_environment = None
                    self._pop_environment(
                        environment_stack,
                        closing_environment,
                    )
                    indentation_units = (
                        max(
                            heading_content_units,
                            1,
                        )
                        + len(environment_stack)
                        if document_open
                        else 0
                    )
                    formatted_lines.append(
                        indent_unit
                        * indentation_units
                        + stripped_literal
                    )
                else:
                    formatted_lines.append(
                        original_line
                    )

                continue

            stripped = original_line.strip()

            if not stripped:
                formatted_lines.append("")
                continue

            code = self._remove_comment(stripped).strip()
            end_match = self._END_PATTERN.match(code)

            if end_match is not None:
                environment = end_match.group("name")

                if environment == "document":
                    document_open = False
                    heading_content_units = 0
                    environment_stack.clear()
                    formatted_lines.append(stripped)
                    continue

                self._pop_environment(
                    environment_stack,
                    environment,
                )

            if not document_open:
                indentation_units = 0
            else:
                indentation_units = max(
                    heading_content_units,
                    1,
                ) + len(environment_stack)

            heading_match = self._HEADING_PATTERN.match(code)

            if heading_match is not None and document_open:
                heading = heading_match.group("heading")
                content_units = self._heading_content_units(
                    document_class,
                    heading,
                )
                indentation_units = max(
                    content_units - 1,
                    1,
                )

            if end_match is not None and document_open:
                indentation_units = max(
                    heading_content_units,
                    1,
                ) + len(environment_stack)

            formatted_lines.append(
                indent_unit * indentation_units + stripped
            )

            begin_match = self._BEGIN_PATTERN.match(code)

            if begin_match is not None:
                environment = begin_match.group("name")

                if environment == "document":
                    document_open = True
                    heading_content_units = 1
                    continue

                environment_stack.append(environment)

                if environment in self._LITERAL_ENVIRONMENTS:
                    literal_environment = environment

            if heading_match is not None and document_open:
                heading_content_units = self._heading_content_units(
                    document_class,
                    heading_match.group("heading"),
                )

        suffix = "\n" if source.endswith("\n") else ""
        return "\n".join(formatted_lines) + suffix

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

    def _document_class(self, source: str) -> str:
        match = self._DOCUMENT_CLASS_PATTERN.search(source)

        if match is None:
            return "article"

        name = match.group("name").strip().casefold()

        if "," in name:
            name = name.split(",", 1)[0].strip()

        return name or "article"

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
        environment: str | None,
    ) -> None:
        if not environment:
            return

        for index in range(
            len(environment_stack) - 1,
            -1,
            -1,
        ):
            if environment_stack[index] == environment:
                del environment_stack[index:]
                return
