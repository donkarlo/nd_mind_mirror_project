"""Reject BibTeX paste operations that would introduce duplicate citation keys."""

from __future__ import annotations

from collections import Counter

from nd_mind_mirror.core.bibliography.bibtex_entry_key_parser import (
    BibtexEntryKeyParser,
)


class BibtexPasteGuard:
    """Detect duplicate keys introduced by a prospective plain-text paste."""

    def __init__(self, parser: BibtexEntryKeyParser | None = None) -> None:
        self._parser = parser or BibtexEntryKeyParser()

    def conflicts(
        self,
        document_source: str,
        selection_start: int,
        selection_end: int,
        pasted_text: str,
    ) -> tuple[str, ...]:
        """Return pasted keys that would duplicate another BibTeX entry."""
        pasted_entries = self._parser.parse(pasted_text)
        if not pasted_entries:
            return ()

        source = str(document_source)
        start = max(0, min(int(selection_start), len(source)))
        end = max(start, min(int(selection_end), len(source)))
        remaining_source = source[:start] + source[end:]

        remaining_keys = Counter(key for key, _line in self._parser.parse(remaining_source))
        pasted_keys = Counter(key for key, _line in pasted_entries)

        conflicts: list[str] = []
        seen: set[str] = set()
        for key, _line_number in pasted_entries:
            if key in seen:
                continue
            seen.add(key)
            if pasted_keys[key] > 1 or remaining_keys[key] > 0:
                conflicts.append(key)
        return tuple(conflicts)
