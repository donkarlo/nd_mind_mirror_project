import re


class LatexDiagnosticSeverityClassifier:
    """Classify compiler diagnostics without promoting warning-only output to errors."""

    _FILE_NOT_FOUND_PATTERN = re.compile(
        r"\bfile\s+[`'][^`']+[`']\s+not\s+found\b",
        re.IGNORECASE,
    )
    _HARD_ERROR_MARKERS = (
        "undefined control sequence",
        "latex error",
        "fatal error",
        "emergency stop",
        "runaway argument",
        "missing $ inserted",
        "extra }",
        "file ended while scanning use",
        "could not resolve",
        "i couldn't open database file",
        "i couldn't open style file",
        "i found no database files",
        "error--",
        "error -",
    )
    _WARNING_MARKERS = (
        "warning",
        "citation",
        "rerunfilecheck",
    )

    def is_warning_only(self, message: str) -> bool:
        lines = [line.strip() for line in str(message).splitlines() if line.strip()]
        if not lines:
            return False
        if any(self.is_error_line(line) for line in lines):
            return False
        return any(self.is_warning_line(line) for line in lines)

    def kind_for_line(self, line: str) -> str:
        if self.is_error_line(line):
            return "error"
        if self.is_warning_line(line):
            return "warning"
        return "info"

    def is_error_line(self, line: str) -> bool:
        stripped = str(line).strip()
        lowered = stripped.casefold()
        if stripped.startswith("!"):
            return True
        if self._FILE_NOT_FOUND_PATTERN.search(stripped):
            return True
        if any(marker in lowered for marker in self._HARD_ERROR_MARKERS):
            return True
        # Catch otherwise-unclassified compiler errors conservatively while not
        # confusing ordinary warning lines with failures.
        return "error" in lowered and "warning" not in lowered

    def is_warning_line(self, line: str) -> bool:
        lowered = str(line).casefold()
        return any(marker in lowered for marker in self._WARNING_MARKERS)
