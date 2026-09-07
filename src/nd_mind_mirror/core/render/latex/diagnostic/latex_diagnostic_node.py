from pathlib import Path


class LatexDiagnosticNode:
    """One visible node in the Preview LaTeX diagnostic tree."""

    def __init__(
        self,
        title: str,
        detail: str = "",
        kind: str = "info",
        source_path: str | Path | None = None,
        line: int = 1,
        column: int = 1,
        target_path: str | Path | None = None,
    ) -> None:
        self.title = str(title)
        self.detail = str(detail)
        self.kind = str(kind)
        self.source_path = self._path_or_none(source_path)
        self.line = max(int(line), 1)
        self.column = max(int(column), 1)
        self.target_path = self._path_or_none(target_path)
        self.children: list[LatexDiagnosticNode] = []

    @staticmethod
    def _path_or_none(value: str | Path | None) -> Path | None:
        if value in (None, ""):
            return None
        return Path(value).expanduser().resolve(strict=False)

    def add_child(self, child: "LatexDiagnosticNode") -> "LatexDiagnosticNode":
        self.children.append(child)
        return child

    def mark_error(self, detail: str = "") -> None:
        self.kind = "error"
        if detail:
            self.detail = detail
