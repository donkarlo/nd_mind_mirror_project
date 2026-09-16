"""Extract inline mathematics from canonical LaTeX source."""

from __future__ import annotations


class LatexInlineMathExtractor:
    r"""Extract unique ``$...$`` and ``\(...\)`` formulas in source order."""

    def extract(self, source: str) -> list[str]:
        text = self._without_comments(str(source))
        formulas: list[str] = []
        seen: set[str] = set()
        index = 0

        while index < len(text):
            if text.startswith(r"\(", index):
                end = self._find_unescaped(text, r"\)", index + 2)
                if end >= 0:
                    self._append_unique(
                        formulas,
                        seen,
                        text[index : end + 2].strip(),
                    )
                    index = end + 2
                    continue

            if text[index] == "$" and not self._is_escaped(text, index):
                if index + 1 < len(text) and text[index + 1] == "$":
                    end = self._find_unescaped(text, "$$", index + 2)
                    index = end + 2 if end >= 0 else index + 2
                    continue

                end = self._find_inline_dollar_end(text, index + 1)
                if end >= 0:
                    self._append_unique(
                        formulas,
                        seen,
                        text[index : end + 1].strip(),
                    )
                    index = end + 1
                    continue

            index += 1

        return formulas

    @staticmethod
    def _append_unique(formulas: list[str], seen: set[str], raw: str) -> None:
        if raw and raw not in seen:
            seen.add(raw)
            formulas.append(raw)

    @classmethod
    def _find_inline_dollar_end(cls, text: str, start: int) -> int:
        index = start
        while index < len(text):
            if text[index] == "\n":
                return -1
            if text[index] == "$" and not cls._is_escaped(text, index):
                if index + 1 >= len(text) or text[index + 1] != "$":
                    return index
            index += 1
        return -1

    @classmethod
    def _find_unescaped(cls, text: str, token: str, start: int) -> int:
        index = text.find(token, start)
        while index >= 0:
            if not cls._is_escaped(text, index):
                return index
            index = text.find(token, index + len(token))
        return -1

    @staticmethod
    def _is_escaped(text: str, index: int) -> bool:
        backslashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            backslashes += 1
            cursor -= 1
        return bool(backslashes % 2)

    @classmethod
    def _without_comments(cls, source: str) -> str:
        cleaned: list[str] = []
        for line in source.splitlines(keepends=True):
            comment = None
            for index, char in enumerate(line):
                if char == "%" and not cls._is_escaped(line, index):
                    comment = index
                    break
            if comment is None:
                cleaned.append(line)
            else:
                suffix = "\n" if line.endswith("\n") else ""
                cleaned.append(line[:comment] + suffix)
        return "".join(cleaned)
