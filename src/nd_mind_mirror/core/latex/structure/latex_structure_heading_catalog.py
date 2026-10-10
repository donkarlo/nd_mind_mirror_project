"""Recognize standard and project-defined deep LaTeX sectioning commands."""

import re


class LatexStructureHeadingCatalog:
    """Provide sectioning ranks shared by Structure parsing and interaction."""

    _STANDARD_RANKS = {
        "part": 0,
        "chapter": 1,
        "section": 2,
        "subsection": 3,
        "subsubsection": 4,
        "paragraph": 5,
        "subparagraph": 6,
    }
    _DEEP_NAMES = ("four", "five", "six", "seven", "eight", "nine", "ten")
    _DEEP_RANKS = {
        **{f"ndsection{name}": rank for rank, name in enumerate(_DEEP_NAMES, start=5)},
        **{f"{'sub' * (rank - 2)}section": rank for rank in range(5, 12)},
        **{f"DeepSection:{level}": level + 1 for level in range(1, 11)},
    }
    HEADING_RANKS = {**_STANDARD_RANKS, **_DEEP_RANKS}
    _COMMANDS = tuple(sorted(
        set(_STANDARD_RANKS) | {name for name in _DEEP_RANKS if ":" not in name} | {"DeepSection"},
        key=len,
        reverse=True,
    ))
    COMMAND_PATTERN = re.compile(
        r"\\(?P<kind>" + "|".join(_COMMANDS) + r")(?P<star>\*)?(?![A-Za-z@])"
    )

    @classmethod
    def rank(cls, kind: str) -> int | None:
        return cls.HEADING_RANKS.get(kind)

    @classmethod
    def is_heading(cls, kind: str) -> bool:
        return kind in cls.HEADING_RANKS
