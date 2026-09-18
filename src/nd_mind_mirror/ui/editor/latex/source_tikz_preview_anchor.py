"""Source-position policy for inline TikZ preview placement."""

from __future__ import annotations


class SourceTikZPreviewAnchor:
    """Anchor a preview to the final visual character of its include/input line."""

    @staticmethod
    def position(start: int, end: int) -> int:
        return max(int(start), int(end) - 1, 0)
