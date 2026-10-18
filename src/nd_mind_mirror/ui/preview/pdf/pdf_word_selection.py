"""Resolve a double-clicked PDF glyph to its full Unicode word and highlight."""

from __future__ import annotations

from math import hypot
from PySide6.QtCore import QPointF


def _word_char(char: str) -> bool:
    return char.isalnum() or char in "_'’" or char == "_"


def word_at_pdf_point(document, page: int, x: float, y: float):
    """Return (text, PDF-point rectangles) at a click, or None over whitespace.

    Qt's PDF text API knows the actual glyph coordinates, including columns and
    non-Latin scripts. Searching a small neighbourhood avoids a costly full-page
    character-by-character geometry walk and never selects a nearby paragraph.
    """
    if page < 0 or page >= document.pageCount():
        return None
    full_text = document.getAllText(page).text()
    if not full_text:
        return None
    candidates: set[int] = set()
    for radius in (4.0, 9.0):
        selection = document.getSelection(
            page, QPointF(x-radius, y), QPointF(x+radius, y)
        )
        if selection.isValid():
            lo = max(0, selection.startIndex() - 1)
            hi = min(len(full_text), selection.endIndex() + 2)
            candidates.update(range(lo, hi))
    if not candidates:
        return None

    best_index = -1
    best_distance = float('inf')
    for idx in sorted(candidates):
        if not _word_char(full_text[idx]):
            continue
        glyph = document.getSelectionAtIndex(page, idx, 1).boundingRectangle()
        if not glyph.isValid() or glyph.isEmpty():
            continue
        dx = max(glyph.left()-x, 0, x-glyph.right())
        dy = max(glyph.top()-y, 0, y-glyph.bottom())
        distance = hypot(dx, dy)
        if distance < best_distance:
            best_index = idx
            best_distance = distance
    # Don't highlight an unrelated word when the user clicked a margin.
    if best_index < 0 or best_distance > 4.0:
        return None

    first = last = best_index
    while first > 0 and _word_char(full_text[first - 1]):
        first -= 1
    while last + 1 < len(full_text) and _word_char(full_text[last + 1]):
        last += 1
    text = full_text[first:last + 1]
    selected = document.getSelectionAtIndex(page, first, last-first+1)
    if not selected.isValid() or not selected.text():
        return None
    rects = []
    # A word normally fits on one line. Break hyphenated/multiline PDF
    # selections into separate rectangular rows instead of painting across
    # the intervening whitespace.
    for polygon in selected.bounds():
        rect = polygon.boundingRect()
        if rect.isValid() and rect.width() > 0 and rect.height() > 0:
            rects.append([float(rect.x()), float(rect.y()),
                          float(rect.width()), float(rect.height())])
    return (selected.text(), rects) if rects else None
