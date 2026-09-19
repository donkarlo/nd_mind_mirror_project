"""Resolve stale managed-graphic paths after Navigator renames."""

from __future__ import annotations

from pathlib import Path


class GraphicPathAliasRegistry:
    """Map old workspace paths to their current locations without touching files."""

    _MAX_REMAP_STEPS = 32

    def __init__(self, workspace_root: str | Path) -> None:
        self._workspace_root = Path(workspace_root).expanduser().resolve()
        self._aliases: dict[Path, Path] = {}

    def register(self, old_path: str | Path, new_path: str | Path) -> None:
        """Remember one authoritative file/folder rename and collapse stale aliases."""
        old = self._workspace_path(old_path)
        new = self._workspace_path(new_path)
        if old == new:
            return

        affected: list[tuple[Path, Path]] = []
        for source in tuple(self._aliases):
            resolved = self.resolve(source)
            try:
                relative = resolved.relative_to(old)
            except ValueError:
                continue
            affected.append((source, relative))

        # The destination now exists as an authoritative path. An older alias
        # rooted there must not redirect the newly renamed file/folder away.
        for source in tuple(self._aliases):
            if self._is_same_or_child(source, new):
                self._aliases.pop(source, None)

        self._set_alias(old, new)
        for source, relative in affected:
            self._set_alias(
                source,
                (new / relative).resolve(strict=False),
            )

    def resolve(self, path: str | Path) -> Path:
        """Return the newest known path, preferring a live filesystem identity."""
        current = self._workspace_path(path)
        for _ in range(self._MAX_REMAP_STEPS):
            # Aliases describe historical names. If that historical name has
            # since been recreated, the live filesystem object is authoritative
            # and must not be redirected through an older rename event.
            if current.exists():
                return current

            mapping = self._best_mapping(current)
            if mapping is None:
                return current
            old, new = mapping
            relative = current.relative_to(old)
            remapped = (new / relative).resolve(strict=False)
            self._assert_inside_workspace(remapped)
            if remapped == current:
                return current
            current = remapped
        return current

    def _set_alias(self, source: Path, destination: Path) -> None:
        self._assert_inside_workspace(source)
        self._assert_inside_workspace(destination)
        if source == destination:
            self._aliases.pop(source, None)
            return
        self._aliases[source] = destination

    def _best_mapping(self, path: Path) -> tuple[Path, Path] | None:
        candidates: list[tuple[Path, Path]] = []
        for old, new in self._aliases.items():
            if not self._is_same_or_child(path, old):
                continue
            candidates.append((old, new))
        if not candidates:
            return None
        return max(candidates, key=lambda item: len(item[0].parts))

    def _workspace_path(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self._workspace_root / candidate
        resolved = candidate.resolve(strict=False)
        self._assert_inside_workspace(resolved)
        return resolved

    def _assert_inside_workspace(self, path: Path) -> None:
        try:
            path.relative_to(self._workspace_root)
        except ValueError as exc:
            raise ValueError("Graphic path alias must stay inside the workspace") from exc

    @staticmethod
    def _is_same_or_child(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False
