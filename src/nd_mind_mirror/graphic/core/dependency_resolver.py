from __future__ import annotations

from pathlib import Path
import re


class GraphicDependencyResolver:
    _PATTERN = re.compile(
        r"\\includegraphics(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^}]+)\}",
        re.MULTILINE,
    )
    _EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".svg")

    def collect(
        self,
        source: str,
        source_path: str | Path | None,
        included_paths: list[Path] | tuple[Path, ...] = (),
    ) -> list[Path]:
        result: list[Path] = []
        seen: set[Path] = set()

        def scan(text: str, parent: Path) -> None:
            for match in self._PATTERN.finditer(text):
                raw = match.group("path").strip()
                if not raw or raw.startswith("\\"):
                    continue
                candidate = Path(raw).expanduser()
                if not candidate.is_absolute():
                    candidate = parent / candidate
                options = [candidate]
                if not candidate.suffix:
                    options = [candidate.with_suffix(ext) for ext in self._EXTENSIONS]
                for option in options:
                    try:
                        resolved = option.resolve()
                    except OSError:
                        continue
                    if resolved.exists():
                        if resolved not in seen:
                            seen.add(resolved)
                            result.append(resolved)
                        break

        if source_path is not None:
            main = Path(source_path).expanduser().resolve()
            scan(source, main.parent)
        else:
            scan(source, Path.cwd())

        for included in included_paths:
            try:
                path = Path(included).expanduser().resolve()
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            scan(text, path.parent)
        return result
