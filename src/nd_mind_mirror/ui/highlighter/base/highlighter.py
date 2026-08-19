from PySide6.QtGui import QSyntaxHighlighter


class Highlighter(QSyntaxHighlighter):
    def __init__(self, document) -> None:
        super().__init__(document)
