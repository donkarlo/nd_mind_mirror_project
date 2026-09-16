"""Source-preserving model for editable Visual LaTeX tables."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LatexTableModel:
    """Editable tabular data plus source text surrounding the tabular body."""

    before_column_spec: str
    column_spec: str
    suffix: str
    rows: list[list[str]] = field(default_factory=list)
    row_prefixes: list[str] = field(default_factory=list)
    trailing_directives: str = ""
    source_line: int = 0

    @property
    def column_count(self) -> int:
        spans = self._column_spans(self.column_spec)
        row_width = max((len(row) for row in self.rows), default=0)
        return max(len(spans), row_width, 1)

    def normalize(self) -> None:
        columns = self.column_count
        if not self.rows:
            self.rows = [[""] * columns]
        for row in self.rows:
            if len(row) < columns:
                row.extend([""] * (columns - len(row)))
            elif len(row) > columns:
                del row[columns:]
        while len(self.row_prefixes) < len(self.rows):
            self.row_prefixes.append("")
        if len(self.row_prefixes) > len(self.rows):
            del self.row_prefixes[len(self.rows):]

    def insert_row(self, index: int) -> None:
        self.normalize()
        target = max(0, min(int(index), len(self.rows)))
        self.rows.insert(target, [""] * self.column_count)
        self.row_prefixes.insert(target, "")

    def remove_row(self, index: int) -> None:
        self.normalize()
        if len(self.rows) <= 1:
            return
        target = max(0, min(int(index), len(self.rows) - 1))
        self.rows.pop(target)
        if target < len(self.row_prefixes):
            self.row_prefixes.pop(target)

    def insert_column(self, index: int) -> None:
        self.normalize()
        current = self.column_count
        target = max(0, min(int(index), current))
        for row in self.rows:
            row.insert(target, "")
        self.column_spec = self._insert_column_token(self.column_spec, target)

    def remove_column(self, index: int) -> None:
        self.normalize()
        if self.column_count <= 1:
            return
        target = max(0, min(int(index), self.column_count - 1))
        for row in self.rows:
            if target < len(row):
                row.pop(target)
        self.column_spec = self._remove_column_token(self.column_spec, target)

    def serialize(self) -> str:
        self.normalize()
        lines: list[str] = []
        for index, row in enumerate(self.rows):
            prefix = self.row_prefixes[index].strip()
            if prefix:
                lines.extend(part for part in prefix.splitlines() if part.strip())
            lines.append(" & ".join(cell.strip() for cell in row) + r" \\")
        trailing = self.trailing_directives.strip()
        if trailing:
            lines.extend(part for part in trailing.splitlines() if part.strip())
        body = "\n".join(lines)
        return (
            f"{self.before_column_spec}{self.column_spec}}}\n"
            f"{body}\n"
            f"{self.suffix.lstrip()}"
        )

    @classmethod
    def _insert_column_token(cls, spec: str, index: int) -> str:
        spans = cls._column_spans(spec)
        if not spans:
            return spec + "l"
        if index >= len(spans):
            position = spans[-1][1]
            token = "|l" if position < len(spec) and spec[position] == "|" else "l"
        else:
            position = spans[index][0]
            token = "l|" if position > 0 and spec[position - 1] == "|" else "l"
        return spec[:position] + token + spec[position:]

    @classmethod
    def _remove_column_token(cls, spec: str, index: int) -> str:
        spans = cls._column_spans(spec)
        if len(spans) <= 1:
            return spec
        target = max(0, min(int(index), len(spans) - 1))
        start, end = spans[target]
        return spec[:start] + spec[end:]

    @classmethod
    def _column_spans(cls, spec: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        index = 0
        length = len(spec)
        while index < length:
            char = spec[index]
            if char in "lcrXS":
                spans.append((index, index + 1))
                index += 1
                continue
            if char in "pmbD" and index + 1 < length and spec[index + 1] == "{":
                end = cls._balanced_group_end(spec, index + 1)
                if end is not None:
                    if char == "D":
                        cursor = end
                        for _ in range(2):
                            if cursor < length and spec[cursor] == "{":
                                extra = cls._balanced_group_end(spec, cursor)
                                if extra is None:
                                    break
                                cursor = extra
                        end = cursor
                    spans.append((index, end))
                    index = end
                    continue
            index += 1
        return spans

    @staticmethod
    def _balanced_group_end(text: str, start: int) -> int | None:
        if start >= len(text) or text[start] != "{":
            return None
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{" and (index == 0 or text[index - 1] != "\\"):
                depth += 1
            elif char == "}" and (index == 0 or text[index - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    return index + 1
        return None
