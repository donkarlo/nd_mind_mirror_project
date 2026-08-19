from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from nd_mind_mirror.ui.highlighter.base.highlighter import Highlighter


class LatexSyntaxHighlighter(Highlighter):
    def __init__(self, document) -> None:
        super().__init__(document)

        self._rules = []

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
                QRegularExpression(
                    r"\\begin\{[^}]+\}|\\end\{[^}]+\}"
                ),
                environment,
            ),
            (
                QRegularExpression(
                    r"\\[A-Za-z@]+"
                ),
                command,
            ),
            (
                QRegularExpression(
                    r"\$[^$]*\$"
                ),
                math,
            ),
            (
                QRegularExpression(
                    r"\[[^\]]*\]"
                ),
                option,
            ),
            (
                QRegularExpression(
                    r"[{}]"
                ),
                brace,
            ),
            (
                QRegularExpression(
                    r"(?<!\\)%[^\n]*"
                ),
                comment,
            ),
        ]

    def highlightBlock(self, text: str) -> None:
        for expression, text_format in self._rules:
            iterator = expression.globalMatch(text)

            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    text_format,
                )
