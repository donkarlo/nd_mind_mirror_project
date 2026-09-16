"""Canvas geometry shared by iPad-backed TikZ preview renderers."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TikZCanvasGeometry:
    """Resolve logical and pixel canvas geometry from canonical source metadata."""

    pixel_width: int
    pixel_height: int
    logical_width: float = 16.0
    logical_height: float = 11.0

    DEFAULT_WIDTH = 760
    DEFAULT_HEIGHT = 980
    MAX_DIMENSION = 1400
    _MARKER = re.compile(
        r"^%\s*nd_mind_mirror_canvas\s*:\s*(\d+)\s*x\s*(\d+)\s*$",
        re.MULTILINE | re.IGNORECASE,
    )

    @classmethod
    def from_source(cls, source: str) -> "TikZCanvasGeometry":
        """Return marked canvas geometry, or the iPad default when metadata is absent."""
        marked = cls.from_marker(source)
        if marked is not None:
            return marked
        return cls(pixel_width=cls.DEFAULT_WIDTH, pixel_height=cls.DEFAULT_HEIGHT)

    @classmethod
    def from_marker(cls, source: str) -> "TikZCanvasGeometry | None":
        """Return explicit source-backed geometry without guessing for generic TikZ."""
        match = cls._MARKER.search(source)
        if match is None:
            return None
        width = max(int(match.group(1)), 64)
        height = max(int(match.group(2)), 64)
        largest = max(width, height)
        if largest > cls.MAX_DIMENSION:
            scale = cls.MAX_DIMENSION / float(largest)
            width = max(int(round(width * scale)), 64)
            height = max(int(round(height * scale)), 64)
        return cls(pixel_width=width, pixel_height=height)
