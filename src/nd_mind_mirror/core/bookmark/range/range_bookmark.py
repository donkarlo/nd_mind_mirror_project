"""Canonical range bookmark model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from uuid import uuid4


@dataclass(frozen=True)
class RangeBookmark:
    """Bookmark one half-open character range in canonical source."""

    id: str
    start_char: int
    end_char: int
    text: str
    name: str = ""

    @classmethod
    def create(
        cls,
        start_char: int,
        end_char: int,
        text: str,
        *,
        name: str = "",
    ) -> "RangeBookmark":
        start = max(int(start_char), 0)
        end = max(int(end_char), start)
        return cls(
            id=uuid4().hex,
            start_char=start,
            end_char=end,
            text=str(text),
            name=str(name).strip(),
        )

    def with_range(
        self,
        start_char: int,
        end_char: int,
        source: str,
    ) -> "RangeBookmark | None":
        start = max(0, min(int(start_char), len(source)))
        end = max(start, min(int(end_char), len(source)))
        if end <= start:
            return None
        return replace(
            self,
            start_char=start,
            end_char=end,
            text=source[start:end],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "start_char": int(self.start_char),
            "end_char": int(self.end_char),
            "text": self.text,
            "name": self.name,
        }
