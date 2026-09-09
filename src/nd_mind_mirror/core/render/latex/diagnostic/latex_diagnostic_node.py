from pathlib import Path

from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_severity_classifier import (
    LatexDiagnosticSeverityClassifier,
)


class LatexDiagnosticNode:
    """One visible node in the Preview LaTeX diagnostic tree."""

    _severity_classifier = LatexDiagnosticSeverityClassifier()

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
        normalized_title, normalized_kind = self._normalized_title_and_kind(
            title=str(title),
            detail=str(detail),
            kind=str(kind),
        )
        self.title = normalized_title
        self.detail = str(detail)
        self.kind = normalized_kind
        self.source_path = self._path_or_none(source_path)
        self.line = max(int(line), 1)
        self.column = max(int(column), 1)
        self.target_path = self._path_or_none(target_path)
        self.children: list[LatexDiagnosticNode] = []

    @classmethod
    def _normalized_title_and_kind(
        cls,
        *,
        title: str,
        detail: str,
        kind: str,
    ) -> tuple[str, str]:
        if (
            title == "Compilation error"
            and kind == "error"
            and cls._severity_classifier.is_warning_only(detail)
        ):
            return "Compilation warnings", "warning"

        if kind == "info" and cls._severity_classifier.is_warning_line(title):
            return title, "warning"

        return title, kind

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
