"""Search text recursively in workspace files without blocking the Qt GUI thread."""

from pathlib import Path
import os
import re

from PySide6.QtCore import QThread, Signal

from nd_mind_mirror.core.search.ignore.search_ignore_matcher import SearchIgnoreMatcher


class TextFileSearchThread(QThread):
    """Find every textual occurrence and retain LaTeX structural context."""

    results_ready = Signal(int, object, bool)

    _YIELD_EVERY_FILES = 24
    _YIELD_EVERY_LINES = 512
    _TEXT_SUFFIXES = {
        ".tex", ".tikz", ".sty", ".cls", ".bib",
        ".txt", ".md", ".markdown", ".rst",
        ".py", ".pyi", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf",
        ".sh", ".bash", ".zsh", ".fish",
        ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hxx",
        ".java", ".kt", ".kts", ".swift", ".m", ".mm",
        ".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html", ".htm", ".xml",
        ".qml", ".gradle", ".groovy", ".cmake", ".ipynb", ".svg",
        ".proto", ".dart", ".scala", ".vue", ".svelte", ".log",
        ".sql", ".lua", ".go", ".rs", ".rb", ".php", ".pl", ".pm", ".r", ".jl",
        ".csv", ".tsv", ".properties", ".env",
    }
    _TEXT_FILENAMES = {
        "makefile", "dockerfile", "readme", "license", "copying", "authors", "changelog",
        ".gitignore", ".gitattributes", ".editorconfig",
    }
    _LATEX_LEVELS = (
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    )
    _LATEX_HEADING_RE = re.compile(
        r"\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)"
        r"\*?\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}"
    )

    def __init__(
        self,
        generation: int,
        root_path: str | Path,
        query: str,
        max_results: int,
        ignore_file_path: str | Path | None,
        parent=None,
    ) -> None:
        """Initialize one cancellable recursive text-search job."""
        super().__init__(parent)
        self._generation = int(generation)
        self._root_path = Path(root_path).expanduser().resolve()
        self._query = str(query)
        self._needle = self._query.casefold()
        self._max_results = max(int(max_results), 1)
        self._ignore_file_path = (
            Path(ignore_file_path).expanduser().resolve()
            if ignore_file_path is not None
            else None
        )

    def run(self) -> None:
        """Scan eligible files and emit grouped text occurrences."""
        if not self._needle:
            self.results_ready.emit(self._generation, [], False)
            return

        matcher = SearchIgnoreMatcher.from_file(self._ignore_file_path)
        file_results: list[dict] = []
        occurrence_count = 0
        truncated = False
        visited_files = 0

        try:
            walker = os.walk(
                self._root_path,
                topdown=True,
                followlinks=False,
                onerror=lambda error: None,
            )

            for current_root, directories, files in walker:
                if self.isInterruptionRequested():
                    return

                current_path = Path(current_root)
                directories[:] = [
                    name
                    for name in directories
                    if not matcher.is_ignored(
                        current_path / name,
                        self._root_path,
                        is_directory=True,
                    )
                ]

                for name in files:
                    if self.isInterruptionRequested():
                        return

                    path = current_path / name
                    if matcher.is_ignored(
                        path,
                        self._root_path,
                        is_directory=False,
                    ):
                        continue
                    if not self._is_text_candidate(path):
                        continue

                    remaining = self._max_results - occurrence_count
                    if remaining <= 0:
                        truncated = True
                        break

                    occurrences = self._search_file(path, remaining)
                    if occurrences:
                        file_results.append(
                            {
                                "path": str(path),
                                "relative_path": self._relative_path(path),
                                "occurrences": occurrences,
                            }
                        )
                        occurrence_count += len(occurrences)

                    visited_files += 1
                    if visited_files % self._YIELD_EVERY_FILES == 0:
                        QThread.msleep(1)

                    if occurrence_count >= self._max_results:
                        truncated = True
                        break

                if truncated or self.isInterruptionRequested():
                    break
        except OSError:
            file_results = []
            truncated = False

        if self.isInterruptionRequested():
            return

        self.results_ready.emit(
            self._generation,
            file_results,
            truncated,
        )

    def _search_file(self, path: Path, remaining: int) -> list[dict]:
        """Find every query occurrence in one text file."""
        occurrences: list[dict] = []
        latex_structure: list[tuple[str, str, int]] = []
        is_latex = path.suffix.casefold() in {".tex", ".tikz", ".sty", ".cls"}

        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if self.isInterruptionRequested():
                        return []

                    if is_latex:
                        latex_structure = self._updated_latex_structure(
                            latex_structure,
                            line,
                            line_number,
                        )

                    folded = line.casefold()
                    search_from = 0
                    while len(occurrences) < remaining:
                        column = folded.find(self._needle, search_from)
                        if column < 0:
                            break
                        occurrences.append(
                            {
                                "line": line_number,
                                "column": column + 1,
                                "snippet": line.rstrip("\r\n").strip(),
                                "structure": tuple(latex_structure),
                            }
                        )
                        search_from = column + max(len(self._needle), 1)

                    if len(occurrences) >= remaining:
                        break

                    if line_number % self._YIELD_EVERY_LINES == 0:
                        QThread.msleep(1)
        except (OSError, UnicodeError):
            return []

        return occurrences

    def _updated_latex_structure(
        self,
        current: list[tuple[str, str, int]],
        line: str,
        line_number: int,
    ) -> list[tuple[str, str, int]]:
        """Update the active LaTeX heading hierarchy for one source line."""
        source = self._latex_without_comment(line)
        match = self._LATEX_HEADING_RE.search(source)
        if match is None:
            return current

        kind = match.group(1)
        title = " ".join(match.group(2).split()) or f"{kind} at line {line_number}"
        level = self._LATEX_LEVELS.index(kind)
        kept = [
            entry
            for entry in current
            if self._LATEX_LEVELS.index(entry[0]) < level
        ]
        kept.append((kind, title, line_number))
        return kept

    @staticmethod
    def _latex_without_comment(line: str) -> str:
        """Strip an unescaped LaTeX comment from one source line."""
        escaped = False
        for index, character in enumerate(line):
            if character == "\\":
                escaped = not escaped
                continue
            if character == "%" and not escaped:
                return line[:index]
            escaped = False
        return line

    def _relative_path(self, path: Path) -> str:
        """Return a display path relative to the active search root."""
        try:
            return path.relative_to(self._root_path).as_posix()
        except ValueError:
            return path.name

    @classmethod
    def _is_text_candidate(cls, path: Path) -> bool:
        """Return whether a path is eligible for text-content scanning."""
        name = path.name.casefold()
        if path.suffix.casefold() in cls._TEXT_SUFFIXES:
            return True
        if name in cls._TEXT_FILENAMES:
            return True
        if not path.suffix and name.startswith("."):
            return True
        return False
