from nd_mind_mirror.core.render.latex.diagnostic.latex_diagnostic_severity_classifier import (
    LatexDiagnosticSeverityClassifier,
)


class LatexCompilerDiagnosticExtractor:
    """Keep actionable LaTeX errors together with their nearby compiler context."""

    def __init__(self) -> None:
        self._severity_classifier = LatexDiagnosticSeverityClassifier()

    def extract(self, output: str) -> str:
        if not output:
            return "LaTeX compilation failed without diagnostic output."

        lines = output.splitlines()
        error_indices = [
            index
            for index, line in enumerate(lines)
            if self._severity_classifier.is_error_line(line)
        ]

        if error_indices:
            selected: list[str] = []
            seen: set[int] = set()
            for index in error_indices:
                self._append_error_context(lines, index, selected, seen)

            for index, line in enumerate(lines):
                if (
                    index in seen
                    or not self._severity_classifier.is_warning_line(line)
                ):
                    continue
                stripped = line.strip()
                if stripped:
                    selected.append(stripped)

            return "\n".join(selected[:40])

        warnings = [
            line.strip()
            for line in lines
            if line.strip() and self._severity_classifier.is_warning_line(line)
        ]
        if warnings:
            return "\n".join(warnings[-24:])

        non_empty = [line for line in lines if line.strip()]
        return "\n".join(non_empty[-30:])

    @staticmethod
    def _append_error_context(
        lines: list[str],
        index: int,
        selected: list[str],
        seen: set[int],
    ) -> None:
        # LaTeX normally prints the failing command on the one or two lines
        # immediately after the error header (for example ``l.254 \\foo``).
        for candidate in range(index, min(index + 4, len(lines))):
            if candidate in seen:
                continue
            text = lines[candidate].rstrip()
            if not text.strip():
                continue
            selected.append(text.strip() if candidate == index else text)
            seen.add(candidate)
