"""Materialize portable workspace-rooted LaTeX references only for Preview builds."""

from __future__ import annotations

from pathlib import Path

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


class LatexPreviewReferenceMaterializer:
    """Rewrite portable /project/... references in generated Preview source.

    Canonical user source and Preview templates stay portable.  Only the
    temporary source handed to LuaLaTeX receives real filesystem paths.
    """

    def __init__(self, default_path: str | Path | None = None) -> None:
        self._resolver = WorkspaceReferenceResolver(default_path)

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._resolver.set_default_path(default_path)

    def materialize(
        self,
        source: str,
        referring_file: str | Path,
    ) -> str:
        occurrences = self._resolver.occurrences(
            source,
            referring_file,
            require_exists=True,
        )
        replacements: list[tuple[int, int, str]] = []
        for occurrence in occurrences:
            # Relative references already have source-file semantics upstream.
            # This service exists specifically for portable workspace-rooted
            # references such as /nd_language_ai_project/... in Preview wrappers.
            if not occurrence.raw_target.strip().startswith("/"):
                continue
            target = occurrence.target_path
            if target is None:
                continue
            replacements.append(
                (occurrence.target_start, occurrence.target_end, target.as_posix())
            )

        result = source
        for start, end, replacement in sorted(replacements, reverse=True):
            result = result[:start] + replacement + result[end:]
        return result
