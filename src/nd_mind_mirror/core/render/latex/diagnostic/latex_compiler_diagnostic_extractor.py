class LatexCompilerDiagnosticExtractor:
    """Keep actionable LaTeX errors together with their nearby compiler context."""

    _ERROR_MARKERS = (
        "undefined control sequence",
        "latex error",
        "emergency stop",
        "fatal error",
        "runaway argument",
        "missing $ inserted",
        "extra }",
        "file ended while scanning use",
    )
    _WARNING_MARKERS = (
        "citation",
        "warning--",
        "package",
    )

    def extract(self, output: str) -> str:
        if not output:
            return "LaTeX compilation failed without diagnostic output."

        lines = output.splitlines()
        error_indices = [
            index
            for index, line in enumerate(lines)
            if self._is_error_line(line)
        ]

        if error_indices:
            selected: list[str] = []
            seen: set[int] = set()
            for index in error_indices:
                self._append_error_context(lines, index, selected, seen)

            for index, line in enumerate(lines):
                if index in seen or not self._is_warning_line(line):
                    continue
                stripped = line.strip()
                if stripped:
                    selected.append(stripped)

            return "\n".join(selected[:40])

        warnings = [
            line.strip()
            for line in lines
            if line.strip() and self._is_warning_line(line)
        ]
        if warnings:
            return "\n".join(warnings[-24:])

        non_empty = [line for line in lines if line.strip()]
        return "\n".join(non_empty[-30:])

    def _append_error_context(
        self,
        lines: list[str],
        index: int,
        selected: list[str],
        seen: set[int],
    ) -> None:
        # LaTeX normally prints the failing command on the one or two lines
        # immediately after the error header (for example ``l.254 \foo``).
        for candidate in range(index, min(index + 4, len(lines))):
            if candidate in seen:
                continue
            text = lines[candidate].rstrip()
            if not text.strip():
                continue
            selected.append(text.strip() if candidate == index else text)
            seen.add(candidate)

    def _is_error_line(self, line: str) -> bool:
        stripped = line.strip()
        lowered = stripped.casefold()
        if stripped.startswith("!"):
            return True
        if any(marker in lowered for marker in self._ERROR_MARKERS):
            return True
        return "preview.tex:" in lowered and "warning" not in lowered

    def _is_warning_line(self, line: str) -> bool:
        lowered = line.casefold()
        return any(marker in lowered for marker in self._WARNING_MARKERS)
