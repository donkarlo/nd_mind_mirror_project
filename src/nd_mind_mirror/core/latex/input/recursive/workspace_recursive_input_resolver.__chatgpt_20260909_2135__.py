"""Resolve LaTeX inputs with the same path semantics as workspace operations."""

from pathlib import Path

from nd_mind_mirror.core.latex.input.recursive.recursive_input_resolver import (
    RecursiveInputResolver,
)
from nd_mind_mirror.core.workspace.path.workspace_reference_resolver import (
    WorkspaceReferenceResolver,
)


class WorkspaceRecursiveInputResolver(RecursiveInputResolver):
    """Apply the canonical workspace path modes to recursive Preview expansion."""

    _STRUCTURAL_PREVIEW_COMMANDS = {"input", "include"}

    def __init__(self, default_path: str | Path | None = None) -> None:
        super().__init__()
        self._workspace_reference_resolver = WorkspaceReferenceResolver(default_path)

    @property
    def default_path(self) -> Path | None:
        return self._workspace_reference_resolver.default_path

    def set_default_path(self, default_path: str | Path | None) -> None:
        self._workspace_reference_resolver.set_default_path(default_path)

    def resolve_reference(
        self,
        containing_file: str | Path,
        target: str,
        *,
        command: str = "input",
        require_exists: bool = True,
    ) -> Path | None:
        """Resolve one structural reference with canonical workspace semantics."""
        return self._workspace_reference_resolver.resolve(
            target,
            Path(containing_file).expanduser().resolve(strict=False),
            command=command,
            require_exists=require_exists,
        )

    def _resolve_target(
        self,
        containing_file: Path,
        target: str,
    ) -> Path | None:
        """Resolve only through the canonical workspace reference resolver.

        Relative references are resolved beside ``containing_file``. References
        beginning with ``/`` are resolved below ``search.default_path`` first
        and then as true operating-system absolute paths. Recursive Preview
        must never search the rest of the repository for a suffix match,
        because that can silently include an unrelated file.
        """
        return self.resolve_reference(
            containing_file,
            target,
            command="input",
            require_exists=True,
        )

    def _prepare_preamble(
        self,
        source: str,
        containing_file: Path,
    ) -> str:
        rewritten = self._rewrite_paths_for_preview(
            source,
            containing_file,
        )
        return super()._prepare_preamble(rewritten, containing_file)

    def _resolve_source(
        self,
        source: str,
        containing_file: Path,
        stack: set[Path],
        context: str,
        inherited_heading: str | None,
        heading_mapping: dict[str, str],
    ) -> tuple[str, str | None]:
        rewritten = self._rewrite_paths_for_preview(
            source,
            containing_file,
        )
        return super()._resolve_source(
            source=rewritten,
            containing_file=containing_file,
            stack=stack,
            context=context,
            inherited_heading=inherited_heading,
            heading_mapping=heading_mapping,
        )

    def _rewrite_paths_for_preview(
        self,
        source: str,
        containing_file: Path,
    ) -> str:
        """Materialize every local Preview path before temporary compilation.

        ``WorkspaceReferenceResolver.rewrite_paths_for_preview`` intentionally
        leaves structural commands untouched because normal workspace editing
        must preserve their authored path style. Preview compilation is
        different: a default-rooted reference such as ``/project/file.tex``
        must become its concrete filesystem path before the generated document
        is handed to LaTeX.
        """
        structural = self._rewrite_structural_paths_for_preview(
            source,
            containing_file,
        )
        return self._workspace_reference_resolver.rewrite_paths_for_preview(
            structural,
            containing_file,
        )

    def _rewrite_structural_paths_for_preview(
        self,
        source: str,
        containing_file: Path,
    ) -> str:
        output = source
        occurrences = self._workspace_reference_resolver.occurrences(
            source,
            containing_file,
            require_exists=True,
        )
        for occurrence in reversed(occurrences):
            if (
                occurrence.command not in self._STRUCTURAL_PREVIEW_COMMANDS
                or occurrence.target_path is None
            ):
                continue
            output = (
                output[: occurrence.target_start]
                + occurrence.target_path.as_posix()
                + output[occurrence.target_end :]
            )
        return output
