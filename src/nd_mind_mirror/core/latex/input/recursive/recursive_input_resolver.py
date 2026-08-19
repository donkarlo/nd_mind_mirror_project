from pathlib import Path
import re

from nd_mind_mirror.core.latex.hierarchy.transformer.heading_hierarchy_transformer import (
    HeadingHierarchyTransformer,
)
from nd_mind_mirror.core.latex.input.base.input_resolver import InputResolver


class RecursiveInputResolver(InputResolver):
    _COMMAND_PATTERN = re.compile(
        r"\\(?P<command>input|include)\s*"
        r"\{(?P<target>[^{}]+)\}"
    )
    _DOCUMENT_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{document\}"
    )
    _DOCUMENT_END_PATTERN = re.compile(
        r"\\end\s*\{document\}"
    )
    _DOCUMENT_CLASS_PATTERN = re.compile(
        r"\\documentclass"
        r"(?:\[[^\]]*\])?"
        r"\{(?P<name>[^}]+)\}"
    )
    _USEPACKAGE_PATTERN = re.compile(
        r"^\s*\\usepackage"
        r"(?:\[(?P<options>[^\]]*)\])?"
        r"\{(?P<packages>[^}]*)\}\s*$"
    )
    _LIBRARY_PATTERN = re.compile(
        r"^\s*\\(?P<command>usetikzlibrary|usegdlibrary)"
        r"\{(?P<items>[^}]*)\}\s*$"
    )
    _CHILD_METADATA_PATTERN = re.compile(
        r"^\s*\\(?:documentclass|title|author|date)"
        r"(?:\[[^\]]*\])?\s*\{"
    )
    _CHILD_STANDALONE_BODY_PATTERN = re.compile(
        r"(?m)^[ \t]*\\(?:"
        r"maketitle|tableofcontents|listoffigures|listoftables"
        r")[ \t]*\n?"
    )
    _BIBLIOGRAPHY_LINE_PATTERN = re.compile(
        r"(?m)^[ \t]*\\(?:"
        r"bibliographystyle\s*\{[^}]*\}|"
        r"bibliography\s*\{[^}]*\}|"
        r"printbibliography(?:\[[^\]]*\])?"
        r")[ \t]*\n?"
    )
    _LITERAL_BEGIN_PATTERN = re.compile(
        r"\\begin\s*\{"
        r"(?P<name>verbatim|Verbatim|lstlisting|minted)"
        r"\}"
    )

    def __init__(self) -> None:
        self._unresolved: list[str] = []
        self._project_root: Path | None = None
        self._master_file: Path | None = None
        self._preamble_additions: list[str] = []
        self._master_document_class = "article"
        self._master_has_bibliography = False
        self._hierarchy = HeadingHierarchyTransformer(
            self._master_document_class
        )

    @property
    def unresolved(self) -> list[str]:
        return list(self._unresolved)

    @property
    def project_root(self) -> Path | None:
        return self._project_root

    @property
    def master_document_class(self) -> str:
        return self._master_document_class

    def resolve(
        self,
        source: str,
        source_path: Path | None,
    ) -> str:
        self._unresolved = []
        self._preamble_additions = []

        if source_path is None:
            self._project_root = None
            self._master_file = None
            return source

        self._master_file = source_path.expanduser().resolve()
        self._project_root = self._find_project_root(
            self._master_file.parent
        )

        self._master_document_class = (
            self._parse_document_class(source)
        )
        self._hierarchy.configure(
            self._master_document_class
        )
        self._master_has_bibliography = bool(
            re.search(
                r"\\(?:bibliography|printbibliography)\b",
                source,
            )
        )

        (
            master_preamble,
            master_body,
            master_suffix,
        ) = self._split_complete_document(source)

        if master_body is None:
            resolved, _ = self._resolve_source(
                source=source,
                containing_file=self._master_file,
                stack={self._master_file},
                context="body",
                inherited_heading=None,
                heading_mapping={},
            )
            return resolved

        expanded_preamble = self._prepare_preamble(
            source=master_preamble,
            containing_file=self._master_file,
        )

        expanded_body, _ = self._resolve_source(
            source=master_body,
            containing_file=self._master_file,
            stack={self._master_file},
            context="body",
            inherited_heading=None,
            heading_mapping={},
        )

        merged_preamble = self._merge_preamble(
            expanded_preamble,
            self._preamble_additions,
        )

        return (
            merged_preamble
            + "\\begin{document}"
            + expanded_body
            + "\\end{document}"
            + master_suffix
        )

    def _resolve_source(
        self,
        source: str,
        containing_file: Path,
        stack: set[Path],
        context: str,
        inherited_heading: str | None,
        heading_mapping: dict[str, str],
    ) -> tuple[str, str | None]:
        output = []
        current_heading = inherited_heading
        literal_environment: str | None = None

        for line in source.splitlines(keepends=True):
            if literal_environment is not None:
                output.append(line)

                if re.search(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                    line,
                ):
                    literal_environment = None

                continue

            literal_match = self._LITERAL_BEGIN_PATTERN.search(
                line
            )

            if literal_match is not None:
                prefix = line[:literal_match.start()]
                literal_part = line[literal_match.start():]

                resolved_prefix, current_heading = (
                    self._resolve_line_code(
                        code=prefix,
                        containing_file=containing_file,
                        stack=stack,
                        context=context,
                        current_heading=current_heading,
                        heading_mapping=heading_mapping,
                    )
                )

                output.append(
                    resolved_prefix + literal_part
                )

                literal_environment = (
                    literal_match.group("name")
                )

                if re.search(
                    rf"\\end\s*\{{{re.escape(literal_environment)}\}}",
                    literal_part,
                ):
                    literal_environment = None

                continue

            code, comment = self._split_comment(line)

            resolved_code, current_heading = (
                self._resolve_line_code(
                    code=code,
                    containing_file=containing_file,
                    stack=stack,
                    context=context,
                    current_heading=current_heading,
                    heading_mapping=heading_mapping,
                )
            )

            output.append(
                resolved_code + comment
            )

        return "".join(output), current_heading

    def _resolve_line_code(
        self,
        code: str,
        containing_file: Path,
        stack: set[Path],
        context: str,
        current_heading: str | None,
        heading_mapping: dict[str, str],
    ) -> tuple[str, str | None]:
        output = []
        cursor = 0

        for match in self._COMMAND_PATTERN.finditer(code):
            prefix = code[cursor:match.start()]
            transformed_prefix = self._transform_headings(
                prefix,
                context,
                heading_mapping,
            )

            output.append(transformed_prefix)

            prefix_heading = self._hierarchy.last_heading(
                transformed_prefix
            )
            if prefix_heading is not None:
                current_heading = prefix_heading

            replacement = self._resolve_input_match(
                match=match,
                containing_file=containing_file,
                stack=stack,
                context=context,
                parent_heading=current_heading,
            )
            output.append(replacement)

            cursor = match.end()

        suffix = code[cursor:]
        transformed_suffix = self._transform_headings(
            suffix,
            context,
            heading_mapping,
        )
        output.append(transformed_suffix)

        suffix_heading = self._hierarchy.last_heading(
            transformed_suffix
        )
        if suffix_heading is not None:
            current_heading = suffix_heading

        return "".join(output), current_heading

    def _resolve_input_match(
        self,
        match: re.Match[str],
        containing_file: Path,
        stack: set[Path],
        context: str,
        parent_heading: str | None,
    ) -> str:
        command = match.group("command")
        target = match.group("target").strip()

        target_path = self._resolve_target(
            containing_file=containing_file,
            target=target,
        )

        if target_path is None:
            diagnostic = (
                f"{containing_file}: "
                f"could not resolve \\{command}"
                f"{{{target}}}"
            )
            if diagnostic not in self._unresolved:
                self._unresolved.append(diagnostic)

            return match.group(0)

        resolved = target_path.resolve()

        if resolved in stack:
            return (
                "\n% nd_mind_mirror: recursive "
                f"{command} skipped: {resolved}\n"
            )

        try:
            nested_source = resolved.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            try:
                nested_source = resolved.read_text(
                    encoding="latin-1"
                )
            except OSError:
                return match.group(0)
        except OSError:
            return match.group(0)

        nested_stack = set(stack)
        nested_stack.add(resolved)

        (
            nested_preamble,
            nested_body,
            nested_suffix,
        ) = self._split_complete_document(
            nested_source
        )

        if nested_body is not None:
            prepared_child_preamble = (
                self._prepare_preamble(
                    source=nested_preamble,
                    containing_file=resolved,
                )
            )
            self._preamble_additions.append(
                prepared_child_preamble
            )

            if context == "preamble":
                return (
                    "\n% nd_mind_mirror: complete child "
                    f"preamble merged from {resolved}\n"
                )

            target_heading = (
                self._hierarchy.target_for_child(
                    parent_heading
                )
            )

            child_mapping = (
                self._hierarchy.build_mapping(
                    nested_body,
                    target_heading,
                )
            )

            cleaned_body = self._sanitize_child_body(
                nested_body
            )

            expanded_child_body, _ = (
                self._resolve_source(
                    source=cleaned_body,
                    containing_file=resolved,
                    stack=nested_stack,
                    context="body",
                    inherited_heading=parent_heading,
                    heading_mapping=child_mapping,
                )
            )

            return self._wrap_inserted_body(
                command=command,
                resolved=resolved,
                content=expanded_child_body,
                target_heading=target_heading,
                heading_mapping=child_mapping,
            )

        expanded, _ = self._resolve_source(
            source=nested_source,
            containing_file=resolved,
            stack=nested_stack,
            context=context,
            inherited_heading=parent_heading,
            heading_mapping={},
        )

        return self._wrap_inserted_body(
            command=command,
            resolved=resolved,
            content=expanded,
            target_heading=None,
            heading_mapping={},
        )

    def _transform_headings(
        self,
        source: str,
        context: str,
        heading_mapping: dict[str, str],
    ) -> str:
        if (
            context != "body"
            or not heading_mapping
        ):
            return source

        return self._hierarchy.transform(
            source,
            heading_mapping,
        )

    def _sanitize_child_body(
        self,
        body: str,
    ) -> str:
        cleaned = self._CHILD_STANDALONE_BODY_PATTERN.sub(
            "",
            body,
        )

        if self._master_has_bibliography:
            cleaned = self._BIBLIOGRAPHY_LINE_PATTERN.sub(
                "",
                cleaned,
            )

        return cleaned

    def _wrap_inserted_body(
        self,
        command: str,
        resolved: Path,
        content: str,
        target_heading: str | None,
        heading_mapping: dict[str, str],
    ) -> str:
        hierarchy_note = ""

        if heading_mapping:
            mapping_text = ", ".join(
                f"{source}->{destination}"
                for source, destination
                in sorted(
                    heading_mapping.items(),
                    key=lambda item: (
                        self._canonical_heading_index(
                            item[0]
                        )
                    ),
                )
            )
            hierarchy_note = (
                f" hierarchy target={target_heading}; "
                f"{mapping_text}"
            )

        start_marker = (
            "\n% ---- nd_mind_mirror "
            f"{command} begin: {resolved};"
            f"{hierarchy_note} ----\n"
        )
        end_marker = (
            "\n% ---- nd_mind_mirror "
            f"{command} end: {resolved} ----\n"
        )

        if command == "include":
            return (
                "\\clearpage\n"
                + start_marker
                + content
                + end_marker
                + "\\clearpage\n"
            )

        return (
            start_marker
            + content
            + end_marker
        )

    def _split_complete_document(
        self,
        source: str,
    ) -> tuple[str, str | None, str]:
        begin_match = self._DOCUMENT_BEGIN_PATTERN.search(
            source
        )

        if begin_match is None:
            return source, None, ""

        end_matches = list(
            self._DOCUMENT_END_PATTERN.finditer(source)
        )

        if not end_matches:
            return source, None, ""

        end_match = end_matches[-1]

        if end_match.start() < begin_match.end():
            return source, None, ""

        preamble = source[:begin_match.start()]
        body = source[
            begin_match.end():end_match.start()
        ]
        suffix = source[end_match.end():]

        return preamble, body, suffix

    def _parse_document_class(
        self,
        source: str,
    ) -> str:
        match = self._DOCUMENT_CLASS_PATTERN.search(
            source
        )

        if match is None:
            return "article"

        name = match.group("name").strip()

        if "," in name:
            name = name.split(",", 1)[0].strip()

        return name or "article"

    def _prepare_preamble(
        self,
        source: str,
        containing_file: Path,
    ) -> str:
        output = []

        for line in source.splitlines(
            keepends=True
        ):
            code, comment = self._split_comment(
                line
            )

            rewritten = self._rewrite_preamble_inputs(
                code=code,
                containing_file=containing_file,
            )

            output.append(
                rewritten + comment
            )

        return "".join(output)

    def _rewrite_preamble_inputs(
        self,
        code: str,
        containing_file: Path,
    ) -> str:
        def replace(
            match: re.Match[str],
        ) -> str:
            command = match.group("command")
            target = match.group("target").strip()

            target_path = self._resolve_target(
                containing_file=containing_file,
                target=target,
            )

            if target_path is None:
                diagnostic = (
                    f"{containing_file}: "
                    f"could not resolve \\{command}"
                    f"{{{target}}}"
                )

                if diagnostic not in self._unresolved:
                    self._unresolved.append(
                        diagnostic
                    )

                return match.group(0)

            resolved = target_path.resolve()

            return (
                "\\"
                + command
                + "{"
                + resolved.as_posix()
                + "}"
            )

        return self._COMMAND_PATTERN.sub(
            replace,
            code,
        )

    def _merge_preamble(
        self,
        master_preamble: str,
        additions: list[str],
    ) -> str:
        if not additions:
            return master_preamble

        master_lines = (
            master_preamble.splitlines()
        )

        loaded_packages = set()
        loaded_libraries = {
            "usetikzlibrary": set(),
            "usegdlibrary": set(),
        }
        loaded_atomic_lines = {
            self._normalize_line(line)
            for line in master_lines
            if self._normalize_line(line)
        }

        for line in master_lines:
            package_match = (
                self._USEPACKAGE_PATTERN.match(
                    line
                )
            )

            if package_match:
                loaded_packages.update(
                    self._split_csv(
                        package_match.group(
                            "packages"
                        )
                    )
                )

            library_match = (
                self._LIBRARY_PATTERN.match(
                    line
                )
            )

            if library_match:
                loaded_libraries[
                    library_match.group(
                        "command"
                    )
                ].update(
                    self._split_csv(
                        library_match.group(
                            "items"
                        )
                    )
                )

        unique_blocks = []
        seen_blocks = set()

        for addition in additions:
            sanitized = (
                self._sanitize_preamble_metadata(
                    addition
                )
            )
            normalized_block = (
                self._normalize_block(
                    sanitized
                )
            )

            if (
                not normalized_block
                or normalized_block
                in seen_blocks
            ):
                continue

            seen_blocks.add(
                normalized_block
            )
            unique_blocks.append(
                sanitized
            )

        additions_to_append = []

        for block in unique_blocks:
            for line in block.splitlines():
                stripped = line.strip()

                if not stripped:
                    additions_to_append.append(
                        ""
                    )
                    continue

                if stripped.startswith("%"):
                    additions_to_append.append(
                        line
                    )
                    continue

                package_match = (
                    self._USEPACKAGE_PATTERN.match(
                        line
                    )
                )

                if package_match:
                    packages = self._split_csv(
                        package_match.group(
                            "packages"
                        )
                    )
                    missing = [
                        package
                        for package in packages
                        if package
                        not in loaded_packages
                    ]

                    if not missing:
                        continue

                    options = package_match.group(
                        "options"
                    )
                    option_text = (
                        f"[{options}]"
                        if options is not None
                        else ""
                    )
                    new_line = (
                        "\\usepackage"
                        f"{option_text}"
                        "{"
                        + ",".join(missing)
                        + "}"
                    )

                    loaded_packages.update(
                        missing
                    )
                    additions_to_append.append(
                        new_line
                    )
                    loaded_atomic_lines.add(
                        self._normalize_line(
                            new_line
                        )
                    )
                    continue

                library_match = (
                    self._LIBRARY_PATTERN.match(
                        line
                    )
                )

                if library_match:
                    command = library_match.group(
                        "command"
                    )
                    items = self._split_csv(
                        library_match.group(
                            "items"
                        )
                    )
                    missing = [
                        item
                        for item in items
                        if item
                        not in loaded_libraries[
                            command
                        ]
                    ]

                    if not missing:
                        continue

                    new_line = (
                        "\\"
                        + command
                        + "{"
                        + ",".join(missing)
                        + "}"
                    )
                    loaded_libraries[
                        command
                    ].update(
                        missing
                    )
                    additions_to_append.append(
                        new_line
                    )
                    loaded_atomic_lines.add(
                        self._normalize_line(
                            new_line
                        )
                    )
                    continue

                normalized = (
                    self._normalize_line(
                        line
                    )
                )

                is_atomic_input = bool(
                    re.match(
                        r"^\\(?:input|include)"
                        r"\s*\{[^{}]+\}\s*$",
                        stripped,
                    )
                )

                if (
                    is_atomic_input
                    and normalized
                    in loaded_atomic_lines
                ):
                    continue

                additions_to_append.append(
                    line
                )

                if (
                    is_atomic_input
                    and normalized
                ):
                    loaded_atomic_lines.add(
                        normalized
                    )

        while (
            additions_to_append
            and not additions_to_append[-1]
        ):
            additions_to_append.pop()

        if not additions_to_append:
            return master_preamble

        result = master_preamble.rstrip()
        result += (
            "\n"
            "% ---- nd_mind_mirror merged child preambles ----\n"
        )
        result += "\n".join(
            additions_to_append
        )
        result += "\n"

        return result

    def _sanitize_preamble_metadata(
        self,
        source: str,
    ) -> str:
        output = []

        for line in source.splitlines():
            stripped = line.strip()

            if not stripped:
                output.append("")
                continue

            if self._CHILD_METADATA_PATTERN.match(
                line
            ):
                continue

            if stripped in (
                "\\maketitle",
                "\\begin{document}",
                "\\end{document}",
            ):
                continue

            output.append(
                line
            )

        return "\n".join(output)

    def _normalize_block(
        self,
        source: str,
    ) -> str:
        normalized_lines = []

        for line in source.splitlines():
            code, _ = self._split_comment(
                line
            )
            normalized = re.sub(
                r"\s+",
                "",
                code,
            )

            if normalized:
                normalized_lines.append(
                    normalized
                )

        return "\n".join(
            normalized_lines
        )

    def _normalize_line(
        self,
        line: str,
    ) -> str:
        code, _ = self._split_comment(line)

        return re.sub(
            r"\s+",
            "",
            code,
        )

    def _split_csv(
        self,
        value: str,
    ) -> list[str]:
        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    def _split_comment(
        self,
        line: str,
    ) -> tuple[str, str]:
        index = 0

        while index < len(line):
            if line[index] == "%":
                backslashes = 0
                cursor = index - 1

                while (
                    cursor >= 0
                    and line[cursor] == "\\"
                ):
                    backslashes += 1
                    cursor -= 1

                if backslashes % 2 == 0:
                    return (
                        line[:index],
                        line[index:],
                    )

            index += 1

        return line, ""

    def _resolve_target(
        self,
        containing_file: Path,
        target: str,
    ) -> Path | None:
        target_path = Path(target).expanduser()

        if target_path.is_absolute():
            return self._first_existing(
                self._with_tex_variants(
                    target_path
                )
            )

        bases = [
            containing_file.parent,
        ]

        if self._master_file is not None:
            bases.append(
                self._master_file.parent
            )

        for ancestor in containing_file.parent.parents:
            bases.append(ancestor)

            if (
                self._project_root is not None
                and ancestor == self._project_root
            ):
                break

        unique_bases = []
        seen = set()

        for base in bases:
            resolved_base = base.resolve()

            if resolved_base not in seen:
                seen.add(resolved_base)
                unique_bases.append(resolved_base)

        candidates = []

        for base in unique_bases:
            candidates.extend(
                self._with_tex_variants(
                    base / target_path
                )
            )

        direct = self._first_existing(
            candidates
        )

        if direct is not None:
            return direct

        if self._project_root is None:
            return None

        suffix_variants = (
            self._relative_suffix_variants(
                target_path
            )
        )

        matches = []

        try:
            for candidate in self._project_root.rglob(
                "*.tex"
            ):
                if not candidate.is_file():
                    continue

                candidate_posix = (
                    candidate.resolve().as_posix()
                )

                for suffix in suffix_variants:
                    suffix_posix = (
                        suffix.as_posix().lstrip("./")
                    )

                    if candidate_posix.endswith(
                        suffix_posix
                    ):
                        matches.append(candidate)
                        break
        except OSError:
            return None

        if not matches:
            return None

        return sorted(
            set(matches),
            key=lambda item: (
                len(item.parts),
                len(str(item)),
            ),
        )[0]

    def _with_tex_variants(
        self,
        path: Path,
    ) -> list[Path]:
        variants = [path]

        if path.suffix == "":
            variants.append(
                path.with_suffix(".tex")
            )

            if path.name:
                variants.append(
                    path / f"{path.name}.tex"
                )

        return variants

    def _relative_suffix_variants(
        self,
        target: Path,
    ) -> list[Path]:
        if target.suffix:
            return [target]

        return [
            target.with_suffix(".tex"),
            target / f"{target.name}.tex",
        ]

    def _first_existing(
        self,
        candidates: list[Path],
    ) -> Path | None:
        for candidate in candidates:
            try:
                if candidate.is_file():
                    return candidate
            except OSError:
                continue

        return None

    def _find_project_root(
        self,
        start: Path,
    ) -> Path:
        indicators = (
            ".git",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
            ".hg",
        )

        for candidate in (
            start,
            *start.parents,
        ):
            for indicator in indicators:
                if (
                    candidate / indicator
                ).exists():
                    return candidate

        return start

    def _canonical_heading_index(
        self,
        heading: str,
    ) -> int:
        order = (
            "part",
            "chapter",
            "section",
            "subsection",
            "subsubsection",
            "paragraph",
            "subparagraph",
        )

        try:
            return order.index(heading)
        except ValueError:
            return len(order)
