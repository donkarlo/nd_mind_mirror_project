"""Normalize YAML indentation while preserving source spelling, comments, and scalar content."""

from __future__ import annotations

import re


class YamlFormatter:
    """Normalize indentation depth without serializing or rewriting YAML values."""

    _BLOCK_SCALAR_TOKEN = re.compile(
        r"(?:^|:\s*|-\s+)([|>][+-]?[1-9]?|[|>][1-9][+-]?)\s*(?:#.*)?$"
    )

    def __init__(self, indent_size: int = 4) -> None:
        self._indent_size = max(int(indent_size), 1)

    def set_indent_size(self, indent_size: int) -> None:
        """Update the number of spaces used for one YAML nesting level."""
        self._indent_size = max(int(indent_size), 1)

    def format(self, source: str) -> str:
        """Return source with normalized leading indentation and unchanged content text."""
        text = str(source)
        if not text:
            return text

        trailing_newline = text.endswith("\n")
        lines = text.splitlines()
        if not lines:
            return text

        result: list[str] = []
        indent_stack: list[int] = [0]
        previous_structural_indent = 0
        previous_structural_seen = False
        block_scalar_header_indent: int | None = None
        block_scalar_content_indent: int | None = None
        block_scalar_target_indent = 0

        for index, raw_line in enumerate(lines):
            expanded = self._expand_leading_tabs(raw_line)
            raw_indent = self._leading_space_count(expanded)
            stripped = expanded[raw_indent:]

            if block_scalar_header_indent is not None:
                if not stripped:
                    result.append("")
                    continue
                if raw_indent > block_scalar_header_indent:
                    content_indent = (
                        block_scalar_content_indent
                        if block_scalar_content_indent is not None
                        else raw_indent
                    )
                    extra_indent = max(raw_indent - content_indent, 0)
                    result.append(
                        " " * (block_scalar_target_indent + extra_indent)
                        + stripped
                    )
                    continue
                block_scalar_header_indent = None
                block_scalar_content_indent = None
                block_scalar_target_indent = 0

            if not stripped:
                result.append("")
                continue

            if stripped.startswith("#"):
                level = self._level_for_comment(
                    raw_indent,
                    indent_stack,
                    previous_structural_indent,
                    previous_structural_seen,
                )
                result.append(" " * (level * self._indent_size) + stripped)
                continue

            if stripped in {"---", "..."}:
                indent_stack = [0]
                previous_structural_indent = 0
                previous_structural_seen = True
                normalized_indent = 0
            else:
                level, indent_stack = self._structural_level(
                    raw_indent,
                    indent_stack,
                    previous_structural_indent,
                    previous_structural_seen,
                )
                normalized_indent = level * self._indent_size
                previous_structural_indent = raw_indent
                previous_structural_seen = True

            result.append(" " * normalized_indent + stripped)

            token = self._block_scalar_token(stripped)
            if token is not None:
                block_scalar_header_indent = raw_indent
                block_scalar_content_indent = self._find_block_scalar_content_indent(
                    lines,
                    index + 1,
                    raw_indent,
                )
                explicit_indent = self._explicit_block_scalar_indent(token)
                block_scalar_target_indent = normalized_indent + (
                    explicit_indent
                    if explicit_indent is not None
                    else self._indent_size
                )

        formatted = "\n".join(result)
        if trailing_newline:
            formatted += "\n"
        return formatted

    def _structural_level(
        self,
        raw_indent: int,
        indent_stack: list[int],
        previous_indent: int,
        previous_seen: bool,
    ) -> tuple[int, list[int]]:
        if not previous_seen:
            return 0, [raw_indent]

        stack = list(indent_stack)
        if raw_indent > previous_indent:
            if raw_indent not in stack:
                stack.append(raw_indent)
                stack.sort()
            return stack.index(raw_indent), stack

        if raw_indent < previous_indent:
            stack = [value for value in stack if value <= raw_indent]
            if not stack or stack[-1] != raw_indent:
                stack.append(raw_indent)
                stack.sort()
            return stack.index(raw_indent), stack

        if raw_indent not in stack:
            stack.append(raw_indent)
            stack.sort()
        return stack.index(raw_indent), stack

    @staticmethod
    def _level_for_comment(
        raw_indent: int,
        indent_stack: list[int],
        previous_indent: int,
        previous_seen: bool,
    ) -> int:
        if not previous_seen:
            return 0
        if raw_indent in indent_stack:
            return indent_stack.index(raw_indent)
        if raw_indent > previous_indent and previous_indent in indent_stack:
            return indent_stack.index(previous_indent) + 1
        lower = [value for value in indent_stack if value <= raw_indent]
        if lower:
            return indent_stack.index(lower[-1])
        return 0

    @classmethod
    def _block_scalar_token(cls, stripped: str) -> str | None:
        content = cls._strip_inline_comment(stripped).rstrip()
        match = cls._BLOCK_SCALAR_TOKEN.search(content)
        return match.group(1) if match is not None else None

    @staticmethod
    def _explicit_block_scalar_indent(token: str) -> int | None:
        match = re.search(r"[1-9]", token)
        return int(match.group(0)) if match is not None else None

    def _find_block_scalar_content_indent(
        self,
        lines: list[str],
        start_index: int,
        header_indent: int,
    ) -> int | None:
        candidates: list[int] = []
        for raw_line in lines[start_index:]:
            expanded = self._expand_leading_tabs(raw_line)
            stripped = expanded.lstrip(" ")
            if not stripped:
                continue
            indent = self._leading_space_count(expanded)
            if indent <= header_indent:
                break
            candidates.append(indent)
        return min(candidates) if candidates else None

    @staticmethod
    def _strip_inline_comment(text: str) -> str:
        quote: str | None = None
        escaped = False
        for index, character in enumerate(text):
            if escaped:
                escaped = False
                continue
            if quote == '"' and character == "\\":
                escaped = True
                continue
            if character in {"'", '"'}:
                if quote is None:
                    quote = character
                elif quote == character:
                    quote = None
                continue
            if character == "#" and quote is None and (
                index == 0 or text[index - 1].isspace()
            ):
                return text[:index]
        return text

    def _expand_leading_tabs(self, line: str) -> str:
        index = 0
        width = 0
        while index < len(line) and line[index] in {" ", "\t"}:
            width += self._indent_size if line[index] == "\t" else 1
            index += 1
        return " " * width + line[index:]

    @staticmethod
    def _leading_space_count(line: str) -> int:
        return len(line) - len(line.lstrip(" "))
