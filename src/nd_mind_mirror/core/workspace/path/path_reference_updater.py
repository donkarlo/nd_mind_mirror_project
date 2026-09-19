r"""Rewrite workspace references, including Mind Mirror ``\seeherefooter`` links."""

from __future__ import annotations

import re

from nd_mind_mirror.core.workspace.path.path_reference_updater_base import (
    PathReferenceUpdater as PathReferenceUpdaterBase,
)


class PathReferenceUpdater(PathReferenceUpdaterBase):
    """Preserve path style while updating standard and seeherefooter references."""

    _LATEX_COMMAND_PATTERN = re.compile(
        r"(?P<prefix>\\(?P<command>"
        r"input|include|subfile|includegraphics|includepdf|addbibresource|"
        r"bibliography|lstinputlisting|verbatiminput|VerbatimInput|"
        r"includeonly|href|url|seeherefooter"
        r")\*?(?:\s*\[[^\]\n]*\])?\s*\{)"
        r"(?P<value>[^{}\n]+)"
        r"(?P<suffix>\})"
    )
