"""Immutable source ranges projected as rendered LaTeX previews."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLatexPreviewSpan:
    """One renderable LaTeX source range with stable character offsets."""

    kind: str
    start: int
    end: int
    raw: str
    display: bool = False
