"""Workspace reference resolver with Mind Mirror custom LaTeX link commands."""

from __future__ import annotations

import re

from nd_mind_mirror.core.workspace.path.workspace_reference_resolver_base import (
    ReferenceOccurrence,
    WorkspaceReferenceResolver as WorkspaceReferenceResolverBase,
)


class WorkspaceReferenceResolver(WorkspaceReferenceResolverBase):
    r"""Resolve standard references plus local paths carried by ``\seeherefooter``."""

    _ONE = re.compile(
        r"\\(?P<command>input|include|subfile|includegraphics|includepdf|"
        r"addbibresource|lstinputlisting|verbatiminput|VerbatimInput|url|"
        r"seeherefooter)"
        r"\*?(?:\s*\[[^\]\n]*\])?\s*\{(?P<target>[^{}\n]+)\}"
    )
    _MARKERS = WorkspaceReferenceResolverBase._MARKERS + (
        "\\seeherefooter",
    )


__all__ = ["ReferenceOccurrence", "WorkspaceReferenceResolver"]
