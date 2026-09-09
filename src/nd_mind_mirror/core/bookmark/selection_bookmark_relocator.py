"""Relocate line bookmarks without losing their saved selection range."""

from __future__ import annotations

from nd_mind_mirror.core.bookmark.bookmark_anchor_relocator import (
    BookmarkAnchorRelocator,
)


class SelectionBookmarkRelocator(BookmarkAnchorRelocator):
    """Preserve and shift selection endpoints together with a relocated anchor."""

    def relocate(
        self,
        bookmarks: list[dict[str, object]],
        source: str,
    ) -> tuple[list[dict[str, object]], bool]:
        lines = str(source).splitlines() or [""]
        normalized_lines = [self.normalize_line(line) for line in lines]
        relocated: list[dict[str, object]] = []
        changed = False

        for raw in bookmarks:
            try:
                old_line = max(int(raw.get("line", 1)), 1)
            except (TypeError, ValueError):
                old_line = 1
            old_line = min(old_line, len(lines))

            try:
                column = max(int(raw.get("column", 1)), 1)
            except (TypeError, ValueError):
                column = 1

            anchor = self.normalize_line(str(raw.get("anchor", "")))
            current_anchor = normalized_lines[old_line - 1]
            new_line = old_line
            if anchor and current_anchor != anchor:
                candidates = [
                    index + 1
                    for index, value in enumerate(normalized_lines)
                    if value == anchor
                ]
                if candidates:
                    new_line = min(
                        candidates,
                        key=lambda value: abs(value - old_line),
                    )
                else:
                    anchor = current_anchor
            elif not anchor:
                anchor = current_anchor

            item: dict[str, object] = {
                "line": int(new_line),
                "column": min(column, len(lines[new_line - 1]) + 1),
                "name": str(raw.get("name", "")).strip(),
                "anchor": anchor,
            }

            selection = self.normalize_selection(raw.get("selection"), source)
            if selection is not None:
                delta = int(new_line) - int(old_line)
                shifted = self._shift_selection(selection, delta, lines)
                item["selection"] = shifted
                if shifted != selection:
                    changed = True

            relocated.append(item)
            if (
                int(new_line) != int(old_line)
                or anchor != self.normalize_line(str(raw.get("anchor", "")))
            ):
                changed = True

        relocated.sort(
            key=lambda item: (
                int(item.get("line", 1)),
                int(item.get("column", 1)),
            )
        )
        return relocated, changed

    @classmethod
    def normalize_selection(
        cls,
        raw: object,
        source: str,
    ) -> dict[str, object] | None:
        if not isinstance(raw, dict):
            return None
        anchor = cls._normalize_location(raw.get("anchor"), source)
        position = cls._normalize_location(raw.get("position"), source)
        if anchor is None or position is None or anchor == position:
            return None
        return {
            "anchor": [anchor[0], anchor[1]],
            "position": [position[0], position[1]],
            "text": str(raw.get("text", "")).strip()[:480],
        }

    @staticmethod
    def _normalize_location(
        raw: object,
        source: str,
    ) -> tuple[int, int] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return None
        lines = str(source).splitlines() or [""]
        try:
            line = max(int(raw[0]), 1)
            column = max(int(raw[1]), 1)
        except (TypeError, ValueError):
            return None
        line = min(line, len(lines))
        column = min(column, len(lines[line - 1]) + 1)
        return line, column

    @classmethod
    def _shift_selection(
        cls,
        selection: dict[str, object],
        delta: int,
        lines: list[str],
    ) -> dict[str, object]:
        def shifted(raw: object) -> list[int]:
            line, column = int(raw[0]), int(raw[1])
            line = max(1, min(line + int(delta), len(lines)))
            column = max(1, min(column, len(lines[line - 1]) + 1))
            return [line, column]

        return {
            "anchor": shifted(selection["anchor"]),
            "position": shifted(selection["position"]),
            "text": str(selection.get("text", "")).strip()[:480],
        }
