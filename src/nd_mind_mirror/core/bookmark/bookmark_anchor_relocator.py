from __future__ import annotations


class BookmarkAnchorRelocator:
    """Keep line-based bookmarks attached to nearby source text.

    Bookmarks are persisted as simple dictionaries so they remain readable in
    session JSON.  ``anchor`` stores the normalized source line visible when the
    bookmark was created.  When lines are inserted or removed above a bookmark,
    the nearest matching anchor is used to relocate it.
    """

    @staticmethod
    def normalize_line(text: str) -> str:
        return " ".join(str(text).strip().split())[:240]

    def relocate(
        self,
        bookmarks: list[dict[str, object]],
        source: str,
    ) -> tuple[list[dict[str, object]], bool]:
        lines = str(source).splitlines()
        if not lines:
            lines = [""]

        normalized = [self.normalize_line(line) for line in lines]
        relocated: list[dict[str, object]] = []
        changed = False

        for raw in bookmarks:
            try:
                old_line = max(int(raw.get("line", 1)), 1)
            except (TypeError, ValueError):
                old_line = 1
            name = str(raw.get("name", "")).strip()
            try:
                column = max(int(raw.get("column", 1)), 1)
            except (TypeError, ValueError):
                column = 1
            anchor = self.normalize_line(str(raw.get("anchor", "")))
            old_line = min(old_line, len(lines))
            new_line = old_line

            current_anchor = normalized[old_line - 1]
            if anchor and current_anchor != anchor:
                candidates = [
                    index + 1
                    for index, value in enumerate(normalized)
                    if value == anchor
                ]
                if candidates:
                    new_line = min(candidates, key=lambda value: abs(value - old_line))
                else:
                    # The bookmarked line itself may have been edited. Keep the
                    # same logical line and adopt its new text as the anchor.
                    anchor = current_anchor
            elif not anchor:
                anchor = current_anchor

            item = {
                "line": int(new_line),
                "column": min(column, len(lines[new_line - 1]) + 1),
                "name": name,
                "anchor": anchor,
            }
            relocated.append(item)
            if (
                int(new_line) != int(old_line)
                or anchor != self.normalize_line(str(raw.get("anchor", "")))
            ):
                changed = True

        relocated.sort(
            key=lambda item: (
                int(item.get("line", 1)), int(item.get("column", 1))
            )
        )
        return relocated, changed
