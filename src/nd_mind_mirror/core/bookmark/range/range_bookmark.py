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

    def after_source_edit(
        self,
        position: int,
        chars_removed: int,
        inserted_text: str,
    ) -> "RangeBookmark | None":
        point = max(int(position), 0)
        removed = max(int(chars_removed), 0)
        inserted = str(inserted_text)
        added = len(inserted)
        cut_end = point + removed
        delta = added - removed
        start = int(self.start_char)
        end = int(self.end_char)

        if removed == 0:
            if point < start:
                return replace(
                    self,
                    start_char=start + added,
                    end_char=end + added,
                )
            if start <= point <= end:
                offset = max(0, min(point - start, len(self.text)))
                return replace(
                    self,
                    end_char=end + added,
                    text=self.text[:offset] + inserted + self.text[offset:],
                )
            return self

        if cut_end <= start:
            return replace(
                self,
                start_char=start + delta,
                end_char=end + delta,
            )
        if point >= end:
            return self

        new_start = start if start < point else point
        if start >= cut_end:
            new_start = start + delta

        if end <= point:
            new_end = end
        elif end >= cut_end:
            new_end = end + delta
        else:
            new_end = point + added

        new_start = max(new_start, 0)
        new_end = max(new_end, new_start)
        if new_end <= new_start:
            return None

        prefix_end = max(0, min(point - start, len(self.text)))
        suffix_start = max(0, min(cut_end - start, len(self.text)))
        new_text = self.text[:prefix_end] + inserted + self.text[suffix_start:]
        if not new_text:
            return None

        return replace(
            self,
            start_char=new_start,
            end_char=new_end,
            text=new_text,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "start_char": int(self.start_char),
            "end_char": int(self.end_char),
            "text": self.text,
            "name": self.name,
        }
