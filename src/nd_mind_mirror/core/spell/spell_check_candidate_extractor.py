"""Word extraction for LaTeX Source and rendered Visual text."""

from __future__ import annotations

import re


class SpellCheckCandidateExtractor:
    """Return spell-checkable words while excluding LaTeX-only regions."""

    _WORD_RE = re.compile(
        r"[A-Za-zÀ-ÖØ-öø-ÿÄÖÜẞäöüß]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿÄÖÜẞäöüß]+)?"
        r"|[\u0600-\u06FF]+(?:\u200c[\u0600-\u06FF]+)*"
    )
    _SOURCE_PROTECTED = (
        re.compile(r"(?<!\\)%[^\n]*"),
        re.compile(r"\$\$.*?\$\$", re.DOTALL),
        re.compile(r"\$[^$\n]*\$"),
        re.compile(r"\\\(.*?\\\)", re.DOTALL),
        re.compile(r"\\\[.*?\\\]", re.DOTALL),
        re.compile(
            r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|"
            r"tikzpicture|verbatim|minted|lstlisting)\}.*?"
            r"\\end\{[^}]+\}",
            re.DOTALL,
        ),
        re.compile(
            r"\\(?:documentclass|usepackage|begin|end|cite\w*|ref|eqref|label|"
            r"url|path|include|input|bibliography|bibliographystyle|"
            r"includegraphics)\*?(?:\[[^\]]*\])?\{[^{}]*\}"
        ),
        re.compile(r"(?:https?://|www\.)\S+"),
        re.compile(r"(?<!\w)/(?:[\w.\-]+/)*[\w.\-]+"),
        re.compile(r"\\[A-Za-z@]+\*?"),
    )
    _VISUAL_SKIPPED_KINDS = {"raw", "graphic"}

    def source_candidates(
        self,
        text: str,
        start: int = 0,
        end: int | None = None,
    ) -> list[tuple[int, int, str]]:
        source = str(text)
        left = max(int(start), 0)
        right = len(source) if end is None else min(max(int(end), left), len(source))
        segment = source[left:right]
        masked = list(segment)
        for pattern in self._SOURCE_PROTECTED:
            for match in pattern.finditer(segment):
                for index in range(match.start(), match.end()):
                    masked[index] = " "
        visible = "".join(masked)
        return [
            (left + match.start(), left + match.end(), match.group(0))
            for match in self._WORD_RE.finditer(visible)
            if len(match.group(0)) > 1 or match.group(0) in {"a", "I"}
        ]

    def source_word_at(
        self,
        text: str,
        position: int,
    ) -> tuple[int, int, str] | None:
        source = str(text)
        point = max(0, min(int(position), len(source)))
        line_start = source.rfind("\n", 0, point) + 1
        line_end = source.find("\n", point)
        if line_end < 0:
            line_end = len(source)
        for candidate in self.source_candidates(source, line_start, line_end):
            if candidate[0] <= point <= candidate[1]:
                return candidate
        return None

    def visual_candidates(
        self,
        document,
        start: int,
        end: int,
    ) -> list[tuple[int, int, str]]:
        left = max(int(start), 0)
        right = max(int(end), left)
        result: list[tuple[int, int, str]] = []
        block = document.findBlock(left)
        while block.isValid() and block.position() <= right:
            data = block.userData()
            kind = str(getattr(data, "kind", "") or "")
            if kind not in self._VISUAL_SKIPPED_KINDS:
                text = block.text()
                block_start = block.position()
                local_left = max(left - block_start, 0)
                local_right = min(right - block_start, len(text))
                for match in self._WORD_RE.finditer(text, local_left, local_right):
                    word = match.group(0)
                    if len(word) <= 1 and word not in {"a", "I"}:
                        continue
                    result.append(
                        (block_start + match.start(), block_start + match.end(), word)
                    )
            block = block.next()
        return result

    def visual_word_at(self, document, position: int) -> tuple[int, int, str] | None:
        point = max(int(position), 0)
        block = document.findBlock(point)
        if not block.isValid():
            return None
        data = block.userData()
        kind = str(getattr(data, "kind", "") or "")
        if kind in self._VISUAL_SKIPPED_KINDS:
            return None
        local_point = point - block.position()
        for match in self._WORD_RE.finditer(block.text()):
            if match.start() <= local_point <= match.end():
                return block.position() + match.start(), block.position() + match.end(), match.group(0)
        return None
