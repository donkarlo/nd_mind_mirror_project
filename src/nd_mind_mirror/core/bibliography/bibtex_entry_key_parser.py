"""Parse top-level BibTeX entry keys without depending on a BibTeX package."""

from __future__ import annotations


class BibtexEntryKeyParser:
    """Extract citation keys and source line numbers from BibTeX entries."""

    _NON_CITATION_ENTRY_TYPES = frozenset({"comment", "preamble", "string"})

    def parse(self, source: str) -> list[tuple[str, int]]:
        """Return ``(key, line_number)`` pairs for top-level citation entries."""
        text = str(source)
        entries: list[tuple[str, int]] = []
        index = 0

        while index < len(text):
            at_index = self._next_top_level_at(text, index)
            if at_index < 0:
                break

            header = self._entry_header(text, at_index)
            if header is None:
                index = at_index + 1
                continue

            entry_type, opening_index, opening = header
            closing_index = self._matching_entry_end(text, opening_index, opening)
            search_end = closing_index if closing_index >= 0 else len(text)

            if entry_type.casefold() not in self._NON_CITATION_ENTRY_TYPES:
                comma_index = text.find(",", opening_index + 1, search_end)
                if comma_index >= 0:
                    key = text[opening_index + 1 : comma_index].strip()
                    if key and "\n" not in key and "\r" not in key:
                        line_number = text.count("\n", 0, at_index) + 1
                        entries.append((key, line_number))

            if closing_index >= 0:
                index = closing_index + 1
            else:
                index = max(opening_index + 1, at_index + 1)

        return entries

    @staticmethod
    def _next_top_level_at(text: str, start: int) -> int:
        """Find the next entry marker while skipping percent-line comments."""
        index = max(int(start), 0)
        while index < len(text):
            character = text[index]
            if character == "%":
                newline = text.find("\n", index + 1)
                if newline < 0:
                    return -1
                index = newline + 1
                continue
            if character == "@":
                return index
            index += 1
        return -1

    @staticmethod
    def _entry_header(
        text: str,
        at_index: int,
    ) -> tuple[str, int, str] | None:
        """Parse ``@type{`` / ``@type(`` and return its opening delimiter."""
        index = at_index + 1
        while index < len(text) and text[index].isspace():
            index += 1

        type_start = index
        while index < len(text) and (text[index].isalnum() or text[index] in "_-:"):
            index += 1
        if index == type_start:
            return None

        entry_type = text[type_start:index]
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text) or text[index] not in "{(":
            return None
        return entry_type, index, text[index]

    @staticmethod
    def _matching_entry_end(text: str, opening_index: int, opening: str) -> int:
        """Return the matching closing delimiter for one BibTeX entry."""
        expected_closing = "}" if opening == "{" else ")"
        stack: list[str] = [expected_closing]
        index = opening_index + 1
        in_quote = False

        while index < len(text):
            character = text[index]

            if character == "\\":
                index += 2
                continue

            if character == '"':
                in_quote = not in_quote
                index += 1
                continue

            if in_quote:
                index += 1
                continue

            if character == "%":
                newline = text.find("\n", index + 1)
                if newline < 0:
                    return -1
                index = newline + 1
                continue

            if character == "{":
                stack.append("}")
            elif character == "(":
                stack.append(")")
            elif stack and character == stack[-1]:
                stack.pop()
                if not stack:
                    return index
            index += 1

        return -1
