"""Extract display-math regions from canonical LaTeX source."""

from __future__ import annotations

import re


class LatexDisplayMathExtractor:
    """Find display formulas in source while preserving their exact LaTeX."""

    _DISPLAY_PATTERN = re.compile(
        r"(?P<bracket>\\\[.*?\\\])"
        r"|(?P<environment>"
        r"\\begin\{(?P<name>equation\*?|align\*?|gather\*?|multline\*?)\}"
        r".*?"
        r"\\end\{(?P=name)\}"
        r")",
        re.DOTALL,
    )

    def extract(self, source: str) -> list[str]:
        """Return unique display formulas in source order."""
        formulas: list[str] = []
        seen: set[str] = set()
        for match in self._DISPLAY_PATTERN.finditer(str(source)):
            raw = match.group(0).strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            formulas.append(raw)
        return formulas
