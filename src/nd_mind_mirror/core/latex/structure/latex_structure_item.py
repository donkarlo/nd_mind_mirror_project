"""Immutable semantic row model for parsed LaTeX Structure entries."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LatexStructureItem:
    """Describe one Structure row and the canonical source span it owns."""

    kind: str
    title: str
    line_number: int
    level: int
    source_position: int
    source_end: int
    parent_source_position: int | None = None
    sibling_index: int = 0
