"""Parse common tabular/table LaTeX into an editable grid model."""

from __future__ import annotations

import re

from .latex_table_model import LatexTableModel


class LatexTableParser:
    """Recognize safe, rectangular tabular content without touching hard cases."""

    _BEGIN = re.compile(r"\\begin\{tabular\}")
    _END = r"\end{tabular}"
    _ROW_DIRECTIVE = re.compile(
        r"^\s*(\\(?:hline|toprule|midrule|bottomrule|cline\{[^}]+\}))\s*",
        re.DOTALL,
    )

    def parse(self, raw: str, source_line: int = 0) -> LatexTableModel | None:
        source = str(raw)
        begin = self._BEGIN.search(source)
        if begin is None:
            return None
        if "\\begin{tabular}" in source[begin.end():]:
            return None
        if "\\multicolumn" in source or "\\multirow" in source:
            return None

        cursor = begin.end()
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor < len(source) and source[cursor] == "[":
            optional_end = self._balanced_end(source, cursor, "[", "]")
            if optional_end is None:
                return None
            cursor = optional_end
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
        if cursor >= len(source) or source[cursor] != "{":
            return None

        spec_end = self._balanced_end(source, cursor, "{", "}")
        if spec_end is None:
            return None
        column_spec = source[cursor + 1 : spec_end - 1]
        if "*{" in column_spec:
            return None

        end_start = source.find(self._END, spec_end)
        if end_start < 0:
            return None
        body = source[spec_end:end_start]
        chunks = self._split_rows(body)
        rows: list[list[str]] = []
        prefixes: list[str] = []
        pending_directives: list[str] = []
        trailing_directives: list[str] = []

        for raw_chunk in chunks:
            chunk = raw_chunk.strip()
            if not chunk:
                continue
            directives: list[str] = []
            while True:
                match = self._ROW_DIRECTIVE.match(chunk)
                if match is None:
                    break
                directives.append(match.group(1))
                chunk = chunk[match.end():]
            if not chunk.strip():
                pending_directives.extend(directives)
                continue
            prefix = "\n".join(pending_directives + directives)
            pending_directives.clear()
            cells = [cell.strip() for cell in self._split_cells(chunk)]
            rows.append(cells)
            prefixes.append(prefix)

        trailing_directives.extend(pending_directives)
        if not rows:
            return None

        model = LatexTableModel(
            before_column_spec=source[: cursor + 1],
            column_spec=column_spec,
            suffix=source[end_start:],
            rows=rows,
            row_prefixes=prefixes,
            trailing_directives="\n".join(trailing_directives),
            source_line=max(int(source_line), 0),
        )
        model.normalize()
        return model

    def _split_rows(self, body: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        depth = 0
        index = 0
        while index < len(body):
            char = body[index]
            if char == "{" and not self._escaped(body, index):
                depth += 1
            elif char == "}" and not self._escaped(body, index):
                depth = max(depth - 1, 0)
            elif depth == 0 and body.startswith(r"\\", index):
                chunks.append(body[start:index])
                index += 2
                if index < len(body) and body[index] == "*":
                    index += 1
                if index < len(body) and body[index] == "[":
                    optional_end = self._balanced_end(body, index, "[", "]")
                    if optional_end is not None:
                        index = optional_end
                start = index
                continue
            index += 1
        chunks.append(body[start:])
        return chunks

    def _split_cells(self, row: str) -> list[str]:
        cells: list[str] = []
        start = 0
        depth = 0
        for index, char in enumerate(row):
            if char == "{" and not self._escaped(row, index):
                depth += 1
            elif char == "}" and not self._escaped(row, index):
                depth = max(depth - 1, 0)
            elif char == "&" and depth == 0 and not self._escaped(row, index):
                cells.append(row[start:index])
                start = index + 1
        cells.append(row[start:])
        return cells

    @staticmethod
    def _escaped(text: str, index: int) -> bool:
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        return backslashes % 2 == 1

    @staticmethod
    def _balanced_end(
        text: str,
        start: int,
        opening: str,
        closing: str,
    ) -> int | None:
        if start >= len(text) or text[start] != opening:
            return None
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == opening and not LatexTableParser._escaped(text, index):
                depth += 1
            elif char == closing and not LatexTableParser._escaped(text, index):
                depth -= 1
                if depth == 0:
                    return index + 1
        return None
