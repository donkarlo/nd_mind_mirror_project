"""Validate LaTeX structural references with canonical workspace path semantics."""

from pathlib import Path
import re

from nd_mind_mirror.core.latex.input.recursive.workspace_recursive_input_resolver import (
    WorkspaceRecursiveInputResolver,
)


class LatexInputReferenceValidator:
    """Find missing input/include targets using the Preview workspace resolver."""

    _ABSOLUTE_INPUT_PATTERN = re.compile(
        r"\\(?P<command>input|include)\s*\{(?P<path>/[^{}]+)\}"
    )

    def __init__(self, resolver: WorkspaceRecursiveInputResolver) -> None:
        self._resolver = resolver

    def first_missing_absolute_input(
        self,
        source: str,
        containing_file: str | Path,
    ) -> str | None:
        """Return the first unresolved rooted structural reference, if any."""
        source_path = Path(containing_file).expanduser().resolve(strict=False)
        for match in self._ABSOLUTE_INPUT_PATTERN.finditer(source):
            raw_path = match.group("path").strip()
            resolved = self._resolver.resolve_reference(
                containing_file=source_path,
                target=raw_path,
                command=match.group("command"),
                require_exists=True,
            )
            if resolved is None:
                return raw_path
        return None
