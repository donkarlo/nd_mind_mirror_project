"""Resolve delete-reference usages without touching the GUI process."""

from __future__ import annotations

from pathlib import Path

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver,
)


class WorkspaceReferenceUsageScanService:
    """Scan one workspace for references to a collection of delete targets."""

    def execute(self, request: dict[str, object]) -> dict[str, object]:
        """Return JSON-safe occurrences grouped by normalized target path."""
        workspace_root = self._required_path(request.get("workspace_root"))
        raw_targets = request.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError("targets must be a non-empty list")

        ignore_file_path = self._optional_path(request.get("ignore_file_path"))
        resolver = WorkspaceReferenceResolver(workspace_root)
        usages_by_target: dict[str, list[dict[str, object]]] = {}
        errors: list[str] = []

        for raw_target in raw_targets:
            try:
                target = self._required_path(raw_target)
                usages = resolver.find_usages(
                    workspace_root,
                    target,
                    ignore_file_path=ignore_file_path,
                )
                usages_by_target[str(target)] = [
                    self._serialize_occurrence(usage) for usage in usages
                ]
            except Exception as exc:
                errors.append(f"{raw_target}: {exc}")

        return {
            "usages_by_target": usages_by_target,
            "errors": errors,
        }

    @staticmethod
    def _serialize_occurrence(usage: ReferenceOccurrence) -> dict[str, object]:
        """Serialize one reference occurrence for transport over QProcess stdout."""
        return {
            "command": usage.command,
            "raw_target": usage.raw_target,
            "target_path": str(usage.target_path) if usage.target_path is not None else "",
            "target_start": int(usage.target_start),
            "target_end": int(usage.target_end),
            "command_start": int(usage.command_start),
            "command_end": int(usage.command_end),
            "click_start": int(usage.click_start),
            "click_end": int(usage.click_end),
            "line": int(usage.line),
            "column": int(usage.column),
            "referring_file": str(usage.referring_file),
        }

    @staticmethod
    def _required_path(value: object) -> Path:
        """Normalize one required filesystem path."""
        if value in (None, ""):
            raise ValueError("required path is missing")
        return Path(str(value)).expanduser().resolve(strict=False)

    @staticmethod
    def _optional_path(value: object) -> Path | None:
        """Normalize one optional filesystem path."""
        if value in (None, ""):
            return None
        return Path(str(value)).expanduser().resolve(strict=False)
