class LatexBibliographyProcessResultClassifier:
    """Classify bibliography subprocess failures that contain warnings only."""

    _BIBLIOGRAPHY_PHASES = {"bibtex", "biber"}
    _WARNING_MARKERS = (
        "warning--",
        "warn -",
        "warnings:",
        "there was 1 warning",
        "there were ",
    )
    _HARD_ERROR_MARKERS = (
        "error--",
        "error -",
        "fatal -",
        "emergency stop",
        "i couldn't open database file",
        "i couldn't open style file",
        "i found no database files",
        "error message",
        "errors:",
    )

    def is_recoverable_warning_exit(self, phase: str, output: str) -> bool:
        if phase not in self._BIBLIOGRAPHY_PHASES:
            return False
        if not output.strip():
            return False

        lowered_lines = [line.strip().casefold() for line in output.splitlines()]
        if any(
            marker in line
            for line in lowered_lines
            for marker in self._HARD_ERROR_MARKERS
        ):
            return False

        return any(
            marker in line
            for line in lowered_lines
            for marker in self._WARNING_MARKERS
        )
