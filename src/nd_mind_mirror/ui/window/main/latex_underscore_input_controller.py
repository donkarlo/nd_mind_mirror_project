"""Escape literal underscores typed in ordinary LaTeX prose."""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt


class LatexUnderscoreInputController(QObject):
    """Turn a typed underscore into ``\\_`` only when LaTeX treats it as prose."""

    _PROTECTED_COMMANDS = {
        "autoref",
        "bibliography",
        "bibliographystyle",
        "cite",
        "citet",
        "citep",
        "cref",
        "Cref",
        "eqref",
        "graphicspath",
        "href",
        "include",
        "includegraphics",
        "includepdf",
        "input",
        "label",
        "lstinputlisting",
        "nocite",
        "pageref",
        "path",
        "ref",
        "url",
    }
    _MATH_ENVIRONMENTS = {
        "align",
        "align*",
        "aligned",
        "array",
        "displaymath",
        "equation",
        "equation*",
        "gather",
        "gather*",
        "math",
        "matrix",
        "pmatrix",
        "smallmatrix",
        "split",
        "vmatrix",
    }

    def eventFilter(self, watched, event) -> bool:
        if event.type() != QEvent.Type.KeyPress or event.text() != "_":
            return False
        if watched.__class__.__name__ != "LatexEditor":
            return False
        if str(getattr(watched, "edit_mode", "source")) != "source":
            return False
        if bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        ):
            return False

        cursor = watched.textCursor()
        source = watched.toPlainText()
        position = max(int(cursor.position()), 0)
        if self._literal_underscore_is_required(source, position):
            return False

        cursor.insertText(r"\_")
        watched.setTextCursor(cursor)
        event.accept()
        return True

    def _literal_underscore_is_required(self, source: str, position: int) -> bool:
        if position > 0 and source[position - 1] == "\\":
            return True
        if self._inside_comment(source, position):
            return True
        if self._inside_verbatim(source, position):
            return True
        if self._inside_math(source, position):
            return True
        return self._inside_protected_command_argument(source, position)

    @staticmethod
    def _inside_comment(source: str, position: int) -> bool:
        line_start = source.rfind("\n", 0, position) + 1
        line = source[line_start:position]
        for index, character in enumerate(line):
            if character == "%" and not LatexUnderscoreInputController._escaped(line, index):
                return True
        return False

    @staticmethod
    def _inside_verbatim(source: str, position: int) -> bool:
        prefix = source[:position]
        for environment in ("verbatim", "verbatim*", "minted", "lstlisting"):
            if prefix.rfind(f"\\begin{{{environment}}}") > prefix.rfind(
                f"\\end{{{environment}}}"
            ):
                return True
        line_start = prefix.rfind("\n") + 1
        line = prefix[line_start:]
        return bool(re.search(r"\\verb\*?.[^\n]*$", line))

    @classmethod
    def _inside_math(cls, source: str, position: int) -> bool:
        prefix = source[:position]
        for environment in cls._MATH_ENVIRONMENTS:
            if prefix.rfind(f"\\begin{{{environment}}}") > prefix.rfind(
                f"\\end{{{environment}}}"
            ):
                return True

        if prefix.rfind(r"\(") > prefix.rfind(r"\)"):
            return True
        if prefix.rfind(r"\[") > prefix.rfind(r"\]"):
            return True

        inline_math = False
        display_math = False
        index = 0
        while index < len(prefix):
            if prefix[index] == "\\":
                index += 2
                continue
            if prefix.startswith("$$", index):
                display_math = not display_math
                index += 2
                continue
            if prefix[index] == "$" and not display_math:
                inline_math = not inline_math
            index += 1
        return inline_math or display_math

    @classmethod
    def _inside_protected_command_argument(cls, source: str, position: int) -> bool:
        brace_start = cls._nearest_open_brace(source, position)
        if brace_start is None:
            return False
        prefix = source[max(0, brace_start - 180):brace_start]
        match = re.search(r"\\([A-Za-z@]+)\s*(?:\[[^\]]*\]\s*)?$", prefix)
        return bool(match and match.group(1) in cls._PROTECTED_COMMANDS)

    @classmethod
    def _nearest_open_brace(cls, source: str, position: int) -> int | None:
        depth = 0
        for index in range(position - 1, -1, -1):
            character = source[index]
            if cls._escaped(source, index):
                continue
            if character == "}":
                depth += 1
            elif character == "{":
                if depth == 0:
                    return index
                depth -= 1
        return None

    @staticmethod
    def _escaped(text: str, index: int) -> bool:
        slashes = 0
        cursor = index - 1
        while cursor >= 0 and text[cursor] == "\\":
            slashes += 1
            cursor -= 1
        return bool(slashes % 2)
