from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter

try:
    from pygments.lexers import TextLexer, get_lexer_for_filename
    from pygments.token import Token
except Exception:  # pragma: no cover - graceful fallback when Pygments is absent
    TextLexer = None
    get_lexer_for_filename = None
    Token = None


class PygmentsSyntaxHighlighter(QSyntaxHighlighter):
    """Filename-aware syntax highlighting for arbitrary text files.

    Pygments is used because it supports a broad set of programming,
    configuration, markup, shell, data and documentation formats. Unknown
    text files simply fall back to plain text instead of failing to open.
    """

    def __init__(self, document, source_path: str | Path) -> None:
        super().__init__(document)
        self._source_path = Path(source_path)
        self._lexer = self._build_lexer()
        self._formats = self._build_formats()

    def set_source_path(self, source_path: str | Path) -> None:
        self._source_path = Path(source_path)
        self._lexer = self._build_lexer()
        self.rehighlight()

    def _build_lexer(self):
        if get_lexer_for_filename is None:
            return None
        try:
            return get_lexer_for_filename(self._source_path.name)
        except Exception:
            try:
                return TextLexer() if TextLexer is not None else None
            except Exception:
                return None

    @staticmethod
    def _format(
        color: str,
        *,
        bold: bool = False,
        italic: bool = False,
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        fmt.setFontItalic(italic)
        return fmt

    def _build_formats(self) -> list[tuple[object, QTextCharFormat]]:
        if Token is None:
            return []
        return [
            (Token.Comment, self._format("#6a737d", italic=True)),
            (Token.Keyword, self._format("#005cc5", bold=True)),
            (Token.Name.Builtin, self._format("#6f42c1")),
            (Token.Name.Function, self._format("#6f42c1", bold=True)),
            (Token.Name.Class, self._format("#6f42c1", bold=True)),
            (Token.Name.Tag, self._format("#22863a", bold=True)),
            (Token.Name.Attribute, self._format("#005cc5")),
            (Token.String, self._format("#032f62")),
            (Token.Number, self._format("#005cc5")),
            (Token.Operator, self._format("#d73a49")),
            (Token.Punctuation, self._format("#586069")),
            (Token.Generic.Heading, self._format("#005cc5", bold=True)),
            (Token.Generic.Subheading, self._format("#0366d6", bold=True)),
            (Token.Generic.Emph, self._format("#24292e", italic=True)),
            (Token.Generic.Strong, self._format("#24292e", bold=True)),
        ]

    def _format_for_token(self, token_type) -> QTextCharFormat | None:
        if Token is None:
            return None
        for parent, fmt in self._formats:
            if token_type in parent:
                return fmt
        return None

    def highlightBlock(self, text: str) -> None:
        if self._lexer is None or not text:
            return
        try:
            tokens = list(self._lexer.get_tokens(text))
        except Exception:
            return

        offset = 0
        for token_type, value in tokens:
            if not value:
                continue
            # Pygments may append a synthetic newline for a single block.
            visible = value.rstrip("\n")
            if visible:
                fmt = self._format_for_token(token_type)
                if fmt is not None:
                    self.setFormat(offset, len(visible), fmt)
            offset += len(value)
            if offset >= len(text):
                break
