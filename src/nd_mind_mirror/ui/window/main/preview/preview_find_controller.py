"""Independent text search for the rendered PDF preview."""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class PreviewFindController:
    """Search and navigate any PDF viewer without sharing state between windows."""

    def __init__(
        self,
        panel,
        *,
        viewer=None,
        pdf_path_provider: Callable[[], Path | None] | None = None,
        insert_layout=None,
        insert_index: int = 2,
    ):
        self._panel = panel
        self._viewer = viewer if viewer is not None else panel.preview._pdf_view
        self._pdf_path_provider = (
            pdf_path_provider if pdf_path_provider is not None
            else lambda: panel.preview.current_pdf_path
        )
        self._document = QPdfDocument(panel)
        self._loaded_path: Path | None = None
        self._loaded_signature: tuple[int, int] | None = None
        self._matches: list[tuple[int, int]] = []
        self._position = -1
        self._sync_token = 0
        self._bar = QWidget(panel)
        layout = QHBoxLayout(self._bar)
        layout.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit(self._bar)
        self._input.setPlaceholderText("Find in PDF preview")
        previous = QPushButton("◀", self._bar)
        following = QPushButton("▶", self._bar)
        close = QPushButton("×", self._bar)
        self._status = QLabel("", self._bar)
        layout.addWidget(self._input, 1)
        layout.addWidget(previous)
        layout.addWidget(following)
        layout.addWidget(self._status)
        layout.addWidget(close)
        (insert_layout or panel.panel_layout).insertWidget(insert_index, self._bar)
        self._bar.hide()
        self._input.textChanged.connect(self._search)
        self._input.returnPressed.connect(self.next)
        previous.clicked.connect(self.previous)
        following.clicked.connect(self.next)
        close.clicked.connect(self.hide)

    def close_document(self) -> None:
        """Release the search document before its snapshot is removed."""
        self._document.close()

    def show(self):
        self._bar.show()
        self._input.setFocus()
        self._input.selectAll()
        self._search(self._input.text())

    def hide(self):
        self._bar.hide()
        self._set_find_state("", -1)
        self._viewer.setFocus()

    def _search(self, query: str):
        path = self._pdf_path_provider()
        if path is None or not Path(path).is_file():
            self._matches = []
            self._status.setText("No PDF")
            return
        path = Path(path)
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if path != self._loaded_path or signature != self._loaded_signature:
            self._document.close()
            if self._document.load(str(path)) != QPdfDocument.Error.None_:
                self._status.setText("PDF unavailable")
                return
            self._loaded_path = path
            self._loaded_signature = signature
        self._matches = []
        needle = query.casefold()
        if needle:
            for page in range(self._document.pageCount()):
                selection = self._document.getAllText(page)
                haystack = selection.text().casefold()
                cursor = 0
                while True:
                    position = haystack.find(needle, cursor)
                    if position < 0:
                        break
                    self._matches.append((page, position))
                    cursor = position + max(len(needle), 1)
        self._position = 0 if self._matches else -1
        self._navigate()

    def next(self):
        if self._matches:
            self._position = (self._position + 1) % len(self._matches)
            self._navigate()

    def previous(self):
        if self._matches:
            self._position = (self._position - 1) % len(self._matches)
            self._navigate()

    def _navigate(self):
        total = len(self._matches)
        self._status.setText(f"{self._position + 1 if total else 0}/{total}")
        if not total:
            self._set_find_state("", -1)
            return
        page, _ = self._matches[self._position]
        root = self._viewer.rootObject()
        if root is None:
            return
        self._set_find_state(self._input.text(), self._position)
        root.setProperty("syncPage", page)
        root.setProperty("syncX", 0.0)
        root.setProperty("syncY", 0.0)
        self._sync_token += 1
        root.setProperty("syncToken", self._sync_token)

    def _set_find_state(self, query: str, index: int) -> None:
        root = self._viewer.rootObject()
        if root is not None:
            root.setProperty("findQuery", query)
            root.setProperty("findResultIndex", index)
