"""Safe workspace access for TikZ/TeX source files."""

from __future__ import annotations

from pathlib import Path
import hashlib
import os


class TikZWorkspace:
    """Read and atomically write TikZ source inside one configured workspace."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"Workspace is not a directory: {self.root}")

    def resolve_relative(self, relative: str) -> Path:
        """Resolve one bridge-relative path without allowing workspace escape."""
        candidate = (self.root / relative).expanduser().resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path escapes the configured workspace") from exc
        return candidate

    def list_files(self) -> list[str]:
        """List .tikz files and .tex files that actually contain a tikzpicture."""
        ignored_parts = {
            ".git",
            ".idea",
            "__pycache__",
            ".pytest_cache",
            "out",
            "build",
            ".venv",
            "venv",
        }
        files: list[str] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or any(part in ignored_parts for part in path.parts):
                continue
            suffix = path.suffix.lower()
            if suffix not in {".tikz", ".tex"}:
                continue
            if suffix == ".tex":
                try:
                    head = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "\\begin{tikzpicture}" not in head:
                    continue
            files.append(path.relative_to(self.root).as_posix())
        return sorted(files, key=str.casefold)

    def read(self, relative: str) -> str:
        """Read one UTF-8 source file."""
        path = self.resolve_relative(relative)
        if path.suffix.lower() not in {".tikz", ".tex"}:
            raise ValueError("TikZ bridge accepts only .tikz and .tex files")
        return path.read_text(encoding="utf-8")

    def write_atomic(self, relative: str, source: str) -> Path:
        """Replace one source file atomically without leaving Dropbox temp files."""
        path = self.resolve_relative(relative)
        if path.suffix.lower() not in {".tikz", ".tex"}:
            raise ValueError("TikZ bridge accepts only .tikz and .tex files")
        temp = path.with_name(f".{path.name}.ndtikz.tmp")
        temp.write_text(source, encoding="utf-8")
        os.replace(temp, path)
        return path

    def digest(self, relative: str) -> str:
        """Return a stable digest used to suppress bridge echo updates."""
        return hashlib.sha256(self.resolve_relative(relative).read_bytes()).hexdigest()
