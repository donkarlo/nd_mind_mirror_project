from __future__ import annotations

from pathlib import Path
import hashlib
import os


class Workspace:
    def __init__(self, root: str | Path, extensions: tuple[str, ...] = (".tikz", ".tex")) -> None:
        self.root = Path(root).expanduser().resolve()
        self.extensions = tuple(ext.lower() for ext in extensions)
        if not self.root.is_dir():
            raise ValueError(f"Workspace is not a directory: {self.root}")

    def resolve_relative(self, relative: str) -> Path:
        candidate = (self.root / relative).expanduser().resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Path escapes the configured workspace") from exc
        return candidate

    def list_files(self) -> list[str]:
        files: list[str] = []
        ignored_parts = {".git", ".idea", "__pycache__", ".pytest_cache", "out"}
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in self.extensions:
                continue
            relative = path.relative_to(self.root)
            if any(part in ignored_parts for part in relative.parts):
                continue
            files.append(relative.as_posix())
        return sorted(files, key=str.casefold)

    def read(self, relative: str) -> str:
        path = self.resolve_relative(relative)
        return path.read_text(encoding="utf-8")

    def write_atomic(self, relative: str, source: str) -> Path:
        path = self.resolve_relative(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.ndtikz.tmp")
        temp.write_text(source, encoding="utf-8")
        os.replace(temp, path)
        return path

    def digest(self, relative: str) -> str:
        data = self.resolve_relative(relative).read_bytes()
        return hashlib.sha256(data).hexdigest()
