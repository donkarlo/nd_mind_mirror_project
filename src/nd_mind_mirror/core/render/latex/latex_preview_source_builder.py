from pathlib import Path
import re


class LatexPreviewSourceBuilder:
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
        r"\\(?P<name>part|chapter|section|subsection|subsubsection|paragraph|subparagraph)"
        r"\*?\s*(?:\[[^\]]*\]\s*)?\{"
    )
    _DOCUMENT_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{document\}"
    )
    _DOCUMENT_END_PATTERN = re.compile(
        r"\\end\s*\{document\}"
    )
    _TITLE_PATTERN = re.compile(r"\\title\s*\{")
    _BIBLIOGRAPHY_PATTERN = re.compile(
        r"(?m)^\s*\\(?:bibliographystyle|bibliography|printbibliography)\b"
    )
    _CONTENT_MARKERS = (
        "{{ND_MIND_MIRROR_CONTENT}}",
        "% ND_MIND_MIRROR_CONTENT",
    )
    _BEAMER_FRAGMENT_PATTERN = re.compile(
        r"\\begin\s*\{frame\}"
        r"|\\frame(?:\s*<[^>]*>)?\s*\{"
    )

    def __init__(
        self,
        template_path: str | Path,
        beamer_template_path: str | Path | None = None,
    ) -> None:
        self.set_template_path(template_path)
        self.set_beamer_template_path(beamer_template_path)

    @property
    def template_path(self) -> Path:
        return self._template_path

    def set_template_path(
        self,
        template_path: str | Path,
    ) -> None:
        self._template_path = Path(
            template_path
        ).expanduser().resolve()

    @property
    def beamer_template_path(self) -> Path | None:
        return self._beamer_template_path

    def set_beamer_template_path(
        self,
        beamer_template_path: str | Path | None,
    ) -> None:
        if beamer_template_path in (None, ""):
            self._beamer_template_path = None
            return

        self._beamer_template_path = Path(
            beamer_template_path
        ).expanduser().resolve()

    def build(
        self,
        source: str,
        source_path: str | Path | None = None,
        title_source: str | None = None,
    ) -> str:
        if "\\documentclass" in source:
            return source

        template = self._read_template(
            self._template_for_source(source)
        )
        fragment = self._extract_body(source)
        heading_source = (
            title_source
            if title_source is not None
            else source
        )
        title = self.extract_title(heading_source)

        if title:
            template = self._replace_title(
                template,
                title,
            )

        return self._insert_fragment(
            template,
            fragment,
        )

    def extract_title(self, source: str) -> str | None:
        cleaned = self._strip_comments(source)
        candidates: list[tuple[int, int, str]] = []

        for match in self._HEADING_PATTERN.finditer(cleaned):
            title = self._balanced_argument(
                cleaned,
                match.end() - 1,
            )
            if title is None:
                continue

            normalized = title.strip()
            if not normalized:
                continue

            rank = self._HEADING_ORDER[
                match.group("name")
            ]
            candidates.append(
                (rank, match.start(), normalized)
            )

        if not candidates:
            return None

        best_rank = min(
            rank
            for rank, _, _ in candidates
        )

        for rank, _, title in candidates:
            if rank == best_rank:
                return title

        return None

    def _template_for_source(self, source: str) -> Path:
        cleaned = self._strip_comments(source)
        if (
            self._beamer_template_path is not None
            and self._BEAMER_FRAGMENT_PATTERN.search(cleaned) is not None
        ):
            return self._beamer_template_path
        return self._template_path

    def _read_template(self, template_path: Path) -> str:
        try:
            template = template_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise OSError(
                "Could not read LaTeX preview template: "
                f"{template_path}: {exc}"
            ) from exc

        if self._DOCUMENT_BEGIN_PATTERN.search(template) is None:
            raise ValueError(
                "LaTeX preview template has no "
                "\\begin{document}: "
                f"{template_path}"
            )

        if self._DOCUMENT_END_PATTERN.search(template) is None:
            raise ValueError(
                "LaTeX preview template has no "
                "\\end{document}: "
                f"{template_path}"
            )

        return template

    def _extract_body(self, source: str) -> str:
        begin = self._DOCUMENT_BEGIN_PATTERN.search(source)
        if begin is None:
            return source

        end_matches = list(
            self._DOCUMENT_END_PATTERN.finditer(source)
        )
        if not end_matches:
            return source[begin.end():]

        end = end_matches[-1]
        if end.start() < begin.end():
            return source

        return source[begin.end():end.start()]

    def _replace_title(
        self,
        template: str,
        title: str,
    ) -> str:
        match = self._TITLE_PATTERN.search(template)
        if match is not None:
            closing_index = self._matching_brace_index(
                template,
                match.end() - 1,
            )
            if closing_index is not None:
                return (
                    template[:match.end()]
                    + title
                    + template[closing_index:]
                )

        document_begin = self._DOCUMENT_BEGIN_PATTERN.search(
            template
        )
        if document_begin is None:
            return template

        insertion = f"\\title{{{title}}}\n"
        return (
            template[:document_begin.start()]
            + insertion
            + template[document_begin.start():]
        )

    def _insert_fragment(
        self,
        template: str,
        fragment: str,
    ) -> str:
        content = fragment.strip("\n")
        insertion = f"\n{content}\n" if content else "\n"

        for marker in self._CONTENT_MARKERS:
            if marker in template:
                return template.replace(
                    marker,
                    insertion.strip("\n"),
                    1,
                )

        bibliography = self._BIBLIOGRAPHY_PATTERN.search(
            template
        )
        if bibliography is not None:
            return (
                template[:bibliography.start()]
                + insertion
                + template[bibliography.start():]
            )

        end_matches = list(
            self._DOCUMENT_END_PATTERN.finditer(template)
        )
        if not end_matches:
            return template + insertion

        end = end_matches[-1]
        return (
            template[:end.start()]
            + insertion
            + template[end.start():]
        )

    def _balanced_argument(
        self,
        text: str,
        opening_index: int,
    ) -> str | None:
        closing_index = self._matching_brace_index(
            text,
            opening_index,
        )
        if closing_index is None:
            return None

        return text[
            opening_index + 1:closing_index
        ]

    def _matching_brace_index(
        self,
        text: str,
        opening_index: int,
    ) -> int | None:
        if (
            opening_index < 0
            or opening_index >= len(text)
            or text[opening_index] != "{"
        ):
            return None

        depth = 0
        escaped = False

        for index in range(opening_index, len(text)):
            character = text[index]

            if escaped:
                escaped = False
                continue

            if character == "\\":
                escaped = True
                continue

            if character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    return index

        return None

    def _strip_comments(self, source: str) -> str:
        cleaned_lines = []

        for line in source.splitlines():
            output = []
            backslashes = 0

            for character in line:
                if character == "%" and backslashes % 2 == 0:
                    break

                output.append(character)

                if character == "\\":
                    backslashes += 1
                else:
                    backslashes = 0

            cleaned_lines.append("".join(output))

        return "\n".join(cleaned_lines)
