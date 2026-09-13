"""Create and locate source-backed TikZ input files used by LaTeX documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class TikZDocument:
    """Describe one editable TikZ child source and its parent LaTeX reference."""

    source_path: Path
    tex_reference: str


@dataclass(frozen=True)
class TikZReference:
    """Describe one existing TikZ input reference in a parent LaTeX source."""

    source_path: Path
    tex_reference: str
    start: int
    end: int


class TikZDocumentManager:
    """Create collision-safe TikZ child files and resolve TikZ input references."""

    _INPUT = re.compile(
        r"\\(?P<command>input|include)\s*\{(?P<path>[^}]+)\}",
        re.MULTILINE,
    )
    _TIKZ_MARKER = r"\begin{tikzpicture}"

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).expanduser().resolve()

    def create_for_source(self, source_path: str | Path) -> TikZDocument:
        """Create the next tikz_N.tex beside a parent source without overwriting files."""
        parent_source = Path(source_path).expanduser().resolve()
        directory = parent_source.parent
        directory.mkdir(parents=True, exist_ok=True)

        counter = 1
        while True:
            name = "tikz.tex" if counter == 1 else f"tikz_{counter}.tex"
            candidate = directory / name
            try:
                with candidate.open("x", encoding="utf-8") as handle:
                    handle.write(
                        "\\begin{tikzpicture}\n"
                        "\n"
                        "\\end{tikzpicture}\n"
                    )
                return TikZDocument(candidate, rf"\input{{{name}}}")
            except FileExistsError:
                counter += 1

    def find_reference(
        self,
        source: str,
        source_path: str | Path,
        position: int,
    ) -> TikZReference | None:
        """Return the TikZ input represented by a source position or its line."""
        parent_source = Path(source_path).expanduser().resolve()
        position = max(0, min(int(position), len(source)))
        matches = list(self._INPUT.finditer(source))
        if not matches:
            return None

        line_start = source.rfind("\n", 0, position) + 1
        line_end = source.find("\n", position)
        if line_end < 0:
            line_end = len(source)

        candidates = [
            match
            for match in matches
            if match.start() <= position <= match.end()
            or (match.start() >= line_start and match.end() <= line_end)
        ]
        for match in candidates:
            target = self._resolve_input_path(match.group("path"), parent_source)
            if target is None or not self.is_tikz_file(target):
                continue
            return TikZReference(
                source_path=target,
                tex_reference=match.group(0),
                start=match.start(),
                end=match.end(),
            )
        return None

    def workspace_relative_path(self, path: str | Path) -> str:
        """Return a validated workspace-relative path for bridge messages."""
        resolved = Path(path).expanduser().resolve()
        return resolved.relative_to(self._workspace_root).as_posix()

    @classmethod
    def is_tikz_file(cls, path: str | Path) -> bool:
        """Return whether a file contains a TikZ picture environment."""
        candidate = Path(path)
        if not candidate.is_file() or candidate.suffix.lower() not in {".tex", ".tikz"}:
            return False
        try:
            return cls._TIKZ_MARKER in candidate.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            return False

    def _resolve_input_path(self, raw_path: str, parent_source: Path) -> Path | None:
        """Resolve relative, workspace-rooted, and real absolute LaTeX input paths."""
        token = str(raw_path).strip()
        if not token or token.startswith("\\"):
            return None

        raw = Path(token).expanduser()
        candidates: list[Path] = []
        if raw.is_absolute():
            candidates.append(self._workspace_root / token.lstrip("/\\"))
            candidates.append(raw)
        else:
            candidates.append(parent_source.parent / raw)

        expanded: list[Path] = []
        for candidate in candidates:
            expanded.append(candidate)
            if candidate.suffix == "":
                expanded.append(candidate.with_suffix(".tex"))

        for candidate in expanded:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved.is_file():
                return resolved
        return None
