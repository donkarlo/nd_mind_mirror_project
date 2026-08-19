import re


class HeadingHierarchyTransformer:
    _CANONICAL_HEADINGS = (
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
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

    _ARTICLE_LIKE_CLASSES = {
        "article",
        "scrartcl",
        "extarticle",
        "amsart",
        "revtex4",
        "revtex4-1",
        "revtex4-2",
    }

    _HEADING_PATTERN = re.compile(
        r"\\(?P<heading>"
        r"part|chapter|section|subsection|subsubsection|"
        r"paragraph|subparagraph"
        r")(?P<star>\*)?"
        r"(?![A-Za-z@])"
    )

    def __init__(self, document_class: str = "article") -> None:
        self.configure(document_class)

    @property
    def document_class(self) -> str:
        return self._document_class

    @property
    def allowed_headings(self) -> tuple[str, ...]:
        return self._allowed_headings

    def configure(self, document_class: str) -> None:
        normalized = document_class.strip().lower()
        self._document_class = normalized or "article"

        if self._document_class in self._BOOK_LIKE_CLASSES:
            self._allowed_headings = (
                "part",
                "chapter",
                "section",
                "subsection",
                "subsubsection",
                "paragraph",
                "subparagraph",
            )
            return

        self._allowed_headings = (
            "part",
            "section",
            "subsection",
            "subsubsection",
            "paragraph",
            "subparagraph",
        )

    def target_for_child(
        self,
        parent_heading: str | None,
    ) -> str:
        if parent_heading is None:
            return "section"

        if parent_heading in self._allowed_headings:
            index = self._allowed_headings.index(parent_heading)
            if index + 1 < len(self._allowed_headings):
                return self._allowed_headings[index + 1]

            return self._allowed_headings[-1]

        if parent_heading == "chapter":
            return "section"

        if parent_heading == "part":
            if "chapter" in self._allowed_headings:
                return "chapter"
            return "section"

        return "section"

    def build_mapping(
        self,
        source: str,
        target_heading: str,
    ) -> dict[str, str]:
        headings = self.headings_in(source)

        if not headings:
            return {}

        top_heading = min(
            headings,
            key=self._canonical_index,
        )
        top_index = self._canonical_index(top_heading)

        if target_heading not in self._allowed_headings:
            target_heading = "section"

        target_index = self._allowed_headings.index(
            target_heading
        )

        mapping = {}

        for heading in set(headings):
            offset = (
                self._canonical_index(heading)
                - top_index
            )

            destination_index = min(
                target_index + max(offset, 0),
                len(self._allowed_headings) - 1,
            )

            mapping[heading] = (
                self._allowed_headings[
                    destination_index
                ]
            )

        return mapping

    def transform(
        self,
        source: str,
        mapping: dict[str, str],
    ) -> str:
        if not mapping:
            return source

        def replace(match: re.Match[str]) -> str:
            heading = match.group("heading")
            star = match.group("star") or ""
            replacement = mapping.get(
                heading,
                heading,
            )

            return "\\" + replacement + star

        return self._HEADING_PATTERN.sub(
            replace,
            source,
        )

    def last_heading(
        self,
        source: str,
    ) -> str | None:
        matches = list(
            self._HEADING_PATTERN.finditer(source)
        )

        if not matches:
            return None

        return matches[-1].group("heading")

    def headings_in(
        self,
        source: str,
    ) -> list[str]:
        structural_source = self._structural_source(
            source
        )

        return [
            match.group("heading")
            for match in self._HEADING_PATTERN.finditer(
                structural_source
            )
        ]

    def _structural_source(
        self,
        source: str,
    ) -> str:
        output = []
        literal_environment = None

        literal_begin_pattern = re.compile(
            r"\\begin\s*\{"
            r"(?P<name>verbatim|Verbatim|lstlisting|minted)"
            r"\}"
        )

        for line in source.splitlines(
            keepends=True
        ):
            if literal_environment is not None:
                if re.search(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                    line,
                ):
                    literal_environment = None

                output.append("\n")
                continue

            literal_match = literal_begin_pattern.search(
                line
            )

            if literal_match is not None:
                prefix = line[
                    :literal_match.start()
                ]
                output.append(
                    self._remove_comment(prefix)
                    + "\n"
                )

                literal_environment = (
                    literal_match.group("name")
                )

                if re.search(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                    line[literal_match.start():],
                ):
                    literal_environment = None

                continue

            output.append(
                self._remove_comment(line)
            )

        return "".join(output)

    def _remove_comment(
        self,
        line: str,
    ) -> str:
        for index, character in enumerate(line):
            if character != "%":
                continue

            backslashes = 0
            cursor = index - 1

            while (
                cursor >= 0
                and line[cursor] == "\\"
            ):
                backslashes += 1
                cursor -= 1

            if backslashes % 2 == 0:
                return line[:index]

        return line

    def _canonical_index(
        self,
        heading: str,
    ) -> int:
        try:
            return self._CANONICAL_HEADINGS.index(
                heading
            )
        except ValueError:
            return len(self._CANONICAL_HEADINGS)
