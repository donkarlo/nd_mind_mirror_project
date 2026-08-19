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
    _CHAPTER_FRAGMENT_PATTERN = re.compile(
        r"\\chapter\*?\s*(?:\[[^\]]*\]\s*)?\{"
    )
    _ARTICLE_CLASS_PATTERN = re.compile(
        r"\\documentclass(?P<options>\[[^\]]*\])?\{article\}"
    )
    _PERSIAN_SCRIPT_PATTERN = re.compile(
        "[\u0600-\u06ff\u0750-\u077f\u0870-\u089f"
        "\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]"
    )
    _BABEL_PACKAGE_PATTERN = re.compile(
        r"\\usepackage(?:\[[^\]]*\])?\{babel\}"
    )
    _PERSIAN_SUPPORT_PATTERN = re.compile(
        r"\\usepackage(?:\[[^\]]*\])?\{"
        r"(?:xepersian|arabluatex|polyglossia)\}"
        r"|\\babelprovide(?:\[[^\]]*\])?\{(?:persian|farsi)\}"
        r"|\\usepackage\[[^\]]*(?:persian|farsi)[^\]]*\]\{babel\}"
        r"|\\set(?:main|other)language(?:\[[^\]]*\])?\{(?:persian|farsi)\}",
        re.IGNORECASE,
    )
    _DOCUMENT_CLASS_LINE_PATTERN = re.compile(
        r"(?m)^\s*\\documentclass(?:\[[^\]]*\])?\{[^}]+\}\s*$"
    )
    _ALGORITHM_ENVIRONMENT_PATTERN = re.compile(
        r"\\begin\s*\{algorithm\}"
    )
    _ALGORITHMIC_ENVIRONMENT_PATTERN = re.compile(
        r"\\begin\s*\{algorithmic\}"
    )
    _COLORBOX_PATTERN = re.compile(r"\\colorbox\s*\{")

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
            prepared = self._repair_preview_wrappers(source)
            prepared = self._add_preview_package_support(prepared)
            return self._add_persian_preview_support(prepared)

        template = self._read_template(
            self._template_for_source(source)
        )
        fragment = self._extract_body(source)
        template = self._adapt_template_for_fragment_structure(
            template,
            fragment,
        )
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

        prepared = self._insert_fragment(
            template,
            fragment,
        )
        prepared = self._repair_preview_wrappers(prepared)
        prepared = self._add_preview_package_support(prepared)
        return self._add_persian_preview_support(prepared)


    def _repair_preview_wrappers(self, source: str) -> str:
        """Repair incomplete one-line editor helper wrappers for preview only.

        The formatting toolbar writes ``\\colorbox`` and ``\\textbf`` wrappers.
        While a user is editing a very large document, a wrapper can temporarily
        be incomplete (or a TeX comment can hide its closing brace).  LuaLaTeX
        then reports errors such as ``File ended while scanning use of\n        \\color@b@x`` and the whole live preview stops.  The source file is never
        modified here; only the generated temporary preview is made tolerant.

        The repair is intentionally conservative: only a ``\\colorbox`` that
        starts and fails to finish on the *same source line* is closed.  This is
        exactly the shape produced by the editor toolbar and keeps line numbers
        unchanged for SyncTeX.
        """
        repaired: list[str] = []
        for line in source.splitlines(keepends=True):
            repaired.append(self._repair_colorbox_line(line))
        return "".join(repaired)

    @staticmethod
    def _unescaped_comment_index(line: str) -> int | None:
        for index, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                return index
        return None

    def _repair_colorbox_line(self, line: str) -> str:
        newline = ""
        body = line
        if body.endswith("\r\n"):
            body, newline = body[:-2], "\r\n"
        elif body.endswith("\n"):
            body, newline = body[:-1], "\n"

        comment_index = self._unescaped_comment_index(body)
        if comment_index is None:
            code, comment = body, ""
        else:
            code, comment = body[:comment_index], body[comment_index:]

        search_from = 0
        while True:
            match = re.search(r"\\colorbox\s*\{", code[search_from:])
            if match is None:
                break
            start = search_from + match.start()
            cursor = start + match.group(0).find("{")
            depth = 0
            top_groups = 0
            complete = False
            escaped = False

            for pos in range(cursor, len(code)):
                char = code[pos]
                if escaped:
                    escaped = False
                    continue
                if char == "\\":
                    escaped = True
                    continue
                if char == "{":
                    if depth == 0:
                        top_groups += 1
                    depth += 1
                elif char == "}" and depth > 0:
                    depth -= 1
                    if depth == 0 and top_groups >= 2:
                        complete = True
                        search_from = pos + 1
                        break

            if complete:
                continue

            # A toolbar colorbox has two mandatory braced arguments.  Close a
            # partially typed/partially commented invocation before the comment
            # so the preview remains compilable.
            if top_groups >= 2 and depth > 0:
                code += "}" * depth
            elif top_groups == 1:
                code += ("}" * max(depth, 1)) + "{}"
            else:
                break
            search_from = len(code)

        return code + comment + newline

    def _add_preview_package_support(self, source: str) -> str:
        """Inject preview-only packages required by editor helpers.

        This never modifies the user's source file. It only makes the generated
        preview tolerant of fragment/full-document sources that use the toolbar
        highlight command or algorithm environments without spelling out the
        corresponding package in that particular file.
        """
        cleaned = self._strip_comments(source)
        packages: list[str] = []

        if (
            self._ALGORITHM_ENVIRONMENT_PATTERN.search(cleaned) is not None
            and not self._has_package(cleaned, "algorithm")
        ):
            packages.append("algorithm")

        if (
            self._ALGORITHMIC_ENVIRONMENT_PATTERN.search(cleaned) is not None
            and not self._has_package(cleaned, "algpseudocode")
            and not self._has_package(cleaned, "algorithmicx")
        ):
            packages.append("algpseudocode")

        if (
            self._COLORBOX_PATTERN.search(cleaned) is not None
            and not self._has_package(cleaned, "xcolor")
            and not self._has_package(cleaned, "color")
        ):
            packages.append("xcolor")

        if not packages:
            return source

        document_class = self._DOCUMENT_CLASS_LINE_PATTERN.search(source)
        if document_class is None:
            return source

        support = (
            "\n% Preview-only package support\n"
            + "".join(
                f"\\usepackage{{{package}}}\n"
                for package in packages
            )
        )
        return (
            source[:document_class.end()]
            + support
            + source[document_class.end():]
        )

    def _has_package(self, source: str, package: str) -> bool:
        expression = re.compile(
            r"\\usepackage(?:\[[^\]]*\])?\{[^}]*"
            + re.escape(package)
            + r"(?:\s*,|\s*\})",
            re.IGNORECASE,
        )
        return expression.search(source) is not None

    def _add_persian_preview_support(self, source: str) -> str:
        cleaned = self._strip_comments(source)
        if self._PERSIAN_SCRIPT_PATTERN.search(cleaned) is None:
            return source

        if self._PERSIAN_SUPPORT_PATTERN.search(cleaned) is not None:
            return source

        font_setup = (
            "\\babelfont{rm}{FreeSerif}\n"
            "\\babelfont{sf}{FreeSerif}\n"
            "\\babelfont{tt}{FreeSerif}\n"
        )

        babel_match = self._BABEL_PACKAGE_PATTERN.search(cleaned)
        if babel_match is not None:
            support = (
                "\n% Preview-only Persian support\n"
                "\\babelprovide[import,main]{persian}\n"
                + font_setup
            )
            source_babel_match = self._BABEL_PACKAGE_PATTERN.search(source)
            if source_babel_match is None:
                return source
            return (
                source[:source_babel_match.end()]
                + support
                + source[source_babel_match.end():]
            )

        document_class = self._DOCUMENT_CLASS_LINE_PATTERN.search(source)
        if document_class is None:
            return source

        support = (
            "\n% Preview-only Persian support\n"
            "\\usepackage[provide=*,bidi=basic]{babel}\n"
            "\\babelprovide[import,main]{persian}\n"
            + font_setup
        )
        return (
            source[:document_class.end()]
            + support
            + source[document_class.end():]
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

    def _adapt_template_for_fragment_structure(
        self,
        template: str,
        fragment: str,
    ) -> str:
        """Use a chapter-capable class for chapter fragments in preview only.

        The normal standalone preview template intentionally uses ``article``.
        ``article`` does not define ``\\chapter``, though, and many project
        fragments are meant to be included in a ``report``/``book`` parent.
        When such a fragment is previewed by itself, switch only the temporary
        preview document from ``article`` to ``report``.  The user's source and
        their configured template file remain untouched.
        """
        cleaned = self._strip_comments(fragment)
        if self._BEAMER_FRAGMENT_PATTERN.search(cleaned) is not None:
            return template
        if self._CHAPTER_FRAGMENT_PATTERN.search(cleaned) is None:
            return template

        return self._ARTICLE_CLASS_PATTERN.sub(
            lambda match: (
                "\\documentclass"
                + (match.group("options") or "")
                + "{report}"
            ),
            template,
            count=1,
        )

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
