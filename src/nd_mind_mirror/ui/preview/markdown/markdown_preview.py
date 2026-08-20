from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser


class MarkdownPreview(QTextBrowser):
    """Rendered live preview for Markdown text files."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        self.setStyleSheet(
            "QTextBrowser { background: white; color: #202124; padding: 18px; }"
        )

    def show_markdown(self, source: str, source_path: str | Path) -> None:
        path = Path(source_path).expanduser().resolve()
        base = QUrl.fromLocalFile(str(path.parent) + "/")
        self.document().setBaseUrl(base)
        self.setMarkdown(source)
