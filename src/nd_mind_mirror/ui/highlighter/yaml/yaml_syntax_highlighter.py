from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from nd_mind_mirror.ui.highlighter.base.highlighter import Highlighter


class YamlSyntaxHighlighter(Highlighter):
    def __init__(self, document) -> None:
        super().__init__(document)

        key = QTextCharFormat()
        key.setForeground(QColor("#005CC5"))
        key.setFontWeight(QFont.Weight.Bold)

        string = QTextCharFormat()
        string.setForeground(QColor("#22863A"))

        scalar = QTextCharFormat()
        scalar.setForeground(QColor("#6F42C1"))

        punctuation = QTextCharFormat()
        punctuation.setForeground(QColor("#D73A49"))
        punctuation.setFontWeight(QFont.Weight.Bold)

        comment = QTextCharFormat()
        comment.setForeground(QColor("#6A737D"))
        comment.setFontItalic(True)

        self._rules = [
            (
                QRegularExpression(r"^\s*[-?](?=\s)"),
                punctuation,
            ),
            (
                QRegularExpression(
                    r"(?m)(^|\s)([A-Za-z_][A-Za-z0-9_.-]*)(?=\s*: )"
                ),
                key,
            ),
            (
                QRegularExpression(
                    r"(?m)(^|\s)([A-Za-z_][A-Za-z0-9_.-]*)(?=\s*:$)"
                ),
                key,
            ),
            (
                QRegularExpression(r"\"(?:\\.|[^\"\\])*\"|'[^']*'"),
                string,
            ),
            (
                QRegularExpression(
                    r"\b(?:true|false|null|yes|no|on|off|~|[-+]?\d+(?:\.\d+)?)\b"
                ),
                scalar,
            ),
        ]
        self._comment_expression = QRegularExpression(r"(^|\s)(#.*)$")

    def highlightBlock(self, text: str) -> None:
        for expression, text_format in self._rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart()
                length = match.capturedLength()

                # Key patterns include optional leading whitespace in the full
                # match; when capture group 2 exists, colour only the key.
                if match.lastCapturedIndex() >= 2 and match.captured(2):
                    start = match.capturedStart(2)
                    length = match.capturedLength(2)

                self.setFormat(start, length, text_format)

        comment_match = self._comment_expression.match(text)
        if comment_match.hasMatch():
            self.setFormat(
                comment_match.capturedStart(2),
                comment_match.capturedLength(2),
                self._comment_format(),
            )

    @staticmethod
    def _comment_format() -> QTextCharFormat:
        text_format = QTextCharFormat()
        text_format.setForeground(QColor("#6A737D"))
        text_format.setFontItalic(True)
        return text_format
