"""Change the heading level of a complete semantic LaTeX subtree."""

import re

from nd_mind_mirror.core.latex.hierarchy.transformer.heading_hierarchy_transformer import (
    HeadingHierarchyTransformer,
)
from nd_mind_mirror.core.latex.structure.latex_structure_item import LatexStructureItem


class LatexStructureLevelPlanner:
    """Promote or demote a heading and all nested headings by exactly one level."""

    _DOCUMENT_CLASS = re.compile(
        r"\\documentclass(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}"
    )
    _HEADING_KINDS = frozenset(HeadingHierarchyTransformer._CANONICAL_HEADINGS)

    def change(
        self,
        source: str,
        structure: list[LatexStructureItem],
        position: int,
        direction: int,
    ) -> tuple[str, int] | None:
        """Return rewritten source and focus line, rejecting overflowing levels."""
        delta = -1 if direction < 0 else 1 if direction > 0 else 0
        if not delta:
            return None
        root = next(
            (node for node in structure if node.source_position == position), None
        )
        if root is None or root.kind not in self._HEADING_KINDS:
            return None
        match = self._DOCUMENT_CLASS.search(source)
        document_class = match.group(1) if match else "article"
        allowed = HeadingHierarchyTransformer(document_class).allowed_headings
        begin, end = int(root.source_position), int(root.source_end)
        headings = [
            item for item in structure
            if item.kind in self._HEADING_KINDS
            and begin <= item.source_position < end
        ]
        replacements = []
        for node in headings:
            if node.kind not in allowed:
                return None
            new_index = allowed.index(node.kind) + delta
            if not 0 <= new_index < len(allowed):
                return None
            offset = int(node.source_position)
            command = re.match(rf"\\{re.escape(node.kind)}(?P<star>\*)?", source[offset:])
            if command is None:
                return None
            new_command = "\\" + allowed[new_index] + (command.group("star") or "")
            replacements.append((offset, offset + command.end(), new_command))

        if not replacements:
            return None
        rewritten = source
        for start, stop, replacement in reversed(replacements):
            rewritten = rewritten[:start] + replacement + rewritten[stop:]
        return rewritten, int(root.line_number)
