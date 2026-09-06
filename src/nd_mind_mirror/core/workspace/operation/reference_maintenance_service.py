"""Apply repository-wide path-reference maintenance outside the GUI process."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from nd_mind_mirror.core.workspace.path.path_reference_updater import PathReferenceUpdater
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import WorkspaceReferenceResolver


class WorkspaceReferenceMaintenanceService:
    """Execute batched move and delete reference updates with one write per source file."""

    def execute(self, request: dict[str, object]) -> dict[str, object]:
        """Execute one serialized maintenance request and return changed files and errors."""
        workspace_root = self._path(request.get("workspace_root"))
        ignore_file_path = self._optional_path(request.get("ignore_file_path"))
        if workspace_root is None:
            return {"changed_files": [], "errors": ["workspace_root is required"]}

        changed: set[Path] = set()
        errors: list[str] = []

        moves = self._move_mappings(request.get("moves"))
        excluded = self._paths(request.get("exclude_files"))
        if moves:
            try:
                changed.update(
                    PathReferenceUpdater.update_workspace_reference_mappings(
                        workspace_root,
                        moves,
                        ignore_file_path=ignore_file_path,
                        exclude_files=excluded,
                    )
                )
            except Exception as exc:
                errors.append(f"move reference update failed: {exc}")

        deletions = self._delete_targets_by_file(request.get("deletions"))
        if deletions:
            resolver = WorkspaceReferenceResolver(workspace_root)
            for referring_file, targets in deletions.items():
                if referring_file in excluded:
                    continue
                try:
                    source = referring_file.read_text(encoding="utf-8")
                except (OSError, UnicodeError) as exc:
                    errors.append(f"could not read {referring_file}: {exc}")
                    continue

                updated = source
                for target in targets:
                    updated = resolver.remove_references(
                        updated,
                        referring_file,
                        target,
                    )
                if updated == source:
                    continue
                try:
                    self._write_text_atomic(referring_file, updated)
                except OSError as exc:
                    errors.append(f"could not write {referring_file}: {exc}")
                    continue
                changed.add(referring_file.resolve(strict=False))

        return {
            "changed_files": [str(path) for path in sorted(changed)],
            "errors": errors,
        }

    @staticmethod
    def _path(value: object) -> Path | None:
        """Normalize one required path-like value."""
        if value in (None, ""):
            return None
        try:
            return Path(str(value)).expanduser().resolve(strict=False)
        except (OSError, TypeError, ValueError):
            return None

    @classmethod
    def _optional_path(cls, value: object) -> Path | None:
        """Normalize an optional path-like value."""
        return cls._path(value)

    @classmethod
    def _paths(cls, value: object) -> set[Path]:
        """Normalize a serialized list of path-like values."""
        if not isinstance(value, list):
            return set()
        result: set[Path] = set()
        for item in value:
            path = cls._path(item)
            if path is not None:
                result.add(path)
        return result

    @classmethod
    def _move_mappings(cls, value: object) -> list[tuple[Path, Path]]:
        """Normalize serialized move mappings."""
        if not isinstance(value, list):
            return []
        result: list[tuple[Path, Path]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            old_path = cls._path(item.get("old"))
            new_path = cls._path(item.get("new"))
            if old_path is None or new_path is None or old_path == new_path:
                continue
            result.append((old_path, new_path))
        return result

    @classmethod
    def _delete_targets_by_file(cls, value: object) -> dict[Path, list[Path]]:
        """Group serialized delete targets by the referring file that needs rewriting."""
        grouped: dict[Path, list[Path]] = defaultdict(list)
        if not isinstance(value, list):
            return grouped
        for item in value:
            if not isinstance(item, dict):
                continue
            target = cls._path(item.get("target"))
            if target is None:
                continue
            raw_files = item.get("files")
            if not isinstance(raw_files, list):
                continue
            for raw_file in raw_files:
                referring_file = cls._path(raw_file)
                if referring_file is None:
                    continue
                if target == referring_file:
                    continue
                try:
                    referring_file.relative_to(target)
                    continue
                except ValueError:
                    pass
                if target not in grouped[referring_file]:
                    grouped[referring_file].append(target)
        return grouped

    @staticmethod
    def _write_text_atomic(path: Path, content: str) -> None:
        """Replace one text file atomically and clean the temporary file on failure."""
        temporary = path.with_name(f".{path.name}.nd_reference.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
