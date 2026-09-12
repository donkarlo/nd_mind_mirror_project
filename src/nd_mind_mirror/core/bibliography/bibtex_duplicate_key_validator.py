"""Validate uniqueness of citation keys inside one BibTeX database."""

from __future__ import annotations

from collections import defaultdict

from nd_mind_mirror.core.bibliography.bibtex_entry_key_parser import (
    BibtexEntryKeyParser,
)


class BibtexDuplicateKeyValidator:
    """Find duplicate citation keys and all source lines where they occur."""

    def __init__(self, parser: BibtexEntryKeyParser | None = None) -> None:
        self._parser = parser or BibtexEntryKeyParser()

    def duplicates(self, source: str) -> dict[str, tuple[int, ...]]:
        """Return only keys that occur more than once, preserving source order."""
        line_numbers: dict[str, list[int]] = defaultdict(list)
        key_order: list[str] = []

        for key, line_number in self._parser.parse(source):
            if key not in line_numbers:
                key_order.append(key)
            line_numbers[key].append(line_number)

        return {
            key: tuple(line_numbers[key])
            for key in key_order
            if len(line_numbers[key]) > 1
        }
