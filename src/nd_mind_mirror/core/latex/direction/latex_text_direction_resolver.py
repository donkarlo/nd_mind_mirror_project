from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class TextDirection(str, Enum):
    LEFT_TO_RIGHT = "ltr"
    RIGHT_TO_LEFT = "rtl"


@dataclass(frozen=True)
class DirectionDecision:
    direction: TextDirection
    reason: str


class LatexTextDirectionResolver:
    """Resolve visual direction for one line of LaTeX source text.

    The source is never changed. LaTeX structural/setup lines stay LTR, while
    ordinary prose can be laid out RTL when Persian/Arabic-script text
    dominates. Qt then handles Latin runs inside the RTL block with its normal
    Unicode bidirectional text layout.
    """

    _COMMAND_RE = re.compile(r"\\[A-Za-z@]+\*?")
    _LEADING_COMMAND_RE = re.compile(r"^\\([A-Za-z@]+)\*?")
    _COMMENT_RE = re.compile(r"(?<!\\)%")
    _NON_PROSE_ARGUMENT_COMMAND_RE = re.compile(
        r"\\(?:cite[A-Za-z]*|ref|eqref|pageref|autoref|cref|Cref|label)"
        r"\*?(?:\[[^\]]*\])?\{[^{}]*\}"
    )

    _ALWAYS_LTR_LEADING_COMMANDS = {
        "addcontentsline",
        "addtocounter",
        "addtolength",
        "author",
        "begin",
        "bibliography",
        "bibliographystyle",
        "chapter",
        "date",
        "def",
        "documentclass",
        "end",
        "include",
        "includegraphics",
        "input",
        "label",
        "let",
        "maketitle",
        "newcommand",
        "paragraph",
        "part",
        "providecommand",
        "renewcommand",
        "section",
        "setcounter",
        "setlength",
        "subparagraph",
        "subsection",
        "subsubsection",
        "title",
        "usegdlibrary",
        "usepackage",
        "usetikzlibrary",
    }

    def __init__(
        self,
        mode: str = "auto",
        persian_ratio_threshold: float = 0.35,
    ) -> None:
        self.set_preferences(mode, persian_ratio_threshold)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def persian_ratio_threshold(self) -> float:
        return self._persian_ratio_threshold

    def set_preferences(
        self,
        mode: str,
        persian_ratio_threshold: float,
    ) -> None:
        normalized = str(mode or "auto").strip().casefold()
        if normalized not in {"auto", "rtl", "ltr"}:
            normalized = "auto"
        self._mode = normalized
        self._persian_ratio_threshold = max(
            0.05,
            min(float(persian_ratio_threshold), 0.95),
        )

    def resolve(self, line: str) -> TextDirection:
        return self.decide(line).direction

    def decide(self, line: str) -> DirectionDecision:
        stripped = line.lstrip()

        if not stripped:
            return DirectionDecision(
                TextDirection.LEFT_TO_RIGHT,
                "empty",
            )

        if self._is_math_delimiter_line(stripped):
            return DirectionDecision(
                TextDirection.LEFT_TO_RIGHT,
                "math-delimiter",
            )

        if self._is_structural_or_setup_command_line(stripped):
            return DirectionDecision(
                TextDirection.LEFT_TO_RIGHT,
                "latex-control-line",
            )

        if self._mode == "ltr":
            return DirectionDecision(
                TextDirection.LEFT_TO_RIGHT,
                "forced-ltr",
            )

        searchable = self._text_for_language_detection(line)
        rtl_count, ltr_count = self._strong_script_counts(searchable)

        if self._mode == "rtl":
            return DirectionDecision(
                TextDirection.RIGHT_TO_LEFT,
                "forced-rtl-prose",
            )

        strong_total = rtl_count + ltr_count
        if strong_total == 0:
            return DirectionDecision(
                TextDirection.LEFT_TO_RIGHT,
                "no-strong-script",
            )

        rtl_ratio = rtl_count / strong_total
        if rtl_count > 0 and rtl_ratio >= self._persian_ratio_threshold:
            return DirectionDecision(
                TextDirection.RIGHT_TO_LEFT,
                f"rtl-ratio={rtl_ratio:.3f}",
            )

        return DirectionDecision(
            TextDirection.LEFT_TO_RIGHT,
            f"rtl-ratio={rtl_ratio:.3f}",
        )

    def _is_structural_or_setup_command_line(self, stripped: str) -> bool:
        match = self._LEADING_COMMAND_RE.match(stripped)
        if match is None:
            return False
        return match.group(1) in self._ALWAYS_LTR_LEADING_COMMANDS

    def _is_math_delimiter_line(self, stripped: str) -> bool:
        return (
            stripped.startswith("$$")
            or stripped.startswith(r"\[")
            or stripped.startswith(r"\]")
            or stripped.startswith(r"\(")
            or stripped.startswith(r"\)")
        )

    def _text_for_language_detection(self, line: str) -> str:
        comment_match = self._COMMENT_RE.search(line)
        if comment_match is not None:
            before = line[: comment_match.start()]
            after = line[comment_match.start() + 1 :]
            line = before + " " + after

        line = self._NON_PROSE_ARGUMENT_COMMAND_RE.sub(" ", line)
        line = self._COMMAND_RE.sub(" ", line)
        line = re.sub(r"[{}\[\]$&_~^]", " ", line)
        return line

    def _strong_script_counts(self, text: str) -> tuple[int, int]:
        rtl_count = 0
        ltr_count = 0

        for character in text:
            if self._is_arabic_script_letter(character):
                rtl_count += 1
                continue

            bidi = unicodedata.bidirectional(character)
            if bidi == "L" and character.isalpha():
                ltr_count += 1

        return rtl_count, ltr_count

    def _is_arabic_script_letter(self, character: str) -> bool:
        if not character.isalpha():
            return False

        codepoint = ord(character)
        return (
            0x0600 <= codepoint <= 0x06FF
            or 0x0750 <= codepoint <= 0x077F
            or 0x0870 <= codepoint <= 0x089F
            or 0x08A0 <= codepoint <= 0x08FF
            or 0xFB50 <= codepoint <= 0xFDFF
            or 0xFE70 <= codepoint <= 0xFEFF
        )
