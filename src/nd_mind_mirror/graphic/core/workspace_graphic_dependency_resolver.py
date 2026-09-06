"""Collect Preview graphic dependencies with workspace-aware path resolution."""

from pathlib import Path
import re

from nd_mind_mirror.graphic.core.dependency_resolver import GraphicDependencyResolver
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


class WorkspaceGraphicDependencyResolver(GraphicDependencyResolver):
    """Resolve graphic/PDF dependencies through search.default_path as well as the OS."""

    _WORKSPACE_PATTERN = re.compile(
        r"\\(?P<command>includegraphics|includepdf)"
        r"(?:\s*\[[^\]]*\])?\s*\{(?P<path>[^}]+)\}",
        re.MULTILINE,
    )

    def __init__(self, default_path: str | Path | None = None) -> None:
        super().__init__()
        self._reference_resolver = WorkspaceReferenceResolver(default_path)

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._reference_resolver.set_default_path(default_path)

    def collect(
        self,
        source: str,
        source_path: str | Path | None,
        included_paths: list[Path] | tuple[Path, ...] = (),
    ) -> list[Path]:
        result: list[Path] = []
        seen: set[Path] = set()

        def scan(text: str, referring_file: Path) -> None:
            for match in self._WORKSPACE_PATTERN.finditer(text):
                raw = match.group("path").strip()
                if not raw or raw.startswith("\\"):
                    continue
                resolved = self._reference_resolver.resolve(
                    raw,
                    referring_file,
                    command=match.group("command"),
                    require_exists=True,
                )
                if resolved is None or resolved in seen:
                    continue
                seen.add(resolved)
                result.append(resolved)

        if source_path is not None:
            main = Path(source_path).expanduser().resolve()
            scan(source, main)

        for included in included_paths:
            try:
                path = Path(included).expanduser().resolve()
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            scan(text, path)

        return result
