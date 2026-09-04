from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from nd_mind_mirror.ui.highlighter.base.highlighter import Highlighter


class LatexSyntaxHighlighter(Highlighter):
    """Highlight LaTeX with an explicit low-cost mode for large sources."""

    _LARGE_DOCUMENT_THRESHOLD_CHARS = 120_000

    def __init__(self, document) -> None:
        super().__init__(document)
        self._large_document_mode = False

        command = QTextCharFormat()
        command.setForeground(QColor("#005CC5"))
        command.setFontWeight(QFont.Weight.Bold)

        environment = QTextCharFormat()
        environment.setForeground(QColor("#D73A49"))
        environment.setFontWeight(QFont.Weight.Bold)

        comment = QTextCharFormat()
        comment.setForeground(QColor("#6A737D"))
        comment.setFontItalic(True)

        math = QTextCharFormat()
        math.setForeground(QColor("#B31D28"))

        option = QTextCharFormat()
        option.setForeground(QColor("#22863A"))

        brace = QTextCharFormat()
        brace.setForeground(QColor("#6F42C1"))

        self._rules = [
            (
                QRegularExpression(r"\\begin\{[^}]+\}|\\end\{[^}]+\}"),
                environment,
                "\\",
            ),
            (
                QRegularExpression(r"\\[A-Za-z@]+"),
                command,
                "\\",
            ),
            (
                QRegularExpression(r"\$[^$]*\$"),
                math,
                "$",
            ),
            (
                QRegularExpression(r"\[[^\]]*\]"),
                option,
                "[",
            ),
            (
                QRegularExpression(r"[{}]"),
                brace,
                "{}",
            ),
            (
                QRegularExpression(r"(?<!\\)%[^\n]*"),
                comment,
                "%",
            ),
        ]

    def set_large_document_mode(self, enabled: bool) -> None:
        value = bool(enabled)
        if value == self._large_document_mode:
            return
        self._large_document_mode = value
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        value = str(text)
        large_document = (
            self._large_document_mode
            or self.document().characterCount()
            >= self._LARGE_DOCUMENT_THRESHOLD_CHARS
        )

        if large_document and not self._may_contain_latex_token(value):
            return

        for expression, text_format, triggers in self._rules:
            if not any(trigger in value for trigger in triggers):
                continue
            iterator = expression.globalMatch(value)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    text_format,
                )

    @staticmethod
    def _may_contain_latex_token(text: str) -> bool:
        return any(
            character in text
            for character in ("\\", "%", "$", "[", "]", "{", "}")
        )
