"""Plan semantic drag/drop moves for LaTeX Structure nodes."""

import re

from nd_mind_mirror.core.latex.hierarchy.transformer.heading_hierarchy_transformer import (
    HeadingHierarchyTransformer,
)
from nd_mind_mirror.core.latex.structure.latex_structure_item import (
    LatexStructureItem,
)


class LatexStructureMovePlanner:
    """Move complete semantic subtrees without silently reparenting other nodes."""

    _HEADING_KINDS = {
        "part",
        "chapter",
        "section",
        "subsection",
        "subsubsection",
        "paragraph",
        "subparagraph",
    }
    _DOCUMENT_CLASS_PATTERN = re.compile(
        r"\\documentclass(?:\s*\[[^\]]*\])?\s*\{(?P<name>[^{}]+)\}"
    )

    def move(
        self,
        source: str,
        structure: list[LatexStructureItem],
        source_position: int,
        target_position: int,
        placement: str,
    ) -> tuple[str, int] | None:
        """Return rewritten source and moved-start line, or None for an invalid drop."""
        dragged = self._item_at(structure, source_position)
        if dragged is None:
            return None

        normalized_placement = str(placement).strip().lower()
        if normalized_placement not in {"before", "after", "inside", "end"}:
            return None

        target = self._item_at(structure, target_position)
        if normalized_placement != "end" and target is None:
            return None

        start = max(int(dragged.source_position), 0)
        end = min(max(int(dragged.source_end), start), len(source))
        if start >= end:
            return None

        if target is not None:
            target_anchor = int(target.source_position)
            if start <= target_anchor < end:
                return None
            if normalized_placement == "inside" and not self._is_heading(target):
                return None

        # A heading has no explicit closing command in LaTeX. Placing a heading
        # beside a figure/table can therefore capture that leaf (and later leaves)
        # into the new heading. Reject that ambiguous operation instead of
        # changing unrelated parentage behind the user's back.
        if (
            self._is_heading(dragged)
            and target is not None
            and not self._is_heading(target)
            and normalized_placement in {"before", "after"}
        ):
            return None

        chunk = source[start:end]
        if self._is_heading(dragged):
            desired_root_kind = self._desired_root_heading_kind(
                source,
                structure,
                dragged,
                target,
                normalized_placement,
                start,
                end,
            )
            if desired_root_kind is None:
                return None
            transformed = self._retarget_heading_subtree(
                source,
                chunk,
                structure,
                dragged,
                start,
                end,
                desired_root_kind,
            )
            if transformed is None:
                return None
            chunk = transformed

        insertion = self._insertion_position(
            source,
            structure,
            dragged,
            target,
            normalized_placement,
        )
        if insertion is None:
            return None
        if start < insertion < end:
            return None

        source_without = source[:start] + source[end:]
        if insertion >= end:
            insertion -= end - start
        insertion = max(0, min(insertion, len(source_without)))

        chunk = self._prepare_chunk_for_insertion(source_without, insertion, chunk)
        rewritten = source_without[:insertion] + chunk + source_without[insertion:]
        if rewritten == source:
            return None
        moved_line = rewritten.count("\n", 0, insertion) + 1
        return rewritten, moved_line

    def _desired_root_heading_kind(
        self,
        source: str,
        structure: list[LatexStructureItem],
        dragged: LatexStructureItem,
        target: LatexStructureItem | None,
        placement: str,
        start: int,
        end: int,
    ) -> str | None:
        allowed = self._allowed_headings(source)
        if placement == "inside":
            if target is None or not self._is_heading(target):
                return None
            return self._child_heading_kind(target.kind, allowed)

        if placement in {"before", "after"}:
            if target is None or not self._is_heading(target):
                return None
            return target.kind if target.kind in allowed else None

        # Dropping on the empty viewport means a real root-level move. Use the
        # existing root hierarchy when possible rather than preserving a stale
        # subsection/subsubsection command without a parent.
        root_headings = [
            item
            for item in structure
            if (
                self._is_heading(item)
                and item.parent_source_position is None
                and not (start <= item.source_position < end)
            )
        ]
        if root_headings:
            kind = root_headings[-1].kind
            return kind if kind in allowed else None
        if dragged.parent_source_position is None and dragged.kind in allowed:
            return dragged.kind
        if "chapter" in allowed:
            return "chapter"
        return "section" if "section" in allowed else None

    def _retarget_heading_subtree(
        self,
        source: str,
        chunk: str,
        structure: list[LatexStructureItem],
        dragged: LatexStructureItem,
        absolute_start: int,
        absolute_end: int,
        desired_root_kind: str,
    ) -> str | None:
        """Shift every moved heading by one semantic hierarchy delta."""
        allowed = self._allowed_headings(source)
        try:
            source_root_index = allowed.index(dragged.kind)
            desired_root_index = allowed.index(desired_root_kind)
        except ValueError:
            return None

        delta = desired_root_index - source_root_index
        headings = [
            item
            for item in structure
            if (
                self._is_heading(item)
                and absolute_start <= item.source_position < absolute_end
            )
        ]
        headings.sort(key=lambda item: item.source_position)
        if not headings or headings[0].source_position != dragged.source_position:
            return None

        replacements: list[tuple[int, int, str]] = []
        for item in headings:
            try:
                source_index = allowed.index(item.kind)
            except ValueError:
                return None
            destination_index = source_index + delta
            if not (0 <= destination_index < len(allowed)):
                # Never clamp multiple deep headings to subparagraph. If the
                # relative hierarchy cannot be represented, reject the drop.
                return None
            destination_kind = allowed[destination_index]

            local = int(item.source_position) - absolute_start
            match = re.match(
                rf"\\{re.escape(item.kind)}(?P<star>\*)?",
                chunk[local:],
            )
            if match is None:
                return None
            star = match.group("star") or ""
            replacements.append(
                (
                    local,
                    local + match.end(),
                    f"\\{destination_kind}{star}",
                )
            )

        value = chunk
        for begin, finish, replacement in reversed(replacements):
            value = value[:begin] + replacement + value[finish:]
        return value

    def _insertion_position(
        self,
        source: str,
        structure: list[LatexStructureItem],
        dragged: LatexStructureItem,
        target: LatexStructureItem | None,
        placement: str,
    ) -> int | None:
        if placement == "end":
            document_end = re.search(r"\\end\s*\{document\}", source)
            return document_end.start() if document_end is not None else len(source)
        if target is None:
            return None
        if placement == "before":
            return target.source_position
        if placement == "after":
            return target.source_end
        if placement != "inside" or not self._is_heading(target):
            return None

        if self._is_heading(dragged):
            # A moved heading becomes the last child of the requested parent.
            return target.source_end

        # Figures/tables have no explicit structural closing level. Insert a
        # direct leaf before the target's first direct child heading so it cannot
        # accidentally become content of that child heading.
        direct_child_headings = [
            item
            for item in structure
            if (
                self._is_heading(item)
                and item.parent_source_position == target.source_position
                and target.source_position < item.source_position < target.source_end
            )
        ]
        if direct_child_headings:
            return min(item.source_position for item in direct_child_headings)
        return target.source_end

    def _allowed_headings(self, source: str) -> tuple[str, ...]:
        match = self._DOCUMENT_CLASS_PATTERN.search(source)
        document_class = match.group("name").strip() if match is not None else "article"
        return HeadingHierarchyTransformer(document_class).allowed_headings

    @staticmethod
    def _child_heading_kind(
        parent_kind: str,
        allowed: tuple[str, ...],
    ) -> str | None:
        try:
            index = allowed.index(parent_kind)
        except ValueError:
            return None
        if index + 1 >= len(allowed):
            return None
        return allowed[index + 1]

    @classmethod
    def _is_heading(cls, item: LatexStructureItem) -> bool:
        return item.kind in cls._HEADING_KINDS

    @staticmethod
    def _prepare_chunk_for_insertion(source: str, insertion: int, chunk: str) -> str:
        value = chunk
        if insertion > 0 and source[insertion - 1] != "\n" and not value.startswith("\n"):
            value = "\n" + value
        if insertion < len(source) and source[insertion] != "\n" and not value.endswith("\n"):
            value = value + "\n"
        return value

    @staticmethod
    def _item_at(
        structure: list[LatexStructureItem],
        source_position: int,
    ) -> LatexStructureItem | None:
        target = int(source_position)
        for item in structure:
            if int(item.source_position) == target:
                return item
        return None
